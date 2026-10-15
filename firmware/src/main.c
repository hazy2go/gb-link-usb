// gb-link-usb firmware for the Pico 2 W. The Game Boy is always the clock master.
//
// Printer mode (default): the Pico answers like a Game Boy Printer; every byte
// from the Game Boy is streamed to the PC (web/, tools/gbprint.mjs).
// Bridge mode: the PC sends BRIDGE_MAGIC, then every byte it sends is handed to
// the Game Boy as the reply to its next poll, and every byte the Game Boy sends
// goes to the PC (tools/sodax-bridge.mjs + rom/sodax.gb). Bridge mode ends when
// the PC closes the port.
//
// Core 1 runs the link (PIO + reply logic); core 0 does USB and the LED.
#include <stdio.h>
#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "pico/util/queue.h"
#include "pico/cyw43_arch.h"
#include "hardware/pio.h"
#include "gb_link.pio.h"
#include "printer.h"

// Wiring (docs/breadboard.html): plug 5 SCK, plug 2 GB SOUT, plug 3 GB SIN.
#define PIN_SCK  0
#define PIN_IN   1   // from GB SOUT
#define PIN_OUT  2   // to GB SIN

// A gap this long on the link ends any half-received packet and re-aligns the
// PIO to a byte boundary (the GB pauses far less than this inside a packet).
#define IDLE_RESYNC_US 200000

// Debug: answer this byte to everything instead of the printer replies (0 = off).
#ifndef DEBUG_FIXED_REPLY
#define DEBUG_FIXED_REPLY 0
#endif

// The PC sends this to switch to bridge mode.
static const char BRIDGE_MAGIC[] = "\x1bGBBRIDGE";

static PIO pio;
static uint sm, offset;
static queue_t rx_queue;            // bytes from the GB, core 1 -> core 0
static queue_t tx_queue;            // bridge mode: bytes for the GB, core 0 -> core 1
static volatile bool bridge;        // false = printer mode
static volatile uint32_t packets;   // packets seen, for the LED

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

    for (;;) {
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
            printer_abort_packet(&printer);
            link_start();
            idle = true;
        }
    }
}

int main(void) {
    stdio_init_all();
    stdio_set_translate_crlf(&stdio_usb, false);   // binary stream
    bool led = cyw43_arch_init() == 0;

    pio = pio0;
    sm = pio_claim_unused_sm(pio, true);
    offset = pio_add_program(pio, &gb_link_slave_program);
    gb_link_slave_init(pio, sm, offset, PIN_SCK, PIN_IN, PIN_OUT);

    queue_init(&rx_queue, sizeof(uint8_t), 16384);
    queue_init(&tx_queue, sizeof(uint8_t), 8192);
    multicore_launch_core1(core1_main);

    uint32_t seen = 0;
    absolute_time_t led_off = nil_time;
    size_t magic_pos = 0;
    for (;;) {
        uint8_t b;
        while (queue_try_remove(&rx_queue, &b)) putchar_raw(b);

        // Bytes from the PC: data for the GB in bridge mode, else watch for the magic.
        int c;
        while ((c = getchar_timeout_us(0)) >= 0) {
            if (bridge) {
                uint8_t d = (uint8_t)c;
                queue_add_blocking(&tx_queue, &d);
            } else {
                magic_pos = (c == BRIDGE_MAGIC[magic_pos]) ? magic_pos + 1 : (c == BRIDGE_MAGIC[0]);
                if (magic_pos == sizeof BRIDGE_MAGIC - 1) { bridge = true; magic_pos = 0; }
            }
        }
        if (bridge && !stdio_usb_connected()) {        // PC closed the port: back to printer
            bridge = false;
            while (queue_try_remove(&tx_queue, &b)) {}
        }
        if (led) {
            if (packets != seen) {
                seen = packets;
                cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, true);
                led_off = make_timeout_time_ms(80);
            } else if (!is_nil_time(led_off) && time_reached(led_off)) {
                cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, false);
                led_off = nil_time;
            }
        }
        tight_loop_contents();
    }
}
