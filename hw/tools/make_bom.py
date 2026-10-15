#!/usr/bin/env python3
"""JLC assembly BOM (adapted from the WiFi cart, ~/wifi-game-boy-cartridge/hw/rev-b/tools) from the schematic (kicad-cli export) + checks against JLC's live parts library.

- LCSC numbers come from the schematic's LCSC field (Link parts: link.json; RPi core: edit_root.py).
- Parts excluded from the BOM in the schematic (J102 cable pads, RPi's BOM directive symbols) are left out.
- DNP parts are left out of the BOM (and the CPL).
- Every part is looked up live: must exist, package must match the footprint size (0402/0603/...), stock must
  cover BOARDS x qty + 10 % attrition (min +5). Basic vs extended is reported (extended = feeder fee per part).
Writes fab/<name>-BOM-JLC.csv and fab/bom_check.txt. Exit 1 on any FAIL.
Usage: make_bom.py SCH OUTDIR [--boards 5]"""
import csv, json, os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jlc_parts import lookup

MUL = {'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'µ': 1e-6, 'm': 1e-3, 'k': 1e3, 'K': 1e3, 'M': 1e6, '': 1, 'R': 1}


def value_of(v, refs):
    """Schematic value of an R or C as a number (F or ohm): 100nF, 100n, 4.7u, 5k1, 27R, 10k 1%, 0R."""
    kind = refs.split(',')[0].rstrip('0123456789')
    if kind not in ('R', 'C'):
        return None
    m = re.match(r'\s*(\d+)(?:([.,]\d+)|([pnuµmkKMR])(\d+))?\s*([pnuµmkKMR]?)', v)
    if not m:
        return None
    if m.group(3):                                   # 5k1 / 4u7 style
        return float(f"{m.group(1)}.{m.group(4)}") * MUL[m.group(3)]
    return float(m.group(1) + (m.group(2) or '').replace(',', '.')) * MUL[m.group(5)]


def desc_value(d, refs):
    kind = refs.split(',')[0].rstrip('0123456789')
    pat = r'(\d+(?:\.\d+)?)\s*([pnuµmkM]?)F\b' if kind == 'C' else r'(\d+(?:\.\d+)?)\s*([mkM]?)Ω' if kind == 'R' else None
    m = re.search(pat, d) if pat else None
    return float(m.group(1)) * MUL[m.group(2)] if m else None


sch, out = sys.argv[1], sys.argv[2]
boards = int(sys.argv[sys.argv.index('--boards') + 1]) if '--boards' in sys.argv else 5
tmp = tempfile.mktemp(suffix='.csv')
subprocess.run(['kicad-cli', 'sch', 'export', 'bom', '--fields', 'Reference,Value,Footprint,LCSC,${QUANTITY},${DNP}',
                '--labels', 'Ref,Value,Footprint,LCSC,Qty,DNP', '--group-by', 'Value,Footprint,LCSC,${DNP}',
                '--ref-range-delimiter', '', '-o', tmp, sch], check=True, capture_output=True)
rows = list(csv.DictReader(open(tmp)))
os.makedirs(out, exist_ok=True)
lines, fails, ext, dnp, bom = [], [], [], [], []
for r in rows:
    if r['DNP'].strip():
        dnp.append(r['Ref']); continue
    lc = r['LCSC'].strip()
    if not lc:
        fails.append(f"NO LCSC   {r['Ref']} {r['Value']} {r['Footprint']}"); continue
    info = lookup(lc)
    need = int(r['Qty']) * boards
    need = need + max(5, int(need * 0.1))
    m = re.search(r'_(\d{4})_\d{4}Metric', r['Footprint'])
    pkg_ok = (not m) or (info['package'] or '').startswith(m.group(1))
    status = []
    if info['library'] is None:
        status.append('NOT IN JLC LIBRARY')
    if not pkg_ok:
        status.append(f"PACKAGE {info['package']} vs footprint {m.group(1)}")
    vv, dv = value_of(r['Value'], r['Ref']), desc_value(info['desc'] or '', r['Ref'])
    if vv is not None and dv is not None and abs(vv - dv) > 1e-6 * max(vv, dv, 1e-12):
        status.append(f"VALUE {r['Value']} vs part {info['desc'][:40]}")
    if info['stock'] is not None and info['stock'] < need:
        status.append(f"STOCK {info['stock']} < {need}")
    if info['library'] == 'expand':
        ext.append(lc)
    line = f"{'FAIL' if status else 'ok  '} {lc:9} {str(info['library']):6} stock {str(info['stock']):>9} need {need:>4}  {r['Value'][:18]:18} {r['Ref'][:40]:40} {str(info['mpn'])[:22]:22} {'; '.join(status)}"
    lines.append(line)
    if status:
        fails.append(line)
    fp = r['Footprint'].split(':')[-1]
    bom.append([r['Value'], r['Ref'], fp, lc])
name = os.path.splitext(os.path.basename(sch))[0]
with open(os.path.join(out, f'{name}-BOM-JLC.csv'), 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
    for b in bom:
        w.writerow(b)
rep = [f'BOM check for {boards} boards: {len(bom)} lines, {sum(len(b[1].split(",")) for b in bom)} placed parts, '
       f'{len(set(ext))} extended parts (feeder fee each), DNP: {", ".join(dnp) or "-"}', ''] + lines + ['', 'RESULT: ' + ('ALL PASS' if not fails else f'{len(fails)} FAIL')]
open(os.path.join(out, 'bom_check.txt'), 'w').write('\n'.join(rep) + '\n')
print('\n'.join(rep))
sys.exit(1 if fails else 0)
