// gb-link-usb firmware: Game Boy Printer emulator on a Pico 2 W.
//
// Core 1 runs the link: PIO receives each byte from the Game Boy, the printer
// state machine decides the reply, and the byte is queued for USB.
// Core 0 sends the raw byte stream to the PC over USB CDC and drives the LED.
// The PC side (web/ page or tools/printcap.py) turns packets into images.
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

static PIO pio;
static uint sm, offset;
static queue_t rx_queue;            // bytes from the GB, core 1 -> core 0
static volatile uint32_t packets;   // packets seen, for the LED

static void link_start(void) {
    pio_sm_set_enabled(pio, sm, false);
    pio_sm_clear_fifos(pio, sm);
    pio_sm_restart(pio, sm);
    pio_sm_exec(pio, sm, pio_encode_jmp(offset));
    // Replies run two bytes ahead (printer.h): prime the first two.
    pio_sm_put(pio, sm, 0);
    pio_sm_put(pio, sm, 0);
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
            uint8_t reply = printer_rx(&printer, b);
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
    multicore_launch_core1(core1_main);

    uint32_t seen = 0;
    absolute_time_t led_off = nil_time;
    for (;;) {
        uint8_t b;
        while (queue_try_remove(&rx_queue, &b)) putchar_raw(b);
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
