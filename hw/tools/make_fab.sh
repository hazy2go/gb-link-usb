#!/bin/sh
# JLC order files for rev A into hw/rev-a/fab: Gerbers + drill (zip), BOM + check, CPL + check, pin audit.
# Run from anywhere after the board pipeline (pcb_build -> pcb_route hand -> pcb_gnd -> pcb_route) and a clean DRC.
set -e
cd "$(dirname "$0")/../rev-a"
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
N=gb-link-usb
rm -rf fab/gerbers && mkdir -p fab/gerbers
# same settings as the WiFi cart: Protel names, no X2, soldermask subtracted from silk, Excellon mm absolute PTH/NPTH
kicad-cli pcb export gerbers --no-x2 --subtract-soldermask --check-zones \
  --layers F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts -o fab/gerbers/ $N.kicad_pcb
kicad-cli pcb export drill --format excellon --drill-origin absolute --excellon-units mm --excellon-separate-th \
  -o fab/gerbers/ $N.kicad_pcb
rm -f fab/$N-revA-gerbers.zip && (cd fab/gerbers && zip -q ../$N-revA-gerbers.zip *)
python3 ../tools/make_bom.py $N.kicad_sch fab --boards 2   # Hazy: assemble 2 boards (2026-10-16) || true
kicad-cli sch export netlist --format kicadxml -o fab/netlist.xml $N.kicad_sch
$KPY ../tools/make_cpl.py $N.kicad_pcb fab/$N-BOM-JLC.csv fab/$N-CPL-JLC.csv --report fab/cpl_check.txt
python3 ../tools/pin_audit.py fab/netlist.xml fab/$N-BOM-JLC.csv > fab/pin_audit.txt
rm fab/netlist.xml
ls fab
