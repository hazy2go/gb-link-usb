#!/usr/bin/env python3
"""Give every GND pad of the Link parts its own via to the bottom GND pour (short trace + via).

Run with KiCad's Python after pcb_build.py, before pcb_route.py. Through-hole GND pads (USB-C shield,
cable pads) reach the bottom pour by themselves and are skipped. For each SMD GND pad, candidate via
spots around the pad are tried, nearest first; a spot is used only if the via and the short trace keep
clearance from all copper of other nets and from the board edge. The added copper is locked, so the
autorouter treats it as fixed.
"""
import math, os, sys
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcb_build

PCB = pcb_build.OUT
VIA_D, VIA_DRILL, TRACK_W, CLR, EDGE = 0.6, 0.3, 0.25, 0.2, 0.5     # mm (CLR a bit above the 0.15 rule)
KEEP = []


def main():
    b = pcbnew.LoadBoard(PCB)
    gnd = b.FindNet('GND')
    mm = pcbnew.FromMM
    # obstacles: (bbox, net) for pads and tracks/vias, refreshed as we add copper
    obstacles = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            obstacles.append((p.GetBoundingBox(), p.GetNetCode(), p))
    for t in b.GetTracks():
        obstacles.append((t.GetBoundingBox(), t.GetNetCode(), t))

    def seg_box(a, c, half):
        x0, x1 = min(a.x, c.x) - half, max(a.x, c.x) + half
        y0, y1 = min(a.y, c.y) - half, max(a.y, c.y) + half
        return pcbnew.BOX2I(pcbnew.VECTOR2I(int(x0), int(y0)), pcbnew.VECTOR2I(int(x1 - x0), int(y1 - y0)))

    def free(box, own_pad, is_via=False):
        for ob, net, item in obstacles:
            if item is own_pad:
                continue
            if net == gnd.GetNetCode():
                # touching other GND copper is fine, but drilled holes need their spacing
                if is_via and item.Type() == pcbnew.PCB_VIA_T:
                    g = pcbnew.BOX2I(ob.GetPosition(), ob.GetSize())
                    g.Inflate(mm(0.35))
                    if g.Intersects(box):
                        return False
                continue
            g = pcbnew.BOX2I(ob.GetPosition(), ob.GetSize())
            g.Inflate(mm(CLR))
            if g.Intersects(box):
                return False
        return True

    def inside_board(pt):
        x, y = pcbnew.ToMM(pt.x), pcbnew.ToMM(pt.y)
        return pcb_build.X0 + EDGE <= x <= pcb_build.X1 - EDGE and pcb_build.Y0 + EDGE <= y <= pcb_build.Y1 - EDGE

    added, failed, seen = 0, [], set()
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if ref not in pcb_build.PLACE:
            continue
        for pad in fp.Pads():
            if pad.GetNetname() != 'GND' or pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                continue
            c = pad.GetPosition()
            if (c.x, c.y) in seen:            # USB-C A1/B12 etc. share one spot: one via is enough
                continue
            seen.add((c.x, c.y))
            done = False
            # prefer the direction away from the RP2350 (centre 100,100): keeps the GPIO channels free
            away = math.atan2(pcbnew.ToMM(c.y) - 100.0, pcbnew.ToMM(c.x) - 100.0)
            order = sorted(range(16), key=lambda k: abs(math.remainder(2 * math.pi * k / 16 - away, 2 * math.pi)))
            for r in (0.75, 0.95, 1.2, 1.5, 2.0, 2.5):
                for k in order:
                    ang = 2 * math.pi * k / 16
                    v = pcbnew.VECTOR2I(int(c.x + mm(r) * math.cos(ang)), int(c.y + mm(r) * math.sin(ang)))
                    if not inside_board(v):
                        continue
                    vbox = seg_box(v, v, mm(VIA_D / 2))
                    tbox = seg_box(c, v, mm(TRACK_W / 2))
                    if free(vbox, pad, is_via=True) and free(tbox, pad):
                        t = pcbnew.PCB_TRACK(b)
                        t.SetStart(c); t.SetEnd(v); t.SetWidth(mm(TRACK_W)); t.SetLayer(pcbnew.F_Cu)
                        t.SetNet(gnd); t.SetLocked(True)
                        via = pcbnew.PCB_VIA(b)
                        via.SetPosition(v); via.SetDrill(mm(VIA_DRILL)); via.SetWidth(mm(VIA_D))
                        via.SetNet(gnd); via.SetLocked(True)
                        b.Add(t); b.Add(via); KEEP.extend([t, via])
                        obstacles.append((t.GetBoundingBox(), gnd.GetNetCode(), t))
                        obstacles.append((via.GetBoundingBox(), gnd.GetNetCode(), via))
                        added += 1
                        done = True
                        break
                if done:
                    break
            if not done:
                failed.append(f'{ref}.{pad.GetNumber()}')
    b.Save(PCB)
    print('GND vias added:', added, ' no room:', failed)


if __name__ == '__main__':
    main()
