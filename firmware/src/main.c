// gb-link-usb firmware for the Pico 2 W. The Game Boy is always the clock master.
//
// Printer mode (default): the Pico answers like a Game Boy Printer; every byte
// from the Game Boy is streamed to the PC (web/, tools/gbprint.mjs).
// Bridge mode: the PC sends BRIDGE_MAGIC, then every byte it sends is handed to
// the Game Boy as the reply to its next poll, and every byte the Game Boy sends
// goes to the PC (tools/sodax-bridge.mjs + rom/sodax.gb). Bridge mode ends when
// the PC closes the port.
// Bridge mode 2 (BRIDGE2_MAGIC, used by the Slow Horizons server): same, plus a side channel for the
// heartbeat. In the stream to the PC, a GB byte $FD is sent as $FD $00, and $FD $01 is followed by
// a heartbeat report: int32 ppb, uint32 intervals (little endian). ppb = how far the Game Boy's
// link clock (its crystal / 512) runs from nominal 8192 Hz, measured against the Pico's crystal.
//
// Core 1 runs the link (PIO + reply logic); core 0 does USB and the LED.
// Pins per board: board.h (breadboard or PCB rev A).
#include <stdio.h>
#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "pico/util/queue.h"
#include "hardware/pio.h"
#include "hardware/clocks.h"
#include "gb_link.pio.h"
#include "printer.h"
#include "board.h"
#ifdef LED_CYW43
#include "pico/cyw43_arch.h"
#endif

// A gap this long on the link ends any half-received packet and re-aligns the
// PIO to a byte boundary (the GB pauses far less than this inside a packet).
#define IDLE_RESYNC_US 100000   // also used while idle: the ROM pauses polling ~0.3 s every ~2 s for this

// Debug: answer this byte to everything instead of the printer replies (0 = off).
#ifndef DEBUG_FIXED_REPLY
#define DEBUG_FIXED_REPLY 0
#endif

// The PC sends this to switch to bridge mode.
static const char BRIDGE_MAGIC[] = "\x1bGBBRIDGE";
static const char BRIDGE2_MAGIC[] = "\x1bGBBRIDG2";
static const char CALIB_MAGIC[] = "\x1bGBCALIB2";   // bridge mode 2, heartbeat measures PIN_CAL instead of SCK

// Heartbeat (see sck_period in gb_link.pio)
#define HB_WINDOW 8192                  // intervals per report, about 1.2 s of continuous link traffic
typedef struct { int32_t ppb; uint32_t n; } heartbeat_t;
static uint hb_sm, hb_offset;
#ifdef PIN_CAL
static uint cal_sm = 99;
#endif
static void hb_measure(uint pin);
static queue_t hb_queue;                // reports, core 1 -> core 0
static volatile bool bridge2;           // bridge mode with the escaped side channel
static volatile bool hb_reset;          // core 0 changed the measured pin: core 1 drops its running sums

static PIO pio;
static uint sm, offset;
static queue_t rx_queue;            // bytes from the GB, core 1 -> core 0
static queue_t tx_queue;            // bridge mode: bytes for the GB, core 0 -> core 1
static volatile bool bridge;        // false = printer mode
static volatile uint32_t packets;   // packets seen, for the LED

static bool led_init(void) {
#ifdef LED_CYW43
    return cyw43_arch_init() == 0;
#else
    gpio_init(PIN_LED);
    gpio_set_dir(PIN_LED, GPIO_OUT);
    return true;
#endif
}

static void led_put(bool on) {
#ifdef LED_CYW43
    cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, on);
#else
    gpio_put(PIN_LED, on);
#endif
}

static void link_start(void) {
    pio_sm_set_enabled(pio, sm, false);
    pio_sm_clear_fifos(pio, sm);
    pio_sm_restart(pio, sm);
    pio_sm_exec(pio, sm, pio_encode_jmp(offset));
    // Replies run two bytes ahead (printer.h): prime the first two.
    pio_sm_put(pio, sm, (uint32_t)DEBUG_FIXED_REPLY << 24);
    pio_sm_put(pio, sm, (uint32_t)DEBUG_FIXED_REPLY << 24);
    pio_sm_set_enabled(pio, sm, true);
}

static void core1_main(void) {
    printer_t printer;
    printer_init(&printer);
    link_start();
    absolute_time_t last = get_absolute_time();
    bool idle = true;
    const double nominal = (double)clock_get_hz(clk_sys) / 8192.0;   // cycles per SCK period
    const uint32_t lo = (uint32_t)(nominal * 0.9), hi = (uint32_t)(nominal * 1.1);
    uint64_t hb_sum = 0;
    uint32_t hb_n = 0;

    for (;;) {
        if (hb_reset) { hb_reset = false; hb_sum = 0; hb_n = 0; }
        while (!pio_sm_is_rx_fifo_empty(pio, hb_sm)) {
            uint32_t cyc = 2 * pio_sm_get(pio, hb_sm) + 6;
            if (cyc < lo || cyc > hi) continue;          // between bytes, or split by a glitch
            hb_sum += cyc;
            if (++hb_n == HB_WINDOW) {
                heartbeat_t h = { (int32_t)((nominal * hb_n / (double)hb_sum - 1.0) * 1e9), hb_n };
                queue_try_add(&hb_queue, &h);
                hb_sum = 0; hb_n = 0;
            }
        }
        if (!pio_sm_is_rx_fifo_empty(pio, sm)) {
            uint8_t b = (uint8_t)pio_sm_get(pio, sm);
            uint8_t reply = 0;
            if (bridge) queue_try_remove(&tx_queue, &reply);   // 0 when the PC has nothing queued
            else reply = printer_rx(&printer, b);
            if (DEBUG_FIXED_REPLY) reply = DEBUG_FIXED_REPLY;
            pio_sm_put(pio, sm, (uint32_t)reply << 24);   // out shifts from bit 31
            queue_try_add(&rx_queue, &b);                  // drop if the PC is not reading
            packets = printer.packets;
            last = get_absolute_time();
            idle = false;
        } else if (!idle && absolute_time_diff_us(last, get_absolute_time()) > IDLE_RESYNC_US
                   && gpio_get(PIN_SCK)) {
            // a quiet link is a byte boundary: re-align the PIO (also recovers a Pico that started mid-byte)
            printer_abort_packet(&printer);
            link_start();
            idle = true;
        }
    }
}

