#!/usr/bin/env python3
"""Top-side part heights for the case (hw/case). Adapted from the WiFi cart's height_check.py.

Reads every footprint's 3D model (STEP points in mm, VRML points in KiCad's 0.1 inch units), applies the model
scale / rotation / offset, and reports the highest point above the board. Datasheet heights win over models
(OVERRIDE); parts without a model use NO_MODEL. Exit 1 if a part is missing a height or exceeds BUDGET (the
case's inner clearance above the board).
Run with KiCad's Python: height_check.py hw/rev-a/gb-link-usb.kicad_pcb [--json out.json]
"""
import math, os, re, sys
import pcbnew

BUDGET = 4.0        # mm: case inner clearance above the board top (hw/case/case.scad TOP_CLEAR)
# parts without a usable model (RPi's are embedded in their board, HRO's STEP is not shipped with KiCad 10):
# the larger of RPi's schematic "size" field and the JLC/EasyEDA 3D model of the LCSC part (2026-10-16)
NO_MODEL = {
    'U1': (0.86, 'RP2350A QFN-60: RPi 0.85 mm, JLC model C42411118 0.86 mm'),
    'U2': (1.80, 'NCP1117 SOT-223: RPi 1.8 mm, JLC model C26537 1.7 mm'),
    'U3': (2.00, 'W25Q128 SOIC-8 208 mil: RPi 1.95 mm, JLC model C97521 2.0 mm'),
    'SW1': (2.50, 'SKRPABE010: 2.5 mm (JLC model C115360, part data)'),
    'SW2': (2.50, 'SKRPABE010: 2.5 mm (JLC model C115360, part data)'),
    'L1': (1.00, 'AOTA-B201610: RPi 1.0 mm, JLC model 0.95 mm'),
    'X1': (0.80, 'ABM8-272-T3: RPi 0.8 mm, JLC model 0.7 mm'),
    'J101': (3.25, 'TYPE-C-31-M-12: JLC model C165948 top at 3.25 mm above the board (verify on the HRO drawing)'),
    'J102': (0.05, 'cable pads only; the cable itself is handled by the case'),
}
NO_MODEL.update({r: (1.30, '10u 0805: RPi 1.25 mm, JLC model C15850 1.3 mm') for r in ('C1', 'C5', 'C19')})
NO_MODEL.update({f'C{n}': (0.50, '0402 MLCC: RPi 0.5 mm') for n in (2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18)})
NO_MODEL.update({f'R{n}': (0.35, '0402 resistor: RPi 0.35 mm') for n in (1, 2, 3, 4, 6, 7, 8, 10)})
OVERRIDE = {}
EXCEPT = {}
ENV = {}


def resolve(path):
    for k, v in ENV.items():
        path = path.replace('${%s}' % k, v)
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), path)
    return path


def points(path):
    """model points in mm (model coordinates)."""
    base, ext = os.path.splitext(path)
    wrl = base + '.wrl'
    if not os.path.exists(path):     # KiCad 10 ships STEP only: Croco's .wrl references resolve to the .step
        for e in ('.step', '.STEP', '.stp'):
            if os.path.exists(base + e):
                path, ext = base + e, e
                break
    if os.path.exists(wrl):          # KiCad ships VRML next to STEP; VRML unit = 0.1 inch
        txt = open(wrl, errors='ignore').read()
        out = []
        for blk in re.findall(r'point\s*\[([^\]]*)\]', txt):
            nums = [float(x) for x in re.findall(r'-?\d+\.?\d*(?:[eE][-+]?\d+)?', blk)]
            out += [(nums[i] * 2.54, nums[i + 1] * 2.54, nums[i + 2] * 2.54) for i in range(0, len(nums) - 2, 3)]
        if out:
            return out
    if os.path.exists(path) and ext.lower() in ('.step', '.stp'):
        txt = open(path, errors='ignore').read()
        out = []
        for m in re.finditer(r"CARTESIAN_POINT\s*\(\s*'[^']*'\s*,\s*\(([^)]*)\)", txt):
            v = [float(x) for x in m.group(1).split(',')]
            if len(v) == 3:
                out.append(tuple(v))
        return out
    return None


def rot(p, rx, ry, rz):
    x, y, z = p
    for ang, ax in ((rx, 'x'), (ry, 'y'), (rz, 'z')):
        a = math.radians(ang); c, s = math.cos(a), math.sin(a)
        if ax == 'x':
            y, z = y * c - z * s, y * s + z * c
        elif ax == 'y':
            x, z = x * c + z * s, -x * s + z * c
        else:
            x, y = x * c - y * s, x * s + y * c
    return x, y, z


def main():
    kd = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/3dmodels'
    for k in ('KICAD10_3DMODEL_DIR', 'KICAD9_3DMODEL_DIR', 'KICAD8_3DMODEL_DIR', 'KICAD7_3DMODEL_DIR',
              'KICAD6_3DMODEL_DIR', 'KISYS3DMOD'):
        ENV[k] = os.environ.get(k, kd)
    ENV['KIPRJMOD'] = os.path.dirname(os.path.abspath(sys.argv[1]))
    b = pcbnew.LoadBoard(sys.argv[1])
    rows, fails = [], []
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if fp.GetLayer() != pcbnew.F_Cu or fp.IsDNP() or not ref.strip():
            continue
        h, src = None, ''
        for m in fp.Models():
            if not m.m_Show:
                continue
            pts = points(resolve(m.m_Filename))
            if not pts:
                continue
            sc, ro, of = m.m_Scale, m.m_Rotation, m.m_Offset
            zs = [rot((x * sc.x, y * sc.y, z * sc.z), -ro.x, -ro.y, -ro.z)[2] + of.z for x, y, z in pts]
            top = max(zs)
            h = top if h is None else max(h, top)
            src = os.path.basename(m.m_Filename)
        if ref in OVERRIDE:
            h, src = OVERRIDE[ref][0], 'datasheet: ' + OVERRIDE[ref][1]
        if h is None:
            if ref in NO_MODEL:
                h, src = NO_MODEL[ref][0], 'datasheet: ' + NO_MODEL[ref][1]
            else:
                fails.append(f'{ref}: no 3D model and no datasheet height'); continue
        d = 0.0
        rows.append((h, ref, str(fp.GetFPID().GetLibItemName()), d, src))
    rows.sort(reverse=True)
    print(f'{len(rows)} top-side parts; budget {BUDGET} mm')
    for h, ref, name, d, src in rows:
        if h > BUDGET:
            fails.append(f'{ref} {h:.2f} mm > {BUDGET} mm')
        print(f'  {h:5.2f} mm  {ref:6} {name[:40]:40} {src[:60]}')
    if '--json' in sys.argv:
        import json
        out = {ref: dict(h=round(h, 3), x=b.FindFootprintByReference(ref).GetPosition().x / 1e6,
                         y=b.FindFootprintByReference(ref).GetPosition().y / 1e6) for h, ref, *_ in rows}
        json.dump(out, open(sys.argv[sys.argv.index('--json') + 1], 'w'), indent=1)
    for f in fails:
        print('FAIL', f)
    print('RESULT:', 'PASS' if not fails else 'FAIL')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
