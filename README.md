# gb-link-usb

Connect an original **Game Boy** link port to a computer over USB with a **Raspberry Pi Pico 2 W**.

**Works today: Game Boy Printer emulator.** Print from a Game Boy game and get a PNG on your Mac, no printer and no paper needed. Tested on a DMG (original Game Boy) printing a Game Boy Camera photo.

Sister project of the [WiFi Game Boy Cartridge](https://github.com/hazy2go/wifi-game-boy-cartridge).

---

## Print from your Game Boy to PNG

### What you need
| Part | Notes |
|---|---|
| Raspberry Pi **Pico 2 W** (or 2 WH, with headers) | Must be a **Pico 2** (RP2350 chip): its pins tolerate the Game Boy's 5 V. An original Pico (RP2040) would need a level shifter. |
| A Game Boy **link cable** you can cut | DMG-04 (the original big-plug cable) was used here. You keep one plug end. |
| Breadboard + jumper wires | Or solder the cable straight to the Pico. |
| Multimeter (continuity beep) | To find which wire is which. Wire colours are not standard. |
| A Mac with [Node.js](https://nodejs.org) | For the double-click print tool. Any OS with Chrome or Edge can use the web page instead. |

### 1. Cut the cable and find the wires
Cut the link cable, keep one plug with some cable on it, strip the wires. Looking into the plug:
```
 ___________
|  6  4  2  |
 \_5__3__1_/
```
| Pin | Signal | Our cable's colour (yours may differ) |
|---|---|---|
| 2 | SOUT, data from the Game Boy | red |
| 3 | SIN, data to the Game Boy | orange |
| 5 | SCK, clock | green |
| 6 | GND | blue |
| 1, 4 | 5 V and SD: usually not in the cable, not needed | |

Use the multimeter's beep mode: a paperclip in a plug hole, the other probe on each wire end. Leave the shield (bare strands) unconnected and taped.

### 2. Wire it to the Pico
| Cable | Pico pin |
|---|---|
| pin 5, clock | **pin 1** (GP0) |
| pin 2, data from GB | **pin 2** (GP1) |
| pin 6, GND | **pin 3** (GND) |
| pin 3, data to GB | **pin 4** (GP2) |

Pin 1 is the corner pin next to the USB connector. Nothing else is connected: no level shifter, no power wires. A drawing with every breadboard hole is in [`docs/breadboard.html`](docs/breadboard.html) (open it in a browser).

> **Power order matters.** Plug the Pico into USB **before** switching the Game Boy on, and switch the Game Boy off **before** unplugging the Pico. The Pico 2's pins only tolerate 5 V while the Pico is powered.

### 3. Put the firmware on the Pico
1. Get `gb_link_usb.uf2`: from the [Releases](../../releases) page, or build it yourself (see [`firmware/README.md`](firmware/README.md)).
2. Hold the white **BOOTSEL** button on the Pico while plugging it into USB, then let go. A drive called **RP2350** appears.
3. Drag `gb_link_usb.uf2` onto that drive. It disappears and the Pico restarts as the printer.

### 4. Print
**Mac (easiest):**
1. Download this repo (green **Code** button > Download ZIP) and unzip it.
2. Double-click **`GB Printer.command`**. The first time macOS may block it: right-click it > **Open** > Open.
3. Wait for "Pico connected", then print from the game.
4. Every print is saved in **Pictures > GameBoy Prints** (normal size and a 4x version) with a sound. Leave the window open while printing.

**Any computer with Chrome or Edge:**
1. In the repo folder: `cd web && python3 -m http.server 8000`
2. Open http://localhost:8000, click **Connect Pico**, choose the Pico, print from the game.
3. Prints appear on the page with a PNG download link.

### Troubleshooting
| Problem | Try |
|---|---|
| The game says printer error | Check the wiring with the multimeter (plug pin to Pico pin). Swap the two data wires (pins 2 and 3) if your colours were mapped wrong. Power order: Pico first. |
| "Waiting for the Pico..." forever | Is the printer firmware on it? The Pico should show up as "Pico" by Raspberry Pi. Try another USB cable (some are charge-only). |
| Print not saved | Look at `gbprint.log` in the GameBoy Prints folder. The raw data of every session is kept in `raw/`; `node tools/render.mjs <file>` turns it into PNGs. |
| Web page: no Connect | Use Chrome or Edge on a desktop; Safari and Firefox have no Web Serial. Close the Mac tool first, only one program can use the Pico at a time. |

---

## How it works
```
Game Boy link port (5 V, SPI-like: SCK, SOUT, SIN)
   -> Pico 2 W: PIO state machine follows the Game Boy's clock (with a glitch filter),
      core 1 answers like a Game Boy Printer, core 0 streams the data over USB serial
   -> PC: tools/gbprint.mjs or the web page decode the packets into PNG images
```
- Firmware: [`firmware/`](firmware/) (Pico SDK, C). Printer logic is tested on the PC: `make -C firmware/test`.
- Decoder: [`web/gbprinter.js`](web/gbprinter.js), shared by the web page and the Mac tool. Tests: `cd web && npm test`.
- Protocol notes: [`docs/PROTOCOL.md`](docs/PROTOCOL.md). Every decision and test result: [`docs/LOGBOOK.md`](docs/LOGBOOK.md).
- Test ROMs for the Game Boy (`rom/`, build with [RGBDS](https://rgbds.gbdev.io)): `linktest.gb` (link echo test), `printtest.gb` (shows what a printer answers).

## Roadmap
1. ~~Game Boy Printer emulation~~ working.
2. Generic PC link: send and receive bytes between a Game Boy ROM and the computer (live data, chat, controller input).
3. Online link play: two Game Boys in different places (Tetris, Pokémon trades).
4. Own small PCB with USB-C and a case, so nobody has to cut a cable.

## Credits
- [Pan Docs](https://gbdev.io/pandocs/): link port and printer documentation.
- [mofosyne/arduino-gameboy-printer-emulator](https://github.com/mofosyne/arduino-gameboy-printer-emulator): the reference printer emulator; our printer status behaviour follows it (our own code).
- [stacksmashing/gb-link-firmware](https://github.com/stacksmashing/gb-link-firmware): Pico + PIO link firmware, used unchanged (plus a small patch) for our first wiring test in `firmware/firstlight/`.
- [HerrZatacke/gb-printer-web](https://github.com/HerrZatacke/gb-printer-web) and [Raphael-Boichot/The-TinyGB-Printer](https://github.com/Raphael-Boichot/The-TinyGB-Printer): prior art for printer images.