// point the heartbeat timer at another pin (SCK normally, PIN_CAL for calibration)
static void hb_measure(uint pin) {
    pio_sm_set_enabled(pio, hb_sm, false);
    pio_sm_clear_fifos(pio, hb_sm);
    pio_sm_restart(pio, hb_sm);
    sck_period_init(pio, hb_sm, hb_offset, pin);
    hb_reset = true;
}

int main(void) {
    stdio_init_all();
    stdio_set_translate_crlf(&stdio_usb, false);   // binary stream
    bool led = led_init();
#ifdef PIN_SCK_DIR
    // The Game Boy is always the clock master here: SCK translator B to A.
    gpio_init(PIN_SCK_DIR);
    gpio_put(PIN_SCK_DIR, 0);
    gpio_set_dir(PIN_SCK_DIR, GPIO_OUT);
#endif

    pio = pio0;
    sm = pio_claim_unused_sm(pio, true);
    offset = pio_add_program(pio, &gb_link_slave_program);
    gb_link_slave_init(pio, sm, offset, PIN_SCK, PIN_IN, PIN_OUT);
    hb_sm = pio_claim_unused_sm(pio, true);
    hb_offset = pio_add_program(pio, &sck_period_program);
    sck_period_init(pio, hb_sm, hb_offset, PIN_SCK);
    queue_init(&hb_queue, sizeof(heartbeat_t), 16);

    queue_init(&rx_queue, sizeof(uint8_t), 16384);
    queue_init(&tx_queue, sizeof(uint8_t), 8192);
    multicore_launch_core1(core1_main);

    uint32_t seen = 0;
    absolute_time_t led_off = nil_time;
    size_t magic_pos = 0, magic2_pos = 0, magic3_pos = 0;
    for (;;) {
        uint8_t b;
        while (queue_try_remove(&rx_queue, &b)) {
            putchar_raw(b);
            if (bridge2 && b == 0xFD) putchar_raw(0x00);   // escape our side-channel marker
        }
        heartbeat_t h;
        while (queue_try_remove(&hb_queue, &h)) {
            if (!bridge2) continue;
            uint8_t f[10] = { 0xFD, 0x01 };
            for (int i = 0; i < 4; i++) { f[2 + i] = (uint8_t)((uint32_t)h.ppb >> (8 * i)); f[6 + i] = (uint8_t)(h.n >> (8 * i)); }
            for (int i = 0; i < 10; i++) putchar_raw(f[i]);
        }

        // Bytes from the PC: data for the GB in bridge mode, else watch for the magic.
        int c;
        while ((c = getchar_timeout_us(0)) >= 0) {
            if (bridge) {
                uint8_t d = (uint8_t)c;
                queue_try_add(&tx_queue, &d);   // never block: with the Game Boy off nothing drains this queue
            } else {
                magic_pos = (c == BRIDGE_MAGIC[magic_pos]) ? magic_pos + 1 : (c == BRIDGE_MAGIC[0]);
                magic2_pos = (c == BRIDGE2_MAGIC[magic2_pos]) ? magic2_pos + 1 : (c == BRIDGE2_MAGIC[0]);
                if (magic_pos == sizeof BRIDGE_MAGIC - 1) { bridge = true; bridge2 = false; magic_pos = magic2_pos = 0; }
                magic3_pos = (c == CALIB_MAGIC[magic3_pos]) ? magic3_pos + 1 : (c == CALIB_MAGIC[0]);
                if (magic2_pos == sizeof BRIDGE2_MAGIC - 1) {
                    while (queue_try_remove(&rx_queue, &b)) {}   // printer-mode leftovers would go out unescaped
                    bridge = true; bridge2 = true; magic_pos = magic2_pos = magic3_pos = 0;
                }
#ifdef PIN_CAL
                if (magic3_pos == sizeof CALIB_MAGIC - 1) {
                    bridge = true; bridge2 = true; magic_pos = magic2_pos = magic3_pos = 0;
                    if (cal_sm == 99) { cal_sm = pio_claim_unused_sm(pio, true); cal_square_init(pio, cal_sm, pio_add_program(pio, &cal_square_program), PIN_CAL); }
                    hb_measure(PIN_CAL);
                }
#endif
            }
        }
        if (bridge && !stdio_usb_connected()) {        // PC closed the port: back to printer
            bridge = false; bridge2 = false;
            hb_measure(PIN_SCK);   // leave calibration
            while (queue_try_remove(&tx_queue, &b)) {}
        }
        if (led) {
            if (packets != seen) {
                seen = packets;
                led_put(true);
                led_off = make_timeout_time_ms(80);
            } else if (!is_nil_time(led_off) && time_reached(led_off)) {
                led_put(false);
                led_off = nil_time;
            }
        }
        tight_loop_contents();
    }
}
