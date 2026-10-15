#!/usr/bin/env python3
"""Tidy the routing that is NOT in the reference board (Croco's original copper is never touched). KiCad Python.

Phases (each in its own process, because KiCad's Python objects go stale after BOARD.Remove):
  dup    segments lying on another same-net segment's centre line: removed
  crumb  segments < 50 um at a plain joint: removed, the neighbour's end moved onto the crumb's other end
  pull   pull-tight: every maximal chain of new segments (same net + layer, joints with exactly two segments and
         no via/pad) is replaced by the shortest of straight / 45-then-straight / straight-then-45 between its
         two ends, if that has fewer segments, is no longer, and clears all other-net copper on the layer by
         CLEAR (exact KiCad shapes: tracks, vias, pads, footprint copper; zones refill and are not obstacles)
  merge  two collinear same-width segments at a plain joint: one segment
  stub   segments with an end that touches nothing: removed
The driver repeats crumb/pull/stub until nothing changes. Run DRC afterwards.
Usage: route_clean.py PCB REF_PCB"""
import collections, math, subprocess, sys
import pcbnew
CLEAR, HOLE_CLEAR = 0.155, 0.255


def mm(v): return pcbnew.FromMM(v)


def key(t):
    s, e = t.GetStart(), t.GetEnd()
    a, b = sorted([(s.x, s.y), (e.x, e.y)])
    return (t.GetClass(), t.GetNetname(), t.GetLayer(), a, b) if t.GetClass() != 'PCB_VIA' else (t.GetClass(), t.GetNetname(), (s.x, s.y))


