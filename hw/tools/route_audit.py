#!/usr/bin/env python3
"""Routing tidy-up audit (KiCad Python). Only copper that is NOT in the reference board (Croco's original) is
audited, so Croco's proven routing is never reported or touched.

Reports, per new track/via:
  STUB      track end that touches nothing (no pad, via, other track end, zone)            -> dead copper
  TINY      segment shorter than 0.05 mm                                                      -> raster crumbs
  COLLINEAR two segments of one net/layer/width meeting end to end in a straight line          -> mergeable
  STAIR     a run of >= 3 short (< 0.3 mm) segments alternating direction                     -> router staircase
  ACUTE     two segments meeting at an angle sharper than 90 deg (acid trap)
  OVERLAP   segment lying on top of another segment of the same net/layer                    -> duplicate
  VIA1      via whose copper connects on only one layer (no layer change)                     -> pointless via
  DETOUR    net routed length > 3x the straight distance between its pads (and > 10 mm)
Usage: route_audit.py PCB REF_PCB [--json out.json]"""
import collections, json, math, sys
import pcbnew


def key(t):
    s, e = t.GetStart(), t.GetEnd()
    a, b = sorted([(s.x, s.y), (e.x, e.y)])
    return (t.GetClass(), t.GetNetname(), t.GetLayer(), a, b) if t.GetClass() != 'PCB_VIA' else (t.GetClass(), t.GetNetname(), (s.x, s.y))


def ang(v):
    return math.atan2(v[1], v[0])


