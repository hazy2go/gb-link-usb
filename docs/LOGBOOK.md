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
- Shield vs blue (pin 6): **no continuity** (Hazy, multimeter). So the shield/shell is not tied to GND in this cable half; it floats. Leave it unconnected on the breadboard (insulated). Other cable half not mapped.

## 2026-10-15 Parts arrived; first-light firmware builds
- Pico 2 WH, breadboard kit, BSS138 shifters arrived.
- stacksmashing/gb-link-firmware does **not** build unchanged on SDK 2.3.1: `tud_vendor_control_request_cb` is poisoned in current TinyUSB. Minimal patch (rename to `tud_vendor_control_xfer_cb`, act on SETUP stage only) in `firmware/firstlight/`. Builds for `pico2_w`: `gbusb.uf2`, 0 errors. So step 2 is "unchanged except one API rename".
- Their pins (from source): GPIO0 = SCK (Pico is clock master), GPIO1 = in from GB SOUT, GPIO2 = out to GB SIN.
- **Decision: shifter HV side powered from Pico VBUS (pin 40, 5 V from USB).** Why: our cable has no 5 V wire (pin 1 empty), and GB VCC must never go to the Pico's 3V3. LV side from Pico 3V3(OUT) (pin 36).
- Note (verify): with the Pico on USB and the Game Boy off, the shifter's 10k pull-ups feed a little current into the GB's pins. Small (5 V / 10k = 0.5 mA per line), but turn the GB on before plugging the Pico in when possible.

## 2026-10-15 Pico 2 W alive
- BOOTSEL drive "RP2350" appears (INFO_UF2: UF2 Bootloader v1.0, RP2350). picotool sees chip RP2350 QFN60.
- `picotool load` failed at 13% (`picoboot::connection_error`), cause unknown (cable/macOS?). Copying the .uf2 onto the drive works.
- Test program (USB serial + LED): prints "hello from pico 2 w" twice a second on /dev/cu.usbmodem11101. Toolchain + board confirmed end to end.

## 2026-10-15 First-light software ready (not run on hardware yet)
- Correction to the earlier entry: the first-light firmware needed **two more** changes, not just the rename. Current TinyUSB buffers vendor (WebUSB) TX until 64 bytes or a flush, so the 1-byte replies would never be sent; added `tud_vendor_write_flush()`. Upstream `cdc_task` read the vendor stream instead of CDC (upstream bug), fixed so the plain serial port works. Patch and reasons in `firmware/firstlight/`.
- `rom/linktest.gb` (RGBDS 1.0.4, ours): GB as clock slave, replies last+1 (first 0x42), shows last byte + counter. Checked in PyBoy (headless): boots, draws "00 / 0000", waits with SC bit 7 set. Serial not exercised in the emulator.
- `tools/linktest.py`: sends 6 bytes over CDC, checks replies, hints at the likely fault (no reply / all FF / wrong).

## 2026-10-15 Breadboard layout
- Drew the stage-1 layout (`docs/breadboard.html`): Pico in c/h rows 3-22, shifter LV in d / HV in g rows 26-31, every jumper by hole. Power rails not used. Shifter pin order assumed (LV1 LV2 LV GND LV3 LV4): follow the module labels (verify on our module).
- Checked the Pico pins in the drawing against the official Pico 2 W pinout (raspberrypi.com pico2w-pinout.svg): 1 GP0, 2 GP1, 3 GND, 4 GP2, 36 3V3(OUT), 38 GND, 40 VBUS, USB at top. All match. Docs: Pico 2 W pinout "is the same as for Raspberry Pi Pico W and Pico WH".

## 2026-10-15 Breadboard wired, continuity checked (power off)
- Wired per `docs/breadboard.html`. Cable wires joined to male jumpers (wrapped, taped).
- Continuity (Hazy, multimeter): plug 6 to Pico GND pin 38, plug 5 to HV1, plug 2 to HV2, plug 3 to HV3: all beep. No short between pins 36/40, 36/38, 40/38. Photo not usable, so these checks replace it.

