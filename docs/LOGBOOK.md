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
- Hazy cut one DMG-04. Inner wires: **orange, red, blue, green** (4 wires). Shield / bare drain wire: not reported yet (ask).
- Colors are not standardised, so the pin mapping is still unknown. Likely set for 4 wires: SCK, SOUT, SIN, GND (VCC and SD often not carried by link cables) (verify by continuity).
- Prior art (mofosyne README) gives the cable-end pinout (1 5V, 2 SOUT, 3 SIN, 4 SD, 5 SCK, 6 GND) and confirms wire colours are not a reliable guide; data lines can be swapped in software, so only GND and SCK must be identified for sure. Added to PROTOCOL.md.
