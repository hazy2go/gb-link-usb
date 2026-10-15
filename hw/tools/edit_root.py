#!/usr/bin/env python3
"""Turn Raspberry Pi's RP2350A minimal schematic into our root sheet (idempotent on the original file).

- removes the connectors we don't use (micro-USB J1, headers J2/J3, SWD J4) and R9 (optional
  second-memory link on GPIO0, which is our SCK pin)
- removes wires and labels left dangling by that, repeatedly
- unused GPIOs: label + stub removed, a no-connect flag on the RP2350 pin
- signals used by the Link sheet become global labels
Usage: edit_root.py IN.kicad_sch OUT.kicad_sch
"""
import sys, uuid
from sexp import parse, dump, find, first, Str
from schgeom import symbol_pins

REMOVE = {'J1', 'J2', 'J3', 'J4', 'R9'}
GLOBAL = {'GPIO0', 'GPIO1', 'GPIO2', 'GPIO3', 'GPIO25', 'USB_D+', 'USB_D-', 'SWCLK', 'SWD'}
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
            if name.startswith('GPIO'):
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
    open(dst, 'w').write(dump(sch) + '\n')
    print(f'removed {sorted(REMOVE)}; wrote {dst}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