## 2026-10-15 Power-up check (GB not connected)
- Meter: M-01FB, DC V on 20 V range. Black on Pico pin 38 (GND).
- Pico pin 40 (VBUS) 4.7 V. Shifter HV first read 2.7 V: VBUS jumper not in the HV row (breadboard row mix-up), fixed: HV 4.8 V. LV ~3.3 V, LV1 ~3.3 V.
- HV1 (and HV4) read ~2.8 V with HV at 4.8 V: module HV net unpowered, only leakage from the 3.3 V side through the MOSFET body diode (3.3 V - ~0.5 V). Cause: loose press-fit header pins not contacting the module pads. After reseating: HV1 4.8 V.
- Lesson: press-fit headers are unreliable; solder the shifter headers before relying on it (PLAN.md already said so for permanent use).

## 2026-10-15 First-light firmware on the Pico, dry run (GB not connected)
- Flashed `gbusb.uf2` (copy to BOOTSEL drive). Enumerates as "USB to Game Boy Link Cable", VID 0xCAFE, CDC port /dev/cu.usbmodem11.
- Dry run `tools/linktest.py`: replies arrive (USB + PIO work) but all **00**, expected FF (data line idle high). Pico pin 2 (GP1) ~0 V, shifter LV2 ~2 V, continuity pin 2 to LV2 OK. Pressing the module down: no change, so not the press-fit this time.
- Cause: RP2350 GPIO default pull-down plus the E9 input leakage erratum (verify exact wording in the RP2350 datasheet errata) holds the node near 2 V against the shifter's 10k pull-up; reads as 0. RP2040 doesn't have this, so upstream never saw it.
- Fix: `gpio_pull_up(PIN_SIN)` after PIO init (patch item 4). Result: replies **FF FF FF FF FF FF**. Correct for no GB.
- For our own firmware: enable pull-ups (or disable pull-downs) on every input that goes through the BSS138 shifter.

## 2026-10-15 First light with the Game Boy: clock intermittent, data FF both ways
- GB running `linktest.gb`, cable in the GB link port, Pico on first-light firmware (with pull-up fix).
- `tools/linktest.py`: all FF. GB screen stayed 00 / 0000: no clock reached the GB.
- Clock burst (bytes sent nonstop): Pico pin 1 (GP0) ~1.9 V average (clock leaves the Pico), LV1 3.3 V, HV1 steady 5 V (nothing passes the module). Continuity pin 1 to LV1 pin and pin 4 to LV3 pin: OK. So: LV1 header pin not contacting the module pad (press-fit), same as HV1/HV4 earlier.
- Pressing/wiggling the module during bursts: GB counter moves (0005, later 000A, 000B), so the clock gets through when the module makes contact. GB always shows last byte FF; the Pico never received anything but FF (61,584 and 119,211 bytes sent, 0 non-FF replies).
- Swapped red/orange (red to HV3, orange to HV2) on the theory that the data lines were crossed: no change, still FF both ways. So the swap theory is not confirmed; current wiring after the swap: red = HV3, orange = HV2 (verify which is right once contacts are solid).
- Conclusion: press-fit headers make every channel unreliable. Next: solder the shifter headers, re-run continuity incl. module pads, then re-test both wire orders.

## 2026-10-15 Loopback tests isolate the fault: the shifter
- Shifter pins bent to wedge them (not soldered). linktest still all FF.
- Loopback through the shifter (GB unplugged, jumper HV2 row to HV3 row): sent 00 01 55 AA 0F F0 80 7E 3C, got all **FF**.
- Loopback on the Pico directly (jumper pin 2 row to pin 4 row, no shifter): got **00 01 55 AA 0F F0 80 7E 3C**, exact. So Pico, PIO, firmware, USB and the test script are good.
- Cable already passed continuity; ROM reacts to the external clock (GB counter moved when the clock got through). Fault is the shifter's data channels: press-fit header contacts (most likely). Next: solder the headers, repeat the shifter loopback, then the GB test.

