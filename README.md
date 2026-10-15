# gb-link-usb

A small adapter that connects an original **Game Boy (DMG)** link port to a PC over **USB-C**, so a browser or desktop app can talk to the Game Boy through the link cable.

Sister project of the [WiFi Game Boy Cartridge (Rev B)](https://github.com/hazy2go/wifi-game-boy-cartridge). The cart gives the Game Boy WiFi; this gives it a wired link to a PC.

**Status (2026-10-15): idea and planning. Parts ordered, nothing built yet.** See `CLAUDE.md` for the full status and to-do list.

## Goal
1. **Game Boy Printer emulation** (first milestone): print from the Pokémon Pikachu / Game Boy Camera / any printer-supporting game straight to a PNG on the PC.
2. **Generic PC link:** send and receive bytes between a Game Boy ROM and a web page or app (chat, live data, controller input).
3. **Online link play:** two Game Boys in different places, linked over the internet (Tetris, Pokémon trades/battles).
4. **Final product:** our own small PCB (RP2040/RP2350 + level shifter + link plug + USB-C), JLC-assembled, in a 3D-printed case. No soldering for the user.

## How it works
```
Game Boy link port (5 V, SPI-like: SCK, SOUT, SIN)
   -> level shifter (5 V <-> 3.3 V)
   -> Raspberry Pi Pico 2 (RP2350): PIO handles the link timing, TinyUSB talks to the PC
   -> USB-C -> PC: browser page via WebUSB (no driver) or a desktop app
```
Details: `docs/PROTOCOL.md` (link port, timing, printer protocol). Plan and parts: `docs/PLAN.md`. Every decision and result: `docs/LOGBOOK.md`.

## Credits / prior art
- [stacksmashing/gb-link-firmware](https://github.com/stacksmashing/gb-link-firmware) (GPL-3): Pico + PIO SPI + TinyUSB WebUSB, used for [online Tetris](https://github.com/stacksmashing/gb-tetris-web). Closest to what we want.
- [mofosyne/arduino-gameboy-printer-emulator](https://github.com/mofosyne/arduino-gameboy-printer-emulator) (GPL-3): the reference printer emulator.
- [HerrZatacke/gb-printer-web](https://github.com/HerrZatacke/gb-printer-web) (MIT): web app that turns printer data into images.
- [Raphael-Boichot/The-TinyGB-Printer](https://github.com/Raphael-Boichot/The-TinyGB-Printer) (GPL-3): Pico-based printer emulator to PNG on SD.
- [Pan Docs](https://gbdev.io/pandocs/) for link port and printer documentation.
