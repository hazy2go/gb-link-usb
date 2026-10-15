# Firmware: Game Boy Printer emulator (Pico 2 W)

Our own firmware (Pico SDK 2.3.1, C). The first-light build of stacksmashing's firmware lives in `firstlight/` and is not part of this.

## Modes
- **Printer** (default): emulates the Game Boy Printer, described below.
- **Bridge**: the PC sends `ESC GBBRIDGE`; from then on the PC's bytes are the Game Boy's poll replies and the Game Boy's bytes go to the PC. Ends when the PC closes the port. Used by SODAX on the Game Boy (docs/SODAX.md).

## What it does (printer mode)
- The Game Boy is the clock master (printer mode). PIO program `src/gb_link.pio` is a clock **slave**: our bit goes out when SCK falls, the GB's bit is sampled when SCK rises, MSB first.
- `src/printer.c` answers like a Game Boy Printer: 0x00 to every byte, then `0x81` and the status byte in the two dummy bytes. Status sequence after PRINT: full, busy+full for 20 polls, full, idle (same behaviour as mofosyne's game-tested emulator; our code).
- Every byte from the Game Boy is streamed raw to the PC over USB serial (CDC). The PC decodes packets into images (`web/`, `tools/`).
- LED blinks once per complete packet.

## Reply timing (why the printer works two bytes ahead)
PIO autopull loads the reply for the next byte from the TX FIFO as soon as the current byte's last bit is out, before the CPU has seen the current byte. So the TX FIFO always holds one queued reply, primed with two zeros, and `printer_rx()` returns the reply for the byte **after next**. This is enough: the replies that matter (0x81 and the status, in the dummy bytes) are decided when the checksum arrives, which is two bytes before them.

## Pins (docs/breadboard.html, no level shifter on the Pico 2)
| GPIO | Signal | Cable |
|---|---|---|
| GP0 | SCK in | green, plug 5 |
| GP1 | data in (GB SOUT) | red, plug 2 |
| GP2 | data out (GB SIN) | orange, plug 3 |
| GND | GND | blue, plug 6 |

Inputs have pull-ups enabled (RP2350 erratum E9 and a defined idle level). Pico on USB before the Game Boy is switched on.

## Build and flash
```sh
cmake -S firmware -B firmware/build -G Ninja && ninja -C firmware/build   # -> firmware/build/gb_link_usb.uf2
```
Needs `PICO_SDK_PATH` and the Arm toolchain (see CLAUDE.md). Flash: hold BOOTSEL while plugging in and copy the .uf2, or `picotool reboot -f -u` while this firmware runs (USB reset interface) and then copy.

## Tests
`make -C firmware/test`: host test of the printer state machine (framing, 0x81/status placement with the two-byte lag, status sequence, checksum errors, garbage/resync).

## Using it
- Browser: `cd web && npm run serve`, open http://localhost:8000 in Chrome/Edge, Connect Pico, print from the game.
- Terminal: `python3 tools/printcap.py` captures to `captures/`, then `node tools/render.mjs captures/<file>.bin` writes PNGs.
