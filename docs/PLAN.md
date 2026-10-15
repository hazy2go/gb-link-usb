# Plan and parts

## Inventory (Hazy, 2026-10-15)
- Game Boy **DMG** (original), EverDrive flash cart (for test ROMs).
- **Pokémon Pikachu** + Game Boy Printer (the printer has the small socket).
- **DMG-04** link cables x2 (big plug on both ends): one to cut for the prototype, one spare.
- **MGB-004** adapter (big DMG socket to small plug), needed for the printer with the DMG. **Do not cut.**

Ordered (Amazon JP, 2026-10-15):
- Raspberry Pi **Pico 2 WH** (RP2350, WiFi, headers soldered).
- Breadboard kit (830 + 400 holes, jumpers).
- **4-channel BSS138 level shifter** modules (10 pack). Pins come loose: press-fit on the breadboard works for the slow link; solder for anything permanent.
- (Also Seeed XIAO ESP32C3, for the WiFi cart tests, not this project.)

Not yet: a multimeter (~¥1,500) would make mapping the cut cable easy.

## Stage 1: breadboard prototype
1. **Cut one DMG-04 in the middle.** Keep ~10 cm on the plug side. Strip and twist (or tin) the wire ends.
2. **Map the wires** to plug pins 1-6 (continuity). Write the mapping into LOGBOOK.
3. **Wire it:** GB GND to Pico GND; SCK, SOUT, SIN through the level shifter (HV side = GB 5 V, LV side = Pico 3.3 V). The shifter's HV supply: the link-port VCC pin (5 V from the Game Boy) or the Pico's VBUS, (decide and log; never connect GB VCC to Pico 3V3).
4. **First light:** flash stacksmashing's gb-link-firmware (or ours), run a simple test ROM on the EverDrive that sends bytes, check they arrive on the PC.
5. **Printer:** printer emulation in the firmware, browser page that turns packets into a PNG. Test with Pokémon Pikachu.

## Stage 2: firmware + web app (ours)
- Firmware: Pico SDK (C), PIO for the link (master and slave modes), TinyUSB WebUSB + CDC. Modes: printer emulator, raw bridge, online link (relay).
- Web: one static page (WebUSB): printer gallery, raw console, online link via a small relay server.

## Stage 3: our own PCB
- RP2040 or RP2350, USB-C, proper level shifter (e.g. a bidirectional buffer with direction set per signal: SCK direction depends on who is master), ESD protection, DMG link plug or socket, status LED.
- KiCad, checked like the cart (ERC/DRC, JLC parts check), JLC-assembled. 3D-printed case.

## Open questions
- Does the RP2350 tolerate 5 V on its inputs? (RP2350 datasheet; we use a level shifter anyway until checked.)
- Does a 3.3 V high reach the DMG's input threshold reliably? (Level shifter makes this moot.)
- BSS138 shifters slow down fast edges: fine at 8 kHz, check if we run the external clock fast.
- License: building on stacksmashing / mofosyne code means GPL-3 for the firmware.