## 2026-10-15 Decision: test without the level shifter (Pico 2 only)
- No soldering iron on hand, so the shifter can't be fixed today.
- RP2350 datasheet (RP-008373-DS-3): GPIO0-2 are "Digital IO (FT)". FT pins "will tolerate voltages up to 5.5 V, provided IOVDD is powered to 3.3 V" and draw very little current "whilst it is below 3.63 V and IOVDD is 0 V". Table 1683: VIH (FT) at IOVDD 3.3 V: min 2 V, max 5.5 V, "IOVDD must be powered to tolerate input voltages above 3.63V". VIL max 0.8 V.
- So the DMG's 5 V outputs can go straight into GP0-2 **while the Pico is powered**. Rule: Pico USB in before the Game Boy is switched on; Game Boy off before USB out. (RP2040 Picos do not have this; it only holds for RP2350.)
- Other direction: Pico drives 3.3 V highs into the DMG's SCK/SIN inputs. Whether the DMG reads 3.3 V as high reliably: not checked (verify). Can't damage anything; worst case it is not recognised.
- Answers PLAN.md open question "Does the RP2350 tolerate 5 V on its inputs?": yes, when powered (datasheet).
- Wire order: back to the measured map (red = plug pin 2 = GB SOUT to GP1, orange = pin 3 = GB SIN to GP2), because the earlier swap test was invalid (the shifter passed nothing either way).

## 2026-10-15 First light, half: PC to Game Boy works (no shifter)
- Direct wiring: green to GP0, red to GP1, orange to GP2, blue to GND. Pico powered before the GB.
- `tools/linktest.py` sent 01 10 20 7F A0 FE. **GB screen: last byte FE, counter 0006.** So the Pico's 3.3 V clock and data are read correctly by the DMG (answers the 3.3 V "verify" above: works on this unit), and orange = GB SIN (plug pin 3) is confirmed.
- Pico received all FF: GB to Pico (red, GP1) not working yet. Line reads high (GP1 pull-up), so likely red not connected (wrap/row). Checking continuity plug hole 2 to Pico pin 2.

## 2026-10-15 FIRST LIGHT: both directions work (no shifter)
- Fault in the GB-to-Pico direction was simple: red was still in an old shifter row (29), not in Pico pin 2's row. Moved it; continuity plug hole 2 to Pico pin 2: beep.
- `tools/linktest.py`: sent 01 10 20 7F A0 FE, expected 42 02 11 21 80 A1, **got 42 02 11 21 80 A1. PASS.**
- Stress test: 1000 random bytes (0x0C skipped, CDC quirk), 20 ms apart, 24.4 s: **999 replies checked, 0 wrong, 0 missing.**
- Final working wiring (direct, Pico 2 W only): green (plug 5, SCK) to GP0 / pin 1; red (plug 2, GB SOUT) to GP1 / pin 2; orange (plug 3, GB SIN) to GP2 / pin 4; blue (plug 6) to GND / pin 3; shield unconnected. The measured pin map was right all along.
- Pico is clock master at ~9.2 kHz (calculated, not measured). Power rule: Pico on USB before the GB is on (RP2350 FT pins need IOVDD for 5 V).
- Level shifter: parked until the headers can be soldered. Not needed for the RP2350 per datasheet; still wanted on our PCB for ESD/robustness (decide in stage 3).

## 2026-10-15 Printer emulator firmware (built, not yet run on hardware)
- `firmware/`: our own firmware. Core 1: PIO clock-slave link + printer state machine; core 0: USB CDC raw byte stream + LED. Pico SDK stdio_usb (so `picotool reboot` works without BOOTSEL).
- **Decision: USB CDC + Web Serial instead of WebUSB.** Why: no custom descriptors or landing-page URL needed, Chrome/Edge read CDC directly, and the same port works from Python. Revisit if we need a non-serial interface.
- Clock edge for slave mode: same as proven in first light (change on SCK fall, sample on rise). Pan Docs doesn't state the edge.
- Reply timing: PIO autopull means replies are queued two bytes ahead; printer returns the reply for byte i+2. Dummy replies (0x81, status) are decided at checksum time, exactly two bytes before. Documented in firmware/README.md.
- Status behaviour follows mofosyne's emulator (read for behaviour, code is ours): checked his gbp_serial_io.cpp (commit 43aa5ca). One difference: we report checksum errors (status bit 0) as a real printer does; mofosyne has that disabled. The web decoder now skips bad-checksum packets (the game resends).
- Host test `make -C firmware/test`: all pass. Status after PRINT: 04, 04, 06 x20, 04, 00.
- Firmware builds for pico2_w, 0 warnings. Web: 8/8 tests; page gets Connect Pico (Web Serial) + Save capture. Tools: `tools/printcap.py`, `tools/render.mjs` (PNG from capture; checked on a synthetic capture: 160x144 PNG).
- Next: flash, print from Pokémon Pikachu.

