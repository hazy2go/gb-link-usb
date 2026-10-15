#!/usr/bin/env python3
"""Turn Raspberry Pi's RP2350A minimal schematic into our root sheet (idempotent on the original file).

- removes the connectors we don't use (micro-USB J1, headers J2/J3, SWD J4), R9 (optional
  second-memory link on GPIO0, which is our SCK pin) and the mounting holes MH1-4
- removes wires and labels left dangling by that, repeatedly
- unused GPIOs: label + stub removed, a no-connect flag on the RP2350 pin
- signals used by the Link sheet become global labels
- JLC part numbers (LCSC field) for the RPi core parts (LOGBOOK 2026-10-16: JLC stock, RPi's part advice)
Usage: edit_root.py IN.kicad_sch OUT.kicad_sch
"""
import sys, uuid
from sexp import parse, dump, find, first, Str
from schgeom import symbol_pins

REMOVE = {'J1', 'J2', 'J3', 'J4', 'R9', 'MH1', 'MH2', 'MH3', 'MH4'}   # MH: mounting holes, the dongle has none
GLOBAL = {'GPIO11', 'GPIO12', 'GPIO13', 'GPIO14', 'GPIO21', 'USB_D+', 'USB_D-'}
# LCSC numbers for the core parts, checked on JLC 2026-10-16 (hw/tools/jlc_search.py). (value, lcsc)
# None keeps RPi's value. RPi's hardware design guide asks for exactly the ABM8-272-T3 crystal and the
# polarity-marked AOTA-B201610S3R3-101-T inductor; both kept.
LCSC = {
    'U1': (None, 'C42411118'), 'U2': (None, 'C26537'), 'U3': (None, 'C97521'),
    'X1': ('ABM8-272-T3', 'C20625731'), 'L1': ('AOTA-B201610S3R3-101-T', 'C42411119'),
    'SW1': ('SKRPABE010', 'C115360'), 'SW2': ('SKRPABE010', 'C115360'),   # Wurth 434133025816 out of stock; Alps J-lead 4.2x3.2, 1.6 N like the Wurth
    'C1': (None, 'C15850'), 'C5': (None, 'C15850'), 'C19': (None, 'C15850'),          # 10u 0805 25 V X5R
    'C3': (None, 'C1548'), 'C4': (None, 'C1548'),                                      # 15p 0402 C0G
    'C6': (None, 'C23733'), 'C7': (None, 'C23733'), 'C9': (None, 'C23733'),            # 4.7u 0402 6.3 V X5R
    'R1': (None, 'C25744'), 'R2': (None, 'C11702'), 'R4': (None, 'C11702'), 'R6': (None, 'C11702'),
    'R3': (None, 'C25105'), 'R7': (None, 'C25100'), 'R8': (None, 'C25100'), 'R10': (None, 'C17168'),
}
LCSC.update({f'C{n}': (None, 'C1525') for n in (2, 8, 10, 11, 12, 13, 14, 15, 16, 17, 18)})   # 100n 0402 X7R 16 V
NOT_PARTS = {'PCB1', 'SBREV1', 'VARIANT1'}    # RPi's BOM directive symbols: not placed parts
_NS = uuid.UUID('9b1c7e30-2f4a-4c8e-8d1b-6a5f0e2c3d47')
_n = [0]


def U():
    _n[0] += 1
    return Str(str(uuid.uuid5(_NS, f'nc/{_n[0]}')))


def P(xy):
    return (round(float(xy[1]), 3), round(float(xy[2]), 3))


def ref_of(inst):
    return next((str(p[2]) for p in find(inst, 'property') if p[1] == 'Reference'), '?')


def on_segment(p, a, b):
    (x, y), (x1, y1), (x2, y2) = p, a, b
    if abs((x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)) > 1e-6:
        return False
    return min(x1, x2) - 1e-6 <= x <= max(x1, x2) + 1e-6 and min(y1, y2) - 1e-6 <= y <= max(y1, y2) + 1e-6


