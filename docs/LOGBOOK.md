# Logbook

Every decision, check and result, in order. Dated headings, short "why". Corrections are written as corrections, not silent rewrites.

## 2026-10-15 Project start
- Idea (Hazy): Game Boy to USB-C PC connection through the link port, next project after the WiFi cart.
- Chose a **Pico (RP2040/RP2350)** over the ESP32: native USB, PIO handles the link timing, same chip family as the WiFi cart.
- DMG link signals are 5 V, so a **level shifter** sits between the cable and the Pico.
- Hazy's printer (Pokémon Pikachu set) has the **small** socket; that is why the MGB-004 adapter was needed with the DMG. (Earlier I said the printer used the big socket: wrong for this printer.)
- Bought a second DMG-04 (¥1,400, used) so one can be cut and the printer setup stays complete.
- Prior art surveyed (GitHub, 2026-10-15): stacksmashing/gb-link-firmware is the closest base (Pico + PIO + WebUSB); mofosyne's printer emulator is the protocol reference. See README credits.
- Parts ordered: Pico 2 WH, breadboard kit, BSS138 level shifters (PLAN.md).

## 2026-10-15 Cut DMG-04: four inner wires
- Hazy cut one DMG-04. Inner wires: **orange, red, blue, green** (4 wires). Shield / bare drain wire: not reported yet (ask). **Update:** Hazy reports bare strands wrapped around the 4 wires, i.e. a braided/spiral shield. Usually tied to the plug's metal shell and often to GND (pin 6) (verify by continuity before using it as GND).
- Colors are not standardised, so the pin mapping is still unknown. Likely set for 4 wires: SCK, SOUT, SIN, GND (VCC and SD often not carried by link cables) (verify by continuity).
- Prior art (mofosyne README) gives the cable-end pinout (1 5V, 2 SOUT, 3 SIN, 4 SD, 5 SCK, 6 GND) and confirms wire colours are not a reliable guide; data lines can be swapped in software, so only GND and SCK must be identified for sure. Added to PROTOCOL.md.

## 2026-10-15 Web decoder (no hardware needed)
- No ARM toolchain or Pico SDK on the Mac yet, so started with the web side, which can be tested now.
- `web/gbprinter.js`: packet parser with checksum check, RLE decompress, 2bpp tile decode, palette, joins PRINT strips into images. Written by us from Pan Docs + the RLE description in mofosyne's decoder (algorithm only, no code copied), so no GPL obligation from this file.
- Checked Pan Docs (Gameboy_Printer, Tile_Data): checksum rule and tile format confirmed. Pan Docs has no RLE details and no palette bit layout; those are marked (verify) in PROTOCOL.md.
- `web/index.html`: paste a hex dump or open a log/binary file, shows prints, PNG download. Demo button builds a 160x144 test print.
- Tests: `cd web && npm test`: 7/7 pass. Headless Chrome loads `index.html#demo`: 12 packets (INIT, 10 DATA, PRINT), one 160x144 image, four shades visible.
- Not tested yet: real printer data from a game. Next: capture from Pokémon Pikachu once the hardware works, or try public sample logs from mofosyne's repo.

## 2026-10-15 Toolchain installed
- `brew install --cask gcc-arm-embedded` needs sudo (system pkg install), so instead: downloaded the same Arm pkg (15.3.rel2, darwin-arm64), checked sha256 against the Homebrew cask (OK) and Apple notarization (OK), unpacked it with `pkgutil --expand-full` into `~/pico/arm-gnu-toolchain-15.3.rel2`. No sudo. Not the plain brew `arm-none-eabi-gcc` formula: it ships without newlib, which the Pico SDK needs.
- Pico SDK **2.3.1** (latest tag) in `~/pico/pico-sdk`, submodules incl. TinyUSB and cyw43-driver. ninja from brew; picotool was already in brew.
- `~/.zshrc`: `PICO_SDK_PATH`, `PICO_TOOLCHAIN_PATH`, toolchain on `PATH`.
- Check: built a test program for `PICO_BOARD=pico2_w` (USB stdio + onboard LED blink), `hello.uf2` produced, 0 errors. Not flashed yet (no Pico here).

## 2026-10-15 Cut DMG-04: pin mapping (multimeter, continuity)
Checked by Hazy with a multimeter, plug half we use, pins numbered looking into the plug (PROTOCOL.md diagram):

| Pin | Signal | Wire |
|---|---|---|
| 1 | 5 V | no contact in the plug |
| 2 | SOUT | red |
| 3 | SIN | orange |
| 4 | SD | no contact in the plug |
| 5 | SCK | green |
| 6 | GND | blue |
| shell | | bare shield (beeps to the metal shell) |

- Pin names are as seen from the Game Boy end this plug goes into: red carries the Game Boy's SOUT (data from the GB), orange goes to the GB's SIN (data to the GB) (verify on first light; swapping in software is fine per mofosyne).
- Not checked yet: whether the shell/shield is connected to pin 6 (GND). Not needed: blue is GND. Other cable half not mapped.
