#!/usr/bin/env python3
"""Put Raspberry Pi's footprints and symbols into project libraries so KiCad finds them.

The reference design ships with its footprints embedded in the board and its symbols embedded in the
schematic, but no library files. This writes hw/rev-a/RPI_COMPILED.pretty (from the reference board),
one .kicad_sym per RPi symbol library (from the root schematic) and the project fp-lib-table and
sym-lib-table. Run with KiCad's Python.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sexp import parse, dump, find, first, Str
import pcb_build

REV = pcb_build.REV
lib = os.path.join(REV, 'RPI_COMPILED.pretty')
os.makedirs(lib, exist_ok=True)
# footprints from the reference board. A board file stores pad and text angles with the footprint's own
# rotation included, so each footprint is first put at 0 deg, front side, origin, no nets (pcbnew, temp board)
# and then written out as text (pcbnew's library API is not usable from a script here).
import pcbnew, tempfile
ref = pcbnew.LoadBoard(pcb_build.REF_PCB)
tmp = pcbnew.CreateEmptyBoard()
names = set()
for fp in ref.GetFootprints():
    nick, name = fp.GetFPID().GetUniStringLibId().split(':', 1)
    if nick != 'RPI_COMPILED' or name in names:
        continue
    names.add(name)
    c = pcbnew.FOOTPRINT(fp)
    if c.IsFlipped():
        c.Flip(c.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    c.SetOrientationDegrees(0)
    c.SetPosition(pcbnew.VECTOR2I(0, 0))
    tmp.Add(c)
tmp_path = os.path.join(tempfile.mkdtemp(), 'fp.kicad_pcb')
tmp.Save(tmp_path)
DROP = {'at', 'uuid', 'path', 'sheetname', 'sheetfile', 'locked', 'net'}


def strip(x):
    """Drop board-only data (placement, uuids, nets) at any depth, but keep the 'at' of pads/texts."""
    if not isinstance(x, list):
        return x
    return [strip(y) for y in x if not (isinstance(y, list) and y and y[0] in DROP - {'at'})]


for fp in find(parse(open(tmp_path).read()), 'footprint'):
    name = str(fp[1]).split(':', 1)[1]
    body = [strip(x) for x in fp[2:] if not (isinstance(x, list) and x and x[0] in DROP)]
    out = ['footprint', Str(name), ['version', 20260206], ['generator', Str('extract_libs')]] + body
    open(os.path.join(lib, name + '.kicad_mod'), 'w').write(dump(out) + '\n')
print('footprints:', len(names))

sch = parse(open(os.path.join(REV, 'gb-link-usb.kicad_sch')).read())
libs = {}
for sym in find(first(sch, 'lib_symbols'), 'symbol'):
    nick, name = str(sym[1]).split(':', 1)
    if nick.startswith('RPI'):
        s = list(sym); s[1] = Str(name)
        libs.setdefault(nick, []).append(s)
for nick, syms in libs.items():
    out = ['kicad_symbol_lib', ['version', 20241209], ['generator', Str('gb-link-usb')]] + syms
    open(os.path.join(REV, nick + '.kicad_sym'), 'w').write(dump(out) + '\n')
print('symbol libs:', {k: len(v) for k, v in libs.items()})

fp_table = '(fp_lib_table\n\t(version 7)\n\t(lib (name "RPI_COMPILED")(type "KiCad")(uri "${KIPRJMOD}/RPI_COMPILED.pretty")(options "")(descr "Raspberry Pi RP2350A minimal design footprints (MIT)"))\n)\n'
open(os.path.join(REV, 'fp-lib-table'), 'w').write(fp_table)
rows = ''.join(f'\t(lib (name "{n}")(type "KiCad")(uri "${{KIPRJMOD}}/{n}.kicad_sym")(options "")(descr "Raspberry Pi minimal design symbols (MIT)"))\n' for n in sorted(libs))
open(os.path.join(REV, 'sym-lib-table'), 'w').write('(sym_lib_table\n\t(version 7)\n' + rows + ')\n')
print('wrote fp-lib-table, sym-lib-table')