def main(src, dst):
    sch = parse(open(src).read())
    pins_all = symbol_pins(sch)
    sch[:] = [c for c in sch if not (isinstance(c, list) and c[0] == 'symbol' and ref_of(c) in REMOVE)]
    pins = {k: v for k, v in pins_all.items() if k[0] not in REMOVE}
    pin_pts = set(pins.values())

    # iterative dangling cleanup
    while True:
        wires = [c for c in sch if isinstance(c, list) and c[0] == 'wire']
        segs = [(w, [P(xy) for xy in find(first(w, 'pts'), 'xy')]) for w in wires]
        labels = [c for c in sch if isinstance(c, list) and c[0] in ('label', 'global_label')]
        lab_pts = {P(first(l, 'at')) for l in labels}
        junc = {P(first(j, 'at')) for j in find(sch, 'junction')}
        nc = {P(first(j, 'at')) for j in find(sch, 'no_connect')}

        def connected(pt, me):
            if pt in pin_pts or pt in lab_pts or pt in junc or pt in nc:
                return True
            for w, (a, b) in segs:
                if w is not me and (pt in (a, b) or on_segment(pt, a, b)):
                    return True
            return False

        dead_w = [w for w, (a, b) in segs if not connected(a, w) or not connected(b, w)]
        dead_l = [l for l in labels if not any(on_segment(P(first(l, 'at')), a, b) for _w, (a, b) in segs)
                  and P(first(l, 'at')) not in pin_pts]
        # power symbols (GND, +3V3, ...) and no-connect flags that no longer touch anything
        ends = {p for _w, ab in segs for p in ab}
        dead_p = []
        for c in sch:
            if isinstance(c, list) and c[0] == 'symbol' and str(first(c, 'lib_id')[1]).startswith(('power:', 'RPI - Power:')):
                pt = pins.get((ref_of(c), '1'))
                if pt and not (pt in ends or any(on_segment(pt, a, b) for _w, (a, b) in segs)
                               or sum(1 for v in pin_pts if v == pt) > 1):
                    dead_p.append(c)
            if isinstance(c, list) and c[0] == 'no_connect':
                if P(first(c, 'at')) not in pin_pts:
                    dead_p.append(c)
        dead_l += dead_p
        if not dead_w and not dead_l:
            break
        dead = {id(x) for x in dead_w + dead_l}
        sch[:] = [c for c in sch if id(c) not in dead]

    # unused GPIO labels: label + stub -> no-connect on the pin; used ones -> global labels
    wires = [c for c in sch if isinstance(c, list) and c[0] == 'wire']
    out, removed = [], set()
    for c in sch:
        if isinstance(c, list) and c[0] == 'label':
            name = str(c[1])
            if name in GLOBAL:
                at = first(c, 'at')
                g = ['global_label', Str(name), ['shape', 'passive'], at, ['fields_autoplaced', 'yes'],
                     first(c, 'effects'), first(c, 'uuid'),
                     ['property', Str('Intersheetrefs'), Str('${INTERSHEET_REFS}'), at,
                      ['effects', ['font', ['size', 1.27, 1.27]], ['hide', 'yes']]]]
                out.append(g)
                continue
            if name.startswith('GPIO') or name in ('SWCLK', 'SWD'):    # unused: no pads on rev A
                lp = P(first(c, 'at'))
                for w in wires:
                    a, b = [P(xy) for xy in find(first(w, 'pts'), 'xy')]
                    if lp in (a, b):
                        other = b if lp == a else a
                        if other in pin_pts:
                            removed.add(id(w))
                            out.append(['no_connect', ['at', other[0], other[1]], ['uuid', U()]])
                            break
                else:
                    out.append(c)    # label not on a stub: keep
                continue
        out.append(c)
    sch[:] = [c for c in out if id(c) not in removed]

    for c in sch:
        if not (isinstance(c, list) and c[0] == 'symbol' and first(c, 'lib_id') is not None):
            continue
        ref = ref_of(c)
        if ref in NOT_PARTS:
            ib = first(c, 'in_bom')
            if ib is not None:
                ib[1] = 'no'
        if ref not in LCSC:
            continue
        value, lcsc = LCSC[ref]
        props = [p for p in find(c, 'property')]
        if value:
            next(p for p in props if p[1] == 'Value')[2] = Str(value)
        old = next((p for p in props if p[1] == 'LCSC'), None)
        if old is not None:
            old[2] = Str(lcsc)
        else:
            ds = next(p for p in props if p[1] == 'Datasheet')
            new = [x for x in ds]
            new[1], new[2] = Str('LCSC'), Str(lcsc)
            new = [x for x in new if not (isinstance(x, list) and x and x[0] == 'uuid')]
            c.insert(c.index(ds) + 1, new)
    open(dst, 'w').write(dump(sch) + '\n')
    print(f'removed {sorted(REMOVE)}; wrote {dst}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
