# PCB rev A: design spec

The product version of the breadboard: a small USB-C dongle with a built-in Game Boy link cable. No soldering, no cut cables for the user, safe in any power order. Same firmware as the breadboard (plus one direction pin).

Status 2026-10-16: **schematic and board routed, DRC 0 errors.** Next: fab outputs and JLC checks. Pins on the board: GP12 SCK, GP13 data from GB, GP14 data to GB, GP11 SCK direction, GP21 LED (see LOGBOOK). Never ordered: ordering is Hazy's job.

## Decisions (Hazy, 2026-10-16)
- **Built-in cable**: a short link cable soldered to the board (half of a cut cable; one cable makes two boards). Big plug = DMG version, small plug = Pocket/Color/Advance version. Same PCB.
- **Proper 5 V buffers**: 74LVC1T45 translators powered from USB 5 V on the Game Boy side. Real 5 V levels to the Game Boy, inputs and outputs safe when the board is unpowered (Ioff), so "Pico first" power order no longer matters.

## Block diagram
```
USB-C ──ESD──┬─ D+/D- (27R) ─────────────────── RP2350A ── W25Q128 flash (QSPI)
             │                                    │  12 MHz crystal
             └─ VBUS 5V ─ LDO 3.3V ─ +3V3 ────────┤  internal 1.1 V switcher (L1, from RPi minimal design)
                 │                                │
                 │                    GP0 ◄──► U4 74LVC1T45 (DIR = GP3) ◄──► SCK  ┐
                 │                    GP1 ◄─── U5 74LVC1T45 (B→A fixed) ◄─── SOUT │ ESD ── cable pads ── link cable
                 │                    GP2 ───► U6 74LVC1T45 (A→B fixed) ───► SIN  ┘      (SCK, SIN, SOUT, GND, shield)
                 └─ VCCB of U4-U6 (Game Boy side runs at 5 V)
                                      GP25 ── status LED       BOOTSEL button (QSPI_SS)
```
- Pins match the breadboard (GP0 SCK, GP1 data from GB, GP2 data to GB) so the firmware carries over; new: **GP3 = SCK direction** (low = Game Boy drives the clock, printer and bridge modes; high = Pico drives it, first-light style). Default pulled low.
- Small series resistors (33-100 Ω) on the Game Boy-side outputs to soften edges (the breadboard showed crosstalk from data edges onto SCK); ground trace or pour between SCK and the data lines on the board. The firmware glitch filter stays.
- The link port's own 5 V pin (pin 1) is not used: the board is powered from USB only.

## Core: Raspberry Pi RP2350A minimal design
Base: `RPI-RP2350A-MINIMAL_R4-S1` (Raspberry Pi Ltd, MIT, from datasheets.raspberrypi.com/rp2350/Minimal-KiCAD.zip). Keep its RP2350 + switcher + crystal + flash schematic and layout; replace micro-USB with USB-C; drop the pin headers.

## Parts (JLC stock checked 2026-10-16 with `hw/tools/jlc_search.py`)
| Part | Role | LCSC | Library | Stock |
|---|---|---|---|---|
| RP2350A (QFN-60) | MCU | C42411118 | extended | 6,312 |
| W25Q128JVSIQ (SOIC-8) | 16 MB flash | C97521 | **basic** | 66,988 |
| ABM8-272-T3 12 MHz | crystal (RPi's pick; X322512MSB4SI C9002 is 20 pF/80 ohm, off RPi's tuning) | C20625731 | extended | 6,216 |
| SN74LVC1T45DBVR (SOT-23-6) x3 | 5 V translators | C7843 | extended | 348,868 |
| TYPE-C-31-M-12 | USB-C receptacle (16 pin) | C165948 | extended | 380,560 |
| USBLC6-2SC6 | USB ESD | C7519 | extended | 31,188 |
| TPD4E05U06DQAR | link-line ESD (4 ch) | C138714 | extended | 243,275 |
| NCP1117ST33T3G (the minimal design's LDO) | 3.3 V LDO | C26537 | extended | 61,140 |
| AOTA-B201610S3R3-101-T | RP2350 regulator inductor (polarity-marked, RPi requires it) | C42411119 | extended | **4** (hold point) |
| SKRPABE010 x2 | BOOTSEL/RUN buttons (Wurth 434133025816 out of stock) | C115360 | extended | 33,840 |
| passives, LED, button | | basic parts where possible | | |

W25Q16JVUXIQ (the small flash) is out of stock (2 pcs); W25Q128JVSIQ is a basic part, so it costs less overall (no extended-part fee).

Order files and hold points: `hw/rev-a/fab/ORDER.md` (2026-10-16).

## Checks before any order (same rigor as the WiFi cart)
ERC/DRC clean, parity schematic/board, every pin checked against the JLC part (`pin_audit.py` approach), JLC stock and rotations (`make_bom.py`/`make_cpl.py` approach), 3D/fit check for the case, then Hazy reviews and orders.

## Open (verify)
- Cable strain relief: through-hole slots + zip tie, or a printed clamp in the case.
- Case: 3D-printed two-part shell around board + cable exit.
- RP2350A errata E9 (pull-downs) is moot behind the translators, but keep pull-ups on inputs.