def main():
    pcb, ref = sys.argv[1:3]
    b = pcbnew.LoadBoard(pcb); r = pcbnew.LoadBoard(ref)
    old = {key(t) for t in r.GetTracks()}
    tracks = list(b.GetTracks())
    new = [t for t in tracks if key(t) not in old]
    newset = {id(t) for t in new}
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    issues = []

    def add(kind, t, msg):
        p = t.GetPosition() if t.GetClass() == 'PCB_VIA' else t.GetStart()
        issues.append(dict(kind=kind, net=t.GetNetname(), layer=b.GetLayerName(t.GetLayer()), x=round(p.x / 1e6, 3), y=round(p.y / 1e6, 3), msg=msg))

    segs = [t for t in tracks if t.GetClass() == 'PCB_TRACK']
    vias = [t for t in tracks if t.GetClass() == 'PCB_VIA']
    ends = collections.defaultdict(list)          # (net, layer, x, y) -> segments ending there
    for t in segs:
        for p in (t.GetStart(), t.GetEnd()):
            ends[(t.GetNetname(), t.GetLayer(), p.x, p.y)].append(t)
    pads = collections.defaultdict(list)
    for f in b.GetFootprints():
        for p in f.Pads():
            for l in p.GetLayerSet().CuStack():
                pads[(p.GetNetname(), l)].append(p)
    zones = collections.defaultdict(list)
    for z in b.Zones():
        for l in z.GetLayerSet().CuStack():
            if z.HasFilledPolysForLayer(l):
                zones[(z.GetNetname(), l)].append(z.GetFilledPolysList(l))
    vias_at = collections.defaultdict(list)
    for v in vias:
        vias_at[(v.GetNetname(), v.GetPosition().x, v.GetPosition().y)].append(v)

    def touches(net, l, p, me):
        if len([t for t in ends[(net, l, p.x, p.y)] if t is not me]):
            return True
        if vias_at.get((net, p.x, p.y)):
            return True
        for v in vias:
            if v.GetNetname() == net and (v.GetPosition() - p).EuclideanNorm() < v.GetWidth(l) // 2:
                return True
        for q in pads[(net, l)]:
            if q.HitTest(p):
                return True
        for t in segs:     # T-junction: end lying on another same-net segment's body
            if t is not me and t.GetNetname() == net and t.GetLayer() == l and t.HitTest(p, 1000):
                return True
        for fp in zones[(net, l)]:
            if fp.Contains(p):
                return True
        return False

    for t in new:
        if t.GetClass() == 'PCB_VIA':
            n = t.GetNetname(); p = t.GetPosition()
            layers = set()
            for s in segs:
                if s.GetNetname() == n and (s.GetStart() == p or s.GetEnd() == p or s.HitTest(p, 1000)):
                    layers.add(s.GetLayer())
            for (zn, l), fps in zones.items():
                if zn == n and any(fp.Contains(p) for fp in fps):
                    layers.add(l)
            for (pn, l), ps in pads.items():
                if pn == n and any(q.HitTest(p) for q in ps):
                    layers.add(l)
            if len(layers) < 2:
                add('VIA1', t, f'connects only {sorted(b.GetLayerName(l) for l in layers)}')
            continue
        n, l = t.GetNetname(), t.GetLayer()
        L = t.GetLength() / 1e6
        if L < 0.05:
            add('TINY', t, f'{L * 1000:.0f} um')
        for p in (t.GetStart(), t.GetEnd()):
            if not touches(n, l, p, t):
                add('STUB', t, f'end ({p.x / 1e6:.3f}, {p.y / 1e6:.3f}) touches nothing, {L:.2f} mm')
        for u in segs:
            if u is t or u.GetNetname() != n or u.GetLayer() != l:
                continue
            if id(u) < id(t) and id(u) in newset:
                continue
            # overlap: both ends of t on u
            sg = pcbnew.SEG(u.GetStart(), u.GetEnd())      # centre-line containment, not the copper width
            if sg.Distance(t.GetStart()) <= 1000 and sg.Distance(t.GetEnd()) <= 1000 and L > 0:
                add('OVERLAP', t, f'lies on another {n} segment')
    # collinear / acute / stairs at joints between segments (only joints touching new copper)
    seen = set()
    for k, lst in ends.items():
        if len(lst) != 2 or not any(id(t) in newset for t in lst):
            continue
        net, l, x, y = k
        if any(v for v in vias_at.get((net, x, y), [])):
            continue
        if any(q.HitTest(pcbnew.VECTOR2I(x, y)) for q in pads[(net, l)]):
            continue
        a, c = lst
        va = (a.GetEnd().x - x, a.GetEnd().y - y) if (a.GetStart().x, a.GetStart().y) == (x, y) else (a.GetStart().x - x, a.GetStart().y - y)
        vc = (c.GetEnd().x - x, c.GetEnd().y - y) if (c.GetStart().x, c.GetStart().y) == (x, y) else (c.GetStart().x - x, c.GetStart().y - y)
        if va == (0, 0) or vc == (0, 0):
            continue
        d = abs((ang(va) - ang(vc) + math.pi) % (2 * math.pi) - math.pi)
        if abs(d - math.pi) < 1e-3 and a.GetWidth() == c.GetWidth():
            add('COLLINEAR', a, f'joint ({x / 1e6:.3f}, {y / 1e6:.3f})')
        elif d < math.pi / 2 - 1e-3:
            add('ACUTE', a, f'{math.degrees(d):.0f} deg at ({x / 1e6:.3f}, {y / 1e6:.3f})')
    # stairs: chains of short new segments
    for t in new:
        if t.GetClass() != 'PCB_TRACK' or t.GetLength() / 1e6 >= 0.3:
            continue
        p = t.GetEnd(); chain = 1; cur = t
        while True:
            nx = [u for u in ends[(cur.GetNetname(), cur.GetLayer(), p.x, p.y)] if u is not cur]
            if len(nx) != 1 or nx[0].GetLength() / 1e6 >= 0.3 or id(nx[0]) in seen:
                break
            cur = nx[0]; seen.add(id(cur)); chain += 1
            p = cur.GetEnd() if cur.GetStart() == p else cur.GetStart()
        if chain >= 3:
            add('STAIR', t, f'{chain} short segments in a row')
    # detours: per net, new routed length vs pad spread
    bynet = collections.defaultdict(float)
    for t in new:
        if t.GetClass() == 'PCB_TRACK':
            bynet[t.GetNetname()] += t.GetLength() / 1e6
    for n, ln in bynet.items():
        ps = [q.GetPosition() for (pn, l), qs in pads.items() if pn == n for q in qs]
        if len(ps) < 2:
            continue
        span = max(math.dist((a.x / 1e6, a.y / 1e6), (c.x / 1e6, c.y / 1e6)) for a in ps for c in ps)
        if ln > 10 and ln > 3 * span:
            issues.append(dict(kind='DETOUR', net=n, layer='', x=0, y=0, msg=f'new copper {ln:.1f} mm vs pad span {span:.1f} mm'))
    c = collections.Counter(i['kind'] for i in issues)
    print(f'new items audited: {len(new)} ({sum(1 for t in new if t.GetClass() == "PCB_VIA")} vias)')
    print('summary:', dict(c))
    for i in issues:
        print(f"{i['kind']:9} {i['net']:22} {i['layer']:7} ({i['x']}, {i['y']}) {i['msg']}")
    if '--json' in sys.argv:
        json.dump(issues, open(sys.argv[sys.argv.index('--json') + 1], 'w'), indent=1)


if __name__ == '__main__':
    main()
