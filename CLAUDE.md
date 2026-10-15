# CLAUDE.md: handoff for agents working on this repo

Read this first, then `docs/PLAN.md` (stages, parts, inventory), `docs/PROTOCOL.md` (link port and printer protocol) and `docs/LOGBOOK.md` (decisions).

## Rules (from the owner, Hazy)
- Repo: `hazy2go/gb-link-usb`. With `gh`, always pass `--repo hazy2go/gb-link-usb`.
- Log every decision, check and result in `docs/LOGBOOK.md` (dated heading, short why). Corrections are written as corrections.
- Don't claim anything without evidence: test on hardware, quote the datasheet or Pan Docs. Mark unverified facts "(verify)".
- Hazy reads replies on Discord: short and plain, no long dashes as punctuation.
- Never spend money or place orders; buying is Hazy's job.
- Never cut or modify the **MGB-004 adapter** or the spare DMG-04 (printer setup).

## Where things stand (2026-10-16)
- **PCB rev A ready to order** (2026-10-16): `hw/rev-a/`, DRC 0 errors/0 warnings, order files + hold points in `hw/rev-a/fab/ORDER.md` (L1 inductor: 4 in JLC stock). Rebuild: `pcb_build.py` -> `pcb_route.py hand` -> `pcb_gnd.py` -> `pcb_route.py 60` (KiCad Python), then `hw/tools/make_fab.sh`. Firmware for it: `-DGBLINK_BOARD=revA` (GP12/13/14, DIR GP11, LED GP21).
- **Web page live:** https://hazy2go.github.io/gb-link-usb/ (GitHub Pages, deployed by `.github/workflows/pages.yml` on push to web/).
- **SODAX on Game Boy works on hardware** (2026-10-16): firmware bridge mode + `rom/sodax.gb` + `tools/sodax-bridge.mjs` (docs/SODAX.md). Release v0.2.0.
- **Public repo, MIT license** (firmware/firstlight/ GPL-3.0). Release **v0.1.0** has the printer firmware .uf2. README has user-facing setup; keep it in sync when behaviour changes.
- **Printer emulator works:** `firmware/` (our code) prints from the Game Boy to a PNG (first print 2026-10-15, LOGBOOK). Capture: `python3 tools/printcap.py`, render: `node tools/render.mjs`, or the web page (Web Serial). Test ROMs in `rom/` (linktest, printtest).
- **First light done:** Mac <-> Pico 2 W <-> DMG works both ways (1000 bytes, 0 errors). Direct wiring, no shifter (RP2350 GPIOs are 5 V tolerant while powered; Pico on USB before the GB). Wiring: green GP0, red GP1, orange GP2, blue GND. First-light firmware = stacksmashing + patch in `firmware/firstlight/`.
- One DMG-04 cut and mapped: red = SOUT (2), orange = SIN (3), green = SCK (5), blue = GND (6), shield = shell (LOGBOOK). Web printer decoder in `web/` works on test data (7 tests pass), not yet on real printer data.
- Hardware on hand: DMG, EverDrive, Pokémon Pikachu + printer (small socket), 2x DMG-04, MGB-004.
- Toolchain on the Mac: Arm GCC 15.3 in `~/pico/arm-gnu-toolchain-15.3.rel2`, Pico SDK 2.3.1 in `~/pico/pico-sdk`, env vars in `~/.zshrc`. Build with `-DPICO_BOARD=pico2_w`.
- Ordered, not arrived: Pico 2 WH, breadboard kit, BSS138 level shifters (loose pins).

## To do (in order)
1. **When parts arrive:** cut one DMG-04, map wires to pins (record in LOGBOOK), wire through the level shifter (PLAN.md stage 1).
2. ~~**First light:**~~ done 2026-10-15 (LOGBOOK). build and flash stacksmashing/gb-link-firmware unchanged on the Pico 2 to prove wiring; a test ROM on the EverDrive sends bytes, the PC receives them.
3. **Our firmware** in `firmware/` (Pico SDK, C): PIO link driver (slave mode first, for the printer), TinyUSB WebUSB + CDC.
4. ~~**Printer emulator**~~ works (first print 2026-10-15); still to test: more games, web page live. following mofosyne's emulator and Pan Docs (`docs/PROTOCOL.md`); web page in `web/` renders received tiles to PNG. Test with Pokémon Pikachu.
5. Raw bridge mode + online link mode.
6. Own PCB in `hw/` (KiCad): rev A designed and checked; Hazy orders (hold points in ORDER.md), then bring-up with `-DGBLINK_BOARD=revA`.
   **Before ordering rev A** (Hazy; details in `hw/rev-a/fab/ORDER.md`):
   - [ ] L1 inductor AOTA-B201610S3R3-101-T: JLC has 4, 5 boards need ~10. Order 2-3 boards, use JLC global sourcing, or wait. No substitute (RPi requires the polarity-marked part).
   - [ ] In JLC's placement preview: L1 dot sits on the board's silk dot (JLC's footprint marks disagree, verify).
   - [ ] In the preview: D101 LED cathode on the GND pad; pin 1 of U1, U3, U101-U105; J101 USB-C flush with the edge.
   - [ ] At upload: JLC accepts 0.25 mm vias on 2 layers (verify).
   - [ ] Cable: wire gauge fits the 0.5 mm pad holes (verify on the cable).

## Notes
- Prior-art code is GPL-3 (stacksmashing, mofosyne). If we copy from it, our firmware is GPL-3 too.
- WiFi cart repo for reference on process and tools: `~/wifi-game-boy-cartridge` (its CLAUDE.md).
