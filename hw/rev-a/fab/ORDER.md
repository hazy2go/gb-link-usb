# JLCPCB order: gb-link-usb rev A

**Not ordered. Ordering is Hazy's job.** Hold points first.

## Hold points
1. **L1 inductor stock.** Raspberry Pi asks for exactly the Abracon AOTA-B201610S3R3-101-T (polarity-marked 3.3 uH; RP2350 datasheet: "The inductor must be marked for polarity ... we recommend the AOTA-B201610S3R3-101-T"; Hardware design with RP2350: the regulator misbehaves with the inductor the wrong way round). JLC has **4** (C42411119), 5 boards need 5 plus attrition. Options: order 2-3 boards now; JLC global sourcing / parts pre-order; or wait for stock. No substitute picked on purpose: unmarked 2016 inductors sit randomly oriented on the reel.
2. **L1 orientation in the preview.** JLC's footprint has its polarity marker (EasyEDA polarity layer) at pad 1, the same side as Raspberry Pi's silk dot, so the CPL keeps pad 1 on pad 1. JLC's footprint also has a silk dot at pad 2, which contradicts that (verify): in the placement preview the part's dot must sit on the board's silk dot.
3. **Cable.** Not part of the order: a link cable cut in half, soldered to the five pads (SH, SCK, GND, SO, SI; colours in LOGBOOK 2026-10-15). Wire gauge vs the 0.5 mm holes (verify on the cable).

## Files (this folder)
| file | upload as |
|---|---|
| `gb-link-usb-revA-gerbers.zip` | Gerber file (9 layers + PTH/NPTH Excellon drill, mm, absolute origin) |
| `gb-link-usb-BOM-JLC.csv` | BOM (Comment, Designator, Footprint, LCSC Part #); R1 is DNP (RPi's optional part), the cable pads J102 are not a part |
| `gb-link-usb-CPL-JLC.csv` | CPL (Designator, Mid X, Mid Y, Layer, Rotation); all 57 parts on top |
| `bom_check.txt` | live JLC check: part exists, package matches footprint, value matches, stock for 5 boards |
| `cpl_check.txt` | rotation/offset per part, derived pad by pad from the footprint JLC places |
| `pin_audit.txt` | every pin vs JLC's symbol for the part; the LOOK lines are naming only (checked by hand, LOGBOOK), except the LED, handled in the CPL |

Regenerate everything: `hw/tools/make_fab.sh` (after the board pipeline and a clean DRC).

## PCB options
| option | value | why |
|---|---|---|
| Layers | 2 | |
| Size | 34.25 x 62.25 mm | from the board outline |
| Qty | 5 | |
| Thickness | 1.6 mm | default; nothing slots into anything |
| Min via hole / diameter | 0.25 / 0.6 mm | RPi's core layout uses 0.25 mm vias, also inside the RP2350 exposed pad (verify JLC's 2-layer minimum at upload) |
| Min track / clearance | 0.15 / 0.15 mm | |
| Surface finish | ENIG preferred (flat pads for the 0.4 mm QFN), lead-free HASL possible | |
| Remove order number | Yes (specify a location) or accept it on the back | |

## Assembly (PCBA)
| option | value |
|---|---|
| PCBA type | Standard or Economic (verify which JLC offers for QFN-60 0.4 mm) |
| Side | Top |
| Qty | 5 (or fewer, see hold point 1) |
| Confirm parts placement | **Yes** |

Also checked before this order: routing tidy-up, part heights, link-line simulation (`sim/link`), independent Gerber render (`hw/rev-a/img/gerber_render.png`). See `hw/README.md`.

## Check in JLC's placement preview
- U1 RP2350A pin 1, U3 flash pin 1, U101-U105 (SOT-23-6, USON-10) pin 1
- D101 LED: cathode on the GND pad (CPL renumbers JLC's A/K pads, LOGBOOK)
- L1 dot (hold point 2), X1 crystal, U2 LDO tab
- J101 USB-C sits flush with the board edge (CPL shifts it 1.57 mm to JLC's origin)

## Parts summary
57 placed parts, 26 BOM lines, 10 extended parts (feeder fee each). Changes vs Raspberry Pi's minimal design: crystal ABM8-272-T3 (their pick, kept); buttons Alps SKRPABE010 (Wurth 434133025816 out of stock, same 4.2 x 3.2 mm J-lead footprint and 1.6 N).