def phase(pcb, ref, ph):
    b = pcbnew.LoadBoard(pcb); r = pcbnew.LoadBoard(ref)
    old = {key(t) for t in r.GetTracks()}
    st = collections.Counter()
    tracks = list(b.GetTracks())
    segs = [t for t in tracks if t.GetClass() == 'PCB_TRACK']
    vias = [t for t in tracks if t.GetClass() == 'PCB_VIA']
    ends = collections.defaultdict(list)
    for t in segs:
        for p in (t.GetStart(), t.GetEnd()):
            ends[(t.GetNetname(), t.GetLayer(), p.x, p.y)].append(t)
    pads = collections.defaultdict(list)
    for f in b.GetFootprints():
        for p in f.Pads():
            for l in p.GetLayerSet().CuStack():
                pads[(p.GetNetname(), l)].append(p)
    new = {id(t) for t in segs if key(t) not in old}

    def via_at(n, l, p):
        return any(v.GetNetname() == n and (v.GetPosition() - p).EuclideanNorm() < v.GetWidth(l) // 2 + 1000 for v in vias)

    def plain(n, l, p):
        return len(ends[(n, l, p.x, p.y)]) == 2 and not via_at(n, l, p) and not any(q.HitTest(p) for q in pads[(n, l)])
    remove, add = [], []

    def obstacles():
        ob = collections.defaultdict(list)   # layer -> (net, shape, clearance mm)
        for t in segs + vias:
            for l in t.GetLayerSet().CuStack():
                ob[l].append((t.GetNetname(), t.GetEffectiveShape(l), CLEAR))
        holes = [(v.GetPosition(), v.GetDrill()) for v in vias]
        for f in b.GetFootprints():
            for q in f.Pads():
                for l in q.GetLayerSet().CuStack():
                    ob[l].append((q.GetNetname(), q.GetEffectiveShape(l), max(CLEAR, q.GetOwnClearance(l) / 1e6 + 0.005)))
                if q.GetDrillSizeX() > 0:
                    holes.append((q.GetPosition(), max(q.GetDrillSizeX(), q.GetDrillSizeY())))
            for g in f.GraphicalItems():
                if g.GetClass() == 'PCB_SHAPE' and g.IsOnCopperLayer():
                    ob[g.GetLayer()].append((g.GetNetname(), g.GetEffectiveShape(g.GetLayer()), CLEAR))
        cu = list(b.GetEnabledLayers().CuStack())
        for p, d in holes:                     # hole clearance applies to every net, on every layer
            for l in cu:
                ob[l].append(('<hole>', pcbnew.SHAPE_SEGMENT(p, p, d), HOLE_CLEAR))
        for z in list(b.Zones()) + [z for f in b.GetFootprints() for z in f.Zones()]:   # rule areas that forbid tracks
            if z.GetIsRuleArea() and z.GetDoNotAllowTracks():
                for l in z.GetLayerSet().CuStack():
                    ob[l].append(('<keepout>', z.Outline(), 0.0))
        return ob

    def clear(ob, l, n, shape):
        return not any(nn != n and s.Collide(shape, mm(c)) for nn, s, c in ob[l])
    if ph == 'dup':
        gone = set()
        for t in segs:
            if id(t) not in new:
                continue
            for u in segs:
                if u is t or id(u) in gone or u.GetNetname() != t.GetNetname() or u.GetLayer() != t.GetLayer() or u.GetWidth() < t.GetWidth():
                    continue
                sg = pcbnew.SEG(u.GetStart(), u.GetEnd())
                if sg.Distance(t.GetStart()) <= 1000 and sg.Distance(t.GetEnd()) <= 1000:
                    # only if no third segment hangs on t's ends (else it would be left on u's body)
                    if all(len([x for x in ends[(t.GetNetname(), t.GetLayer(), p.x, p.y)] if x is not t and x is not u]) == 0
                           or p in (u.GetStart(), u.GetEnd()) for p in (t.GetStart(), t.GetEnd())):
                        gone.add(id(t)); remove.append(t); st['duplicate'] += 1; break
    elif ph == 'crumb':
        touched = set(); ob = obstacles()
        for t in segs:
            if id(t) not in new or t.GetLength() >= mm(0.05) or id(t) in touched:
                continue
            n, l = t.GetNetname(), t.GetLayer()
            for P, Q in ((t.GetStart(), t.GetEnd()), (t.GetEnd(), t.GetStart())):
                if plain(n, l, Q):
                    u = [x for x in ends[(n, l, Q.x, Q.y)] if x is not t][0]
                    if id(u) not in new or id(u) in touched:
                        continue
                    other = u.GetEnd() if u.GetStart() == Q else u.GetStart()
                    if not clear(ob, l, n, pcbnew.SHAPE_SEGMENT(other, P, u.GetWidth())):
                        continue
                    if u.GetStart() == Q: u.SetStart(P)
                    else: u.SetEnd(P)
                    touched |= {id(t), id(u)}; remove.append(t); st['crumb'] += 1
                    break
    elif ph == 'pull':
        obst = obstacles()
        used = set()

        def clear_path(path, w, n, l):
            return all(clear(obst, l, n, pcbnew.SHAPE_SEGMENT(path[i], path[i + 1], w)) for i in range(len(path) - 1))

        def shortcuts(A, B):
            dx, dy = B.x - A.x, B.y - A.y; m = min(abs(dx), abs(dy))
            M1 = pcbnew.VECTOR2I(A.x + int(math.copysign(m, dx)), A.y + int(math.copysign(m, dy)))
            M2 = pcbnew.VECTOR2I(B.x - int(math.copysign(m, dx)), B.y - int(math.copysign(m, dy)))
            out = []
            octo = dx == 0 or dy == 0 or abs(dx) == abs(dy)
            for path in (([A, B],) if octo else ()) + ([A, M1, B], [A, M2, B]):   # 0/45/90 degree segments only
                path = [p for i, p in enumerate(path) if i == 0 or p != path[i - 1]]
                if len(path) >= 2:
                    out.append(path)
            return out
        for t in segs:
            if id(t) in used or id(t) not in new:
                continue
            n, l = t.GetNetname(), t.GetLayer()
            # walk to one end of the chain, then collect the ordered point list
            p, cur = t.GetStart(), t
            seen = {id(t)}
            while plain(n, l, p):
                nx = [x for x in ends[(n, l, p.x, p.y)] if x is not cur][0]
                if id(nx) in seen or id(nx) not in new or nx.GetWidth() != t.GetWidth():
                    break
                seen.add(id(nx)); cur = nx
                p = nx.GetEnd() if nx.GetStart() == p else nx.GetStart()
            pts, chain = [p], []
            q = cur.GetEnd() if cur.GetStart() == p else cur.GetStart()
            while True:
                chain.append(cur); used.add(id(cur)); pts.append(q)
                if not plain(n, l, q):
                    break
                nx = [x for x in ends[(n, l, q.x, q.y)] if x is not cur][0]
                if id(nx) in used or id(nx) not in new or nx.GetWidth() != t.GetWidth():
                    break   # a width change (neck-down at a pin) ends the chain: widths are kept as routed
                cur = nx; q = nx.GetEnd() if nx.GetStart() == q else nx.GetStart()
            if len(chain) < 2:
                continue
            w = wmax = t.GetWidth()
            # greedy: from each point jump to the farthest point reachable by a clear shortcut
            outp, i, k = [pts[0]], 0, len(pts) - 1
            while i < k:
                best = None
                for j in range(k, i + 1, -1):
                    seglen = sum((pts[x + 1] - pts[x]).EuclideanNorm() for x in range(i, j))
                    for path in shortcuts(pts[i], pts[j]):
                        ln = sum((path[x + 1] - path[x]).EuclideanNorm() for x in range(len(path) - 1))
                        if ln <= seglen + 1000 and len(path) - 1 < j - i and clear_path(path, wmax if wmax == w else w, n, l):
                            best = (j, path); break
                    if best:
                        break
                if best:
                    outp += best[1][1:]; i = best[0]
                else:
                    outp.append(pts[i + 1]); i += 1
            if len(outp) - 1 >= len(chain):
                continue
            remove += chain
            for x in range(len(outp) - 1):
                add.append((outp[x], outp[x + 1], w if wmax != w else wmax, n, l))
                obst[l].append((n, pcbnew.SHAPE_SEGMENT(outp[x], outp[x + 1], w), CLEAR))
            st['pulled_chains'] += 1; st['segments_saved'] += len(chain) - (len(outp) - 1)
    elif ph == 'merge':                 # two collinear same-width new segments at a plain joint -> one segment
        done = set()
        for (n, l, x, y), lst in list(ends.items()):
            if len(lst) != 2 or any(id(t) in done or id(t) not in new for t in lst):
                continue
            p = pcbnew.VECTOR2I(x, y)
            if not plain(n, l, p) or lst[0].GetWidth() != lst[1].GetWidth():
                continue
            a = lst[0].GetEnd() if lst[0].GetStart() == p else lst[0].GetStart()
            c = lst[1].GetEnd() if lst[1].GetStart() == p else lst[1].GetStart()
            if a == p or c == p or (a.x - p.x) * (c.y - p.y) != (a.y - p.y) * (c.x - p.x) or (a.x - p.x) * (c.x - p.x) + (a.y - p.y) * (c.y - p.y) >= 0:
                continue                    # not on one straight line through p
            done |= {id(lst[0]), id(lst[1])}; remove += lst; add.append((a, c, lst[0].GetWidth(), n, l)); st['merged'] += 1
    elif ph == 'stub':
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
        zf = collections.defaultdict(list)
        for z in b.Zones():
            for l in z.GetLayerSet().CuStack():
                if z.HasFilledPolysForLayer(l):
                    zf[(z.GetNetname(), l)].append(z.GetFilledPolysList(l))
        for t in segs:
            if id(t) not in new:
                continue
            n, l = t.GetNetname(), t.GetLayer()
            for p in (t.GetStart(), t.GetEnd()):
                if len(ends[(n, l, p.x, p.y)]) > 1 or via_at(n, l, p) or any(q.HitTest(p) for q in pads[(n, l)]):
                    continue
                if any(u is not t and u.GetNetname() == n and u.GetLayer() == l and pcbnew.SEG(u.GetStart(), u.GetEnd()).Distance(p) <= u.GetWidth() // 2 for u in segs):
                    continue
                if any(fp.Contains(p) for fp in zf[(n, l)]):
                    continue
                remove.append(t); st['stub'] += 1
                break
    for t in remove:
        b.Remove(t)
    for a, c, w, n, l in add:
        s = pcbnew.PCB_TRACK(b); s.SetStart(a); s.SetEnd(c); s.SetWidth(w); s.SetLayer(l); s.SetNet(b.FindNet(n)); b.Add(s)
    if remove or add:
        b.Save(pcb)
    print('STATS', dict(st), flush=True)


def main():
    pcb, ref = sys.argv[1:3]
    if '--phase' in sys.argv:
        return phase(pcb, ref, sys.argv[sys.argv.index('--phase') + 1])
    total = collections.Counter()

    def run(ph):
        out = subprocess.run([sys.executable, __file__, pcb, ref, '--phase', ph], capture_output=True, text=True)
        line = [l for l in out.stdout.splitlines() if l.startswith('STATS ')]
        if not line:
            sys.exit(f'phase {ph} failed:\n{out.stderr[-2000:]}')
        st = eval(line[-1][6:]); total.update(st); print(ph, st, flush=True); return st
    run('dup')
    for rnd in range(12):
        if not any([run('crumb'), run('pull'), run('merge'), run('dup'), run('stub')]):
            break
    print('TOTAL', dict(total))


if __name__ == '__main__':
    main()
