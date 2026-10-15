"""Schematic geometry for KiCad .kicad_sch files: symbol pin positions in sheet coordinates."""
import math
from sexp import find, first


def lib_pins(libsym):
    """[(number, unit, x, y)] in library coordinates (y up) for an embedded lib_symbols entry."""
    out = []
    for sub in find(libsym, 'symbol'):
        unit = int(str(sub[1]).rsplit('_', 2)[-2])
        for p in find(sub, 'pin'):
            at = first(p, 'at')
            out.append((str(first(p, 'number')[1]), unit, float(at[1]), float(at[2])))
    return out


def place(inst, x, y):
    """Library point -> sheet point for a placed symbol (mirror, then rotate, then y flip)."""
    at = first(inst, 'at')
    sx, sy, rot = float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0
    m = first(inst, 'mirror')
    if m:
        if m[1] == 'x': y = -y
        if m[1] == 'y': x = -x
    r = math.radians(rot)
    xr = x * math.cos(r) - y * math.sin(r)
    yr = x * math.sin(r) + y * math.cos(r)
    return (round(sx + xr, 3), round(sy - yr, 3))


def symbol_pins(sch):
    """{(ref, pin): (x, y)} for every placed symbol in a parsed schematic."""
    libs = {str(s[1]): s for s in find(first(sch, 'lib_symbols'), 'symbol')}
    res = {}
    for inst in find(sch, 'symbol'):
        lib_id = str(first(inst, 'lib_id')[1])
        unit = int(first(inst, 'unit')[1]) if first(inst, 'unit') else 1
        ref = next((str(p[2]) for p in find(inst, 'property') if p[1] == 'Reference'), '?')
        for num, u, x, y in lib_pins(libs[lib_id]):
            if u in (0, unit):
                res[(ref, num)] = place(inst, x, y)
    return res