## 2026-10-15 Printer emulator: crosstalk on SCK found and fixed
- First Pikachu try: game shows a printer error. Capture: INIT received correctly (88 33 01 00 00 00 01 00 00 00), retried every ~4 s.
- `rom/printtest.gb` (ours): GB as clock master sends INIT + STATUS and shows the printer's replies. Result: all 00, no 0x81. Capture of the same run: every STATUS arrived **shifted by 2 bits** (22 0C C3 C0 ... = 88 33 0F 00 ... >> 2).
- Debug build answering 0xA5 to everything (`-DDEBUG_FIXED_REPLY=0xA5`): GB saw `08 42 10 84 21` repeating (a 1 every 5 bits), changing over time. So the TX path reaches the GB but our bit stream runs out of step with the GB's clock.
- Diagnosis: our data-out edges (orange) couple onto SCK (green) in the cable/breadboard; the PIO, polling SCK at 150 MHz with no filter, counted each spike as a clock. 0x81 has two 0-to-1 edges = 2 extra bits = the 2-bit shift, and the 1s were skipped within nanoseconds, so the GB read 00.
- Fix (firmware only): PIO glitch filter (an SCK edge counts only if the level still holds 1.6 us later; SM at 10 MHz; GB half-bit ~61 us), data-out pin slew SLOW + 2 mA drive, Schmitt trigger on SCK.
- Result, printtest.gb: INIT replies `00 x8, 81 00`, STATUS replies `00 x8, 81 00`. Correct (photo from Hazy).
- Note for the PCB: keep SCK away from SOUT/SIN or add a ground between them; the filter stays anyway.

## 2026-10-15 FIRST PRINT: Game Boy -> Pico 2 W printer emulator -> PNG
- With the glitch-filter firmware, the game printed without error ("printing" on screen, Hazy).
- Capture: INIT, 9 x DATA (640 bytes), empty DATA, PRINT (4 bytes), then STATUS polls; 117 packets, 0 checksum errors.
- `node tools/render.mjs`: one 160x144 image, a Pocket Camera photo with its frame, decoded correctly (palette assumption 0xE4 holds for this print). Saved locally as captures/first-print.png (captures/ is not committed).
- Firmware, decoder, and status emulation confirmed on real hardware for this game. Still to try: other printer games (compression, multi-part prints), the live web page.

## 2026-10-15 Hands-free print tool for Hazy
- `GB Printer.command` (double-click) runs `tools/gbprint.mjs`: waits for the Pico, saves each finished print to ~/Pictures/GameBoy Prints as PNG (1x + 4x), plays a sound, survives unplug/replug, keeps raw captures in `raw/`.
- Decoder marks the last image `open` when no feed-after has closed it yet (multi-part prints), so the tool waits instead of saving half a print; after 30 s quiet it saves whatever is there.
- PNG encoder moved to `tools/png.mjs` (shared with render.mjs). Checked: `--file` on the first-print capture saves 160x144 + 640x576 PNGs; live run connects to the Pico. Decoder tests 8/8.
- **Fix (Hazy report: the tool "messes with my other port"):** gbprint.mjs, printcap.py and linktest.py opened the *first* /dev/cu.usbmodem* and set it to raw mode, which could be another USB serial device. Now they find the port by USB vendor ID via ioreg: 0x2E8A (Raspberry Pi, printer firmware) or 0xCAFE (first-light firmware). Shared helper `tools/picoport.py`. Also two copies of the tool had been running at once (mine + Hazy's); I stopped both by accident, Hazy restarts it.
- **Fix 2:** the tool read the port with `fs.createReadStream`; on macOS an empty read from the tty came back as end-of-stream, so the tool "disconnected" and reconnected every second and saved nothing (Hazy's print at 23:42 only landed in raw/). Now: open the port first (so `stty raw` sticks while it is open), non-blocking reads, "no data" = wait, unplug = read error or device gone. Also the ioreg lookup failed silently with ENOBUFS (ioreg output > 1 MB, Node's default limit); maxBuffer raised. Checked: tool connects and holds /dev/cu.usbmodem101 steadily (lsof); the 23:42 capture decodes to one 160x144 print. Tool also logs to `gbprint.log` in the prints folder.

## 2026-10-15 Repo made public
- Hazy asked to make the repo public so others can use the printer emulator. Checked first: no keys/passwords/captures/photos in any commit. README rewritten with full setup instructions.
- Still open (Hazy to decide): license (proposed MIT, firstlight/ stays GPL-3), a v0.1 release with the prebuilt .uf2.

## 2026-10-16 README polish
- New README layout (hero banner, badges, quick start with wiring diagram and breadboard render, printing, troubleshooting, how it works, layout, development, roadmap). Images in docs/img: hero.svg and wiring.svg (drawn), breadboard.png and web-app.png (screenshots of our pages), sample-print.png (a test image sent through the full printer protocol and decoded by our code; labelled as such). The first real print is not used: it shows people, and the repo is public. Preview checked with GitHub's Markdown renderer.

## 2026-10-16 MIT license, release v0.1.0
- Hazy chose MIT for our code; firmware/firstlight/ stays GPL-3.0 (patch of stacksmashing's firmware), noted in LICENSE and README.
- Release v0.1.0: gb_link_usb.uf2 built clean from this commit (Pico SDK 2.3.1, Arm GCC 15.3, pico2_w), host tests and decoder tests pass before tagging.

## 2026-10-16 SODAX on the Game Boy (built, emulator-tested; hardware test next)
- Data: endpoints from `@sodax/sdk` 2.2.0 (MIT). Oracle candles `GET api.sodax.com/v1/be/oracle/candles` (138 symbols, intervals 1m/5m/1h/1d) and solver quotes `POST api.sodax.com/v1/intent/quote`, no API key. Hub token addresses + decimals from the solver oracle (chain 146). Checked live: BTC, ETH, SOL, SUI, XLM, AVAX, HYPE, POL, SODA all route to USDC. Python's urllib gets Cloudflare error 1010 (user agent); Node fetch and curl work, so the bridge is Node.
- Firmware: bridge mode. PC sends `ESC GBBRIDGE`; then PC bytes are the Game Boy's poll replies and Game Boy bytes go to the PC; ends when the PC closes the port. Printer mode stays the default.
- ROM `rom/sodax.gb` (ours): splash with the official SODAX lockup (icon-project/sodax-sdks docs/sodax-lockup-light.svg, MIT; brand rule: don't recreate the logo), bold 8x16 price, change + range tabs, 128x48 chart (shaded area, dotted grid, 2 px line, end marker), solver quote box, page dots, inverted bars. Updates copy a VRAM slice per VBlank (no blank flash). Font: generated 5x7, bold without closing 1 px gaps (fixed "W" looking like "V").
- Emulator tests (PyBoy): splash; live BTC/SODA payloads injected into WRAM render correctly; a test build feeds a live ETH frame (with junk before it) through `ParseByte`: renders. **That test found a real bug**: the length check rejected frames >= 256 bytes (ours are 278); fixed. Also fixed: big price top half copied with source/destination swapped.
- `tools/sodax-bridge.mjs` + `SODAX Bridge.command`; `--dry` prints all 9 live screens. Docs: docs/SODAX.md.

## 2026-10-16 SODAX on real hardware: works
- First tries: ROM stuck on the splash / "LOADING". Bridge stats showed ~1000 bytes/s arriving from the Game Boy and screens being sent. A5 test (bridge mode + printtest.gb): rows full of A5, so bridge mode and Pico-to-GB work.
- Debug build with link counters on row 1, freshly copied to the EverDrive: screens render, buttons switch coin/range/refresh (Hazy: "all works"). Root cause of the earlier failure not confirmed; most likely the EverDrive had a ROM from before the length-check fix.
- SODAX API: one HTTP 520 and some timeouts seen; bridge now retries with timeouts and reuses the last good data.
- Footer "A:NEW" renamed "A:LOAD" (Hazy didn't know what NEW meant). Debug row only in -D DEBUG builds.

## 2026-10-16 v0.2.0 release
- README: SODAX section with screenshots (re-rendered with the A:LOAD footer), troubleshooting row, layout, roadmap (general PC link done).
- Release v0.2.0: gb_link_usb.uf2 (printer + bridge mode), sodax.gb, printtest.gb, linktest.gb, SHA256SUMS. Clean builds; host tests and decoder tests pass.

## 2026-10-16 Web page on GitHub Pages
- `.github/workflows/pages.yml` runs the decoder tests and publishes web/ + the wiring drawing to https://hazy2go.github.io/gb-link-usb/ on push. First run: success; live page checked in headless Chrome (demo decodes: 12 packets). README points to the live page. Correction: the WiFi cart repo is at ~/wifi-game-boy-cartridge (CLAUDE.md said ~/projects/...).

## 2026-10-16 PCB rev A: decisions and parts
- Hazy chose: built-in link cable (one cut cable makes two boards), proper 5 V buffers (74LVC1T45 on USB 5 V, Ioff: safe in any power order).
- Base: Raspberry Pi RP2350A minimal design R4 (MIT), copied to hw/reference/. Keeps the RP2350 switcher/crystal/flash layout.
- JLC stock checked (hw/tools/jlc_search.py): RP2350A 6,312; 74LVC1T45 348k; USB-C TYPE-C-31-M-12 380k; USBLC6 31k; TPD4E05U06 243k; crystal C9002 basic. W25Q16JVUXIQ out of stock (2): using W25Q128JVSIQ C97521 (basic part, 67k).
- New pin: GP3 = SCK direction for the translator. Spec in docs/PCB.md.

## 2026-10-16 PCB rev A: schematic done
- `hw/tools/add_sheet.py` rebuilds everything: `edit_root.py` turns the RPi RP2350A minimal schematic into our root (removes micro-USB J1, headers J2/J3, SWD J4, and R9 = optional GPIO0-to-flash link, since GPIO0 is our SCK; strips dangling wires/labels/power symbols; unused GPIOs get no-connect flags; GPIO0-3, GPIO25, USB_D+/-, SWCLK, SWD become global labels). `gen_sheet.py` (adapted from the WiFi cart) generates the Link sheet from `hw/rev-a/link.json`: USB-C + CC 5.1k + USBLC6, 3x 74LVC1T45 (VCCB = VBUS), 33R series, 100k idle pull-ups, TPD4E05U06 ESD, cable pads (shield, SCK, GND, SOUT, SIN), LED, SWD test pads.
- Fix in the copied `sexp.py`: it decoded `\n` in strings into real newlines and KiCad 10 refused to load the file; strings are now kept raw (round trip checked).
- Checks: ERC identical to the untouched RPi design (2 off-grid warnings, U2 power-output pair, 2 regulator pins; all in the original). Netlist check: GPIO0-3, GPIO25, USB D+/D-, LINK_SCK/SO/SI, SWCLK/SWD each connect exactly the intended pins; VBUS reaches U2 and all VCCB pins.
- Parts swapped for basic/in-stock: green LED C72043 out of stock -> KT-0805G C2297; 47R (extended) -> 33R C25105.
- Next: PCB layout (keep the RPi core layout, add our parts, shrink the board).
- Correction: the first Link sheet reused reference numbers of the RPi core (C10-C15, R10/R11); KiCad ERC did not flag it. Renumbered all Link parts to 101+ (J101 USB-C, J102 cable pads, U101 USBLC6, U102-U104 translators, U105 ESD, ...). Netlist now: 67 components, no duplicates (checked), nets re-verified. Duplicate-reference check added to the checks list.

## 2026-10-16 PCB rev A: board built and routed, DRC 0 errors
- Pipeline (all scripted, reproducible from the untouched RPi board): `hw/tools/pcb_build.py` -> `pcb_route.py hand` -> `pcb_gnd.py` -> `pcb_route.py` (Freerouting 2.5.0, OpenJDK 27 from brew).
- pcb_build: removes connectors/R9/mounting holes; strips dangling copper (fixed two bugs: T-junction ends counted as loose; a trace running *through* SW2's pads lost RUN -> now trimmed back to the last pad); removes reference copper under new parts or outside the outline; renames nets; adds Link footprints; clips the two full-board pours to the new outline **keeping RPi's shape** (their +3V3 pour has deliberate cut-outs and is held together by columns at the board edges, which our narrower board cut off -> added a 1 mm +3V3 column on our right edge; a plain rectangle had flooded the inner area); syncs net classes before filling.
- KiCad Python quirk: after removing items, the bindings return unwrapped objects for the rest of the process. Every removal step runs in its own process.
- Freerouting setup: it sees a copy without the two big pours (as planes they block almost everything), the small core pours kept (it won't cross them; as no-go areas they made the core's own copper count as violations), no-go areas for the right +3V3 column, the bottom layer under the core (keeps the GND pour whole) and the +3V3 feed right of USB D+/D-. Core +3V3/VBUS pins hidden except one tap each (C15, C1); GND done by pcb_gnd.py (every Link GND pad gets its own via). Zero-length segments removed (Freerouting choked on them).
- Placement: link corner left of the crystal. Pins changed for short routes: **GP12 SCK, GP13 data from GB, GP14 data to GB, GP11 direction** (GP15 free: a core +3V3 trace under pad 20 blocks it); LED on **GP21** (GP25 is in line with C14). Hand routes for the nested GPIO fan, the direction line (down the gap between U102's pin rows), U104 DIR to VCCA, the ESD chip's two GND pins. SWD test pads dropped (flashing is over USB; SWD stays on the chip).
- Board: 34.2 x 62.2 mm, 2 layers. DRC: 0 errors; warnings left: silkscreen (designators), RPI_COMPILED library path, J102 BOM flag/LCSC field. Schematic ERC = RPi baseline, net checks pass, 60 components.
- Next: clean the warnings, then fab outputs + JLC checks.

## 2026-10-16 PCB rev A: warnings cleaned, DRC 0 errors / 0 unconnected
- **ESD chip routing**: TPD4E05U06 NC pins 10/9/7 now tied to the line on the opposite pad (1/2/4). TI datasheet pin table: "Not connected; Used for optional straight-through routing. Can be left floating or grounded." Freerouting kept failing LINK_SO (pad 2 boxed in between SCK and GND); now each line runs straight across the chip.
- **GND pour island**: RPi's bottom GND pour stopped above our cable pads; a LINK_SI trace along that edge sealed off a pocket (C104 GND via + J102 GND pad). The bottom GND pour now runs to the board edge.
- **Router retries**: Freerouting is not deterministic. `pcb_route.py` now restarts from the same pre-route board up to 6 times and keeps the first result with 0 unconnected/0 DRC errors (kicad-cli DRC after each try).
- **Silkscreen**: the LCSC field was printed on silk (most of the 150 silk warnings). LCSC/Datasheet/Description fields hidden on the fab layer, designators moved to the fab layer, labels only: cable pads SH/SCK/GND/SO/SI (narrow font to fit between the strain-relief lines), "gb-link-usb rev A", "LED".
- **Libraries**: `hw/tools/extract_libs.py` writes the RPi symbols and footprints next to the project (RPI_DB, RPI - Power, RPI - BOM Directives, RPI_COMPILED.pretty) plus sym-lib-table/fp-lib-table. Footprints are copied as text from the reference board (pcbnew's library API fails from a script); they need a `(version ...)` header or KiCad parses arcs in the old format.
- Result: DRC 0 errors, 0 unconnected, schematic parity 0. Warnings left: 25 lib_footprint_mismatch (RPi core footprints differ slightly per instance from the one copy in the library; same kind as on the WiFi cart). ERC = RPi baseline. Renders in `hw/rev-a/img/`.
- Next: fab outputs + JLC checks (BOM with LCSC, CPL rotations, stock, pin audit).
- Correction (same day): the 25 lib_footprint_mismatch warnings were our extraction bug, not RPi instance differences. A board file stores pad/text angles with the footprint's rotation included, and pads carry nets; even the untouched RPi board showed the mismatch against our copies. `extract_libs.py` now puts each footprint at 0 deg/front/origin in a temp board first and strips nets. **DRC now: 0 errors, 0 warnings, 0 unconnected, parity 0.**

## 2026-10-16 PCB rev A: JLC order files (not ordered)
- RPi core parts got LCSC numbers (`edit_root.py`), checked live on JLC. Kept Raspberry Pi's own picks where their guide asks for them: **ABM8-272-T3** crystal C20625731 ("Pico 2 has been specifically tuned for the ABM8-272-T3"; the basic X322512MSB4SI is 20 pF / 80 ohm, so dropped) and the polarity-marked **AOTA-B201610S3R3-101-T** inductor C42411119 (RP2350 datasheet: "The inductor must be marked for polarity"). Buttons: Wurth 434133025816 has 0 stock -> Alps SKRPABE010 C115360 (same 4.2x3.2 J-lead footprint, 1.6 N; CPL pad fit 0.025 mm). Passives: basic parts (100n C1525, 15p C1548, 4.7u C23733, 10u C15850, 1k C11702, 0R C17168); 27R C25100 (extended, RPi's USB value kept).
- **Hold point: L1 stock is 4 at JLC** (5 boards need 10 with attrition). In ORDER.md with options.
- Board: core footprints now carry value + LCSC from the schematic (parity clean). J102 GND pads solid to the pour (a trace between the pads left one thermal spoke: DRC error "thermal relief incomplete").
- `hw/tools/make_fab.sh`: Gerbers + drill (WiFi cart settings), `make_bom.py`, `make_cpl.py`, `pin_audit.py` (adapted from the WiFi cart). Results: BOM 25 lines / 55 parts / 10 extended, 1 FAIL = L1 stock. CPL: all 55 parts matched against JLC's footprints, none to review by the tool.
- **Pin audit catch: the LED.** JLC's KT-0805G symbol has pin 1 = A, KiCad's LED has pad 1 = K. Matching pads by number put it backwards (the CPL said rot +180). `make_cpl.py` now renumbers JLC's pads for C2297 (PAD_MAP); D101 now rot 0 with A on A. Other LOOK lines are naming only (checked by hand: USB-C combined pins, NCP1117 1 GND/2 OUT/3 IN/tab OUT, crystal 2/4 GND, LVC1T45 pin 3 = A).
- L1 orientation: JLC's footprint polarity marker (EasyEDA polarity layer) is at pad 1, like RPi's silk dot, but its silk dot is at pad 2 (verify in JLC's preview). Hold point in ORDER.md.
- DRC still 0 errors / 0 warnings / parity 0. Files: `hw/rev-a/fab/`.

## 2026-10-16 Firmware: pin map per board
- `firmware/src/board.h` + cmake `-DGBLINK_BOARD=breadboard|revA` (default breadboard, unchanged pins GP0/1/2, LED via the CYW43).
- revA: GP12 SCK, GP13 data in, GP14 data out, GP11 = U102 DIR driven low at boot (Game Boy drives SCK; R103 already pulls it low before the firmware runs), LED on GP21. Builds as PICO_BOARD=pico2 (same RP2350A, same ABM8-272-T3 crystal; flash setting 4 MB on a 16 MB chip is fine) without the CYW43 library.
- Both builds compile with no warnings (Arm GCC 15.3, SDK 2.3.1). Not tested on hardware: the Pico was not connected; rev A can only be tested once boards exist (verify).
