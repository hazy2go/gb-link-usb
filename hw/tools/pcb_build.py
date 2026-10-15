#!/usr/bin/env python3
"""Build hw/rev-a/gb-link-usb.kicad_pcb from Raspberry Pi's RP2350A minimal board + our schematic.

Run with KiCad's Python (provides pcbnew):
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 hw/tools/pcb_build.py

Always starts from the untouched reference board, so the result is reproducible:
  1. removes footprints that are not in our schematic (micro-USB, headers, SWD connector, R9, mounting holes)
     and the reference's board-level silkscreen text
  2. removes tracks/vias left dangling by that, repeatedly (header fan-out disappears, core routing stays)
  3. moves copper from reference net names ('/GPIO0') to our schematic's names ('GPIO0') so kept routing
     keeps its meaning; every pad then gets its schematic net
  4. adds the Link sheet footprints at the positions in PLACE, with symbol links for the parity check
  5. new board outline; the two full-board pours (+3V3 top, GND bottom) are reshaped to it; the small
     core pours (1V1, VREG_LX, VBUS, ...) stay as Raspberry Pi drew them
  6. locks every kept track/via so the autorouter treats the core routing as fixed
Routing of the remaining connections: pcb_route.py (Freerouting).
"""
import math, os, subprocess, sys, tempfile
import xml.etree.ElementTree as ET
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
REV = os.path.join(HERE, '..', 'rev-a')
REF_PCB = os.path.join(HERE, '..', 'reference', 'RPI-RP2350A-MINIMAL_R4-S1_public', 'RPI-RP2350A-MINIMAL_R4-S1.kicad_pcb')
SCH = os.path.join(REV, 'gb-link-usb.kicad_sch')
OUT = os.path.join(REV, 'gb-link-usb.kicad_pcb')
KICAD_FP = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints'

# Board outline (mm, same frame as the reference: RP2350 centre at 100,100)
X0, X1, Y0, Y1, CORNER = 83.3, 117.5, 67.0, 129.2, 1.5

# Link sheet parts: ref -> (x, y, rotation deg, side)
PLACE = {
    'J101': (100.0, 71.0, 180, 'F'),   # USB-C, opening at the top edge
    'R101': (94.0, 77.4, 90, 'F'),     # CC1 5.1k
    'R102': (95.0, 77.4, 90, 'F'),     # CC2 5.1k
    'U101': (98.0, 78.7, 90, 'F'),     # USBLC6
    # Link corner, left of the crystal, fed from the RP2350's bottom-left pins (GPIO12-15 at x 97.2-98.4,
    # y 103.45). Translators rotated 180: A (GPIO side) faces right, B (cable side) faces left. Pitch 5 mm
    # leaves room for the VCCA cap (right) and VCCB cap (left) between neighbours.
    'U102': (92.8, 104.8, 180, 'F'),   # 74LVC1T45 SCK  (A = GPIO13, DIR = GPIO12)
    'U103': (92.8, 109.8, 180, 'F'),   # 74LVC1T45 data from GB (A = GPIO14)
    'U104': (92.8, 114.8, 180, 'F'),   # 74LVC1T45 data to GB   (A = GPIO15)
    'C101': (94.0, 107.3, 0, 'F'), 'C103': (94.0, 112.3, 0, 'F'), 'C105': (96.0, 115.2, 90, 'F'),   # VCCA (+3V3)
    'C102': (90.4, 107.3, 0, 'F'), 'C104': (90.4, 112.3, 0, 'F'), 'C106': (89.6, 115.6, 90, 'F'),   # VCCB (VBUS)
    'R103': (89.9, 104.8, 90, 'F'),    # DIR pull-down, next to U102 DIR
    'R104': (88.0, 103.9, 0, 'F'), 'R105': (88.0, 108.9, 0, 'F'), 'R106': (88.0, 113.9, 0, 'F'),   # 220R series
    'C107': (90.1, 102.7, 270, 'F'), 'C108': (89.9, 109.2, 270, 'F'),     # 100p at the B inputs (SCK, data from GB)
    'R107': (88.0, 105.3, 0, 'F'), 'R108': (88.0, 110.3, 0, 'F'),                                  # 100k pull-ups
    'U105': (85.6, 110.0, 0, 'F'),     # TPD4E05U06 ESD, near the cable entry
    'J102': (85.0, 118.6, 0, 'F'),     # cable pads x 85..101 at y 118.6, strain-relief holes at y 127.6
    'D101': (114.2, 102.0, 0, 'F'), 'R109': (110.6, 102.0, 0, 'F'),    # status LED on GPIO21 (U1 pad 33, y 102.0)
}


SILK_PADS = ['SH', 'SCK', 'GND', 'SO', 'SI']   # J102 pads 1-5 (link.json): shield, plug 5, plug 6, plug 2, plug 3

KEEP = []   # every object we create and hand to the board: Python must not garbage-collect it


def mm(v):
    return pcbnew.FromMM(v)


def pt(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def schematic():
    xml = os.path.join(tempfile.mkdtemp(), 'net.xml')
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', xml, SCH], check=True, capture_output=True)
    root = ET.parse(xml).getroot()
    comps = {}
    for c in root.iter('comp'):
        sp = c.find('sheetpath')
        fields = {f.get('name'): (f.text or '') for f in c.iter('field')}
        tstamps = [t.text for t in c.iter('tstamps')] or [c.findtext('tstamp', '')]
        props = {pp.get('name') for pp in c.iter('property')}
        comps[c.get('ref')] = dict(value=c.findtext('value', ''), footprint=c.findtext('footprint', ''),
                                   sheet=sp.get('tstamps'), sym=tstamps[0], fields=fields,
                                   exclude_bom='exclude_from_bom' in props)
    pin_net = {}
    for n in root.iter('net'):
        name = n.get('name')
        if name.startswith('unconnected-('):
            name = 'unconnected-(' + name[len('unconnected-('):].replace('/', '{slash}')
        for nd in n.iter('node'):
            pin_net[(nd.get('ref'), nd.get('pin'))] = name
    return comps, pin_net


def is_via(t):
    return t.Type() == pcbnew.PCB_VIA_T


def remove_dangling(board, skip_refs=()):
    """Delete tracks with a loose end and vias that connect nothing, until stable.
    Pads of footprints in skip_refs count as already gone (they are removed afterwards)."""
    pads = [p for fp in board.GetFootprints() if fp.GetReference() not in skip_refs for p in fp.Pads()]
    zones = list(board.Zones())
    if True:
        tracks = list(board.GetTracks())
        ends = {}
        for t in tracks:
            if is_via(t):
                ends.setdefault((t.GetPosition().x, t.GetPosition().y, 'via'), []).append(t)
            else:
                for p in (t.GetStart(), t.GetEnd()):
                    ends.setdefault((p.x, p.y, t.GetLayer()), []).append(t)
        vias_at = {(k[0], k[1]) for k in ends if k[2] == 'via'}

        segs = [(t, t.GetStart(), t.GetEnd(), t.GetWidth(), t.GetLayer()) for t in tracks if not is_via(t)]

        def on_track(p, layer, me):
            # an end that lands on the middle of another track (T-junction) is connected
            for t, a, b, w, l in segs:
                if t is me or l != layer:
                    continue
                ax, ay, bx, by = a.x, a.y, b.x, b.y
                dx, dy = bx - ax, by - ay
                L2 = dx * dx + dy * dy
                u = 0 if L2 == 0 else max(0, min(1, ((p.x - ax) * dx + (p.y - ay) * dy) / L2))
                cx, cy = ax + u * dx, ay + u * dy
                if (p.x - cx) ** 2 + (p.y - cy) ** 2 <= (w / 2) ** 2:
                    return True
            return False

        def connected(p, layer, me, net):
            if len([x for x in ends.get((p.x, p.y, layer), []) if x is not me]) > 0:
                return True
            if on_track(p, layer, me):
                return True
            if (p.x, p.y) in vias_at and not is_via(me):
                return True
            for pad in pads:
                if pad.IsOnLayer(layer) and pad.HitTest(p, 0):
                    return True
            for z in zones:
                if z.GetNetCode() == net and z.IsOnLayer(layer) and z.Outline().Contains(p):
                    return True
            return False

        def trim(t):
            """A segment with one loose end that runs through pads: cut it back to the pad nearest the
            loose end (e.g. RUN runs through both SW2 pads on its way to the removed header)."""
            a, b, layer = t.GetStart(), t.GetEnd(), t.GetLayer()
            loose_a = not connected(a, layer, t, t.GetNetCode())
            loose_b = not connected(b, layer, t, t.GetNetCode())
            if loose_a == loose_b:
                return False
            loose, keep = (a, b) if loose_a else (b, a)
            best = None
            for pad in pads:
                if not pad.IsOnLayer(layer) or pad.GetNetCode() != t.GetNetCode():
                    continue
                c = pad.GetPosition()
                dx, dy = keep.x - loose.x, keep.y - loose.y
                L2 = dx * dx + dy * dy
                if L2 == 0:
                    continue
                u = ((c.x - loose.x) * dx + (c.y - loose.y) * dy) / L2
                px, py = loose.x + u * dx, loose.y + u * dy
                if 0 < u < 1 and (c.x - px) ** 2 + (c.y - py) ** 2 < pcbnew.FromMM(0.01) ** 2:
                    if best is None or u < best[0]:
                        best = (u, c)
            if best is None:
                return False
            if loose_a:
                t.SetStart(best[1])
            else:
                t.SetEnd(best[1])
            return True

        trimmed = [t for t in tracks if not is_via(t) and trim(t)]
        if trimmed:
            return len(trimmed)        # geometry changed: next pass (fresh process) re-evaluates

        dead = []
        for t in tracks:
            net = t.GetNetCode()
            if is_via(t):
                p = t.GetPosition()
                n_tracks = sum(len([x for x in ends.get((p.x, p.y, l), []) if not is_via(x)]) for l in (pcbnew.F_Cu, pcbnew.B_Cu))
                on_pad = any(pad.HitTest(p, 0) for pad in pads)
                in_zone = sum(1 for z in zones if z.GetNetCode() == net and z.Outline().Contains(p))
                if n_tracks + on_pad + in_zone < 2 and not (in_zone and n_tracks):
                    if n_tracks + in_zone + on_pad <= 1:
                        dead.append(t)
            else:
                if not connected(t.GetStart(), t.GetLayer(), t, net) or not connected(t.GetEnd(), t.GetLayer(), t, net):
                    dead.append(t)
        for t in dead:
            board.Remove(t)
        return len(dead)       # one pass; caller saves + reloads (KiCad's wrappers degrade after removals)


def remove_drawings(board):
    for d in list(board.GetDrawings()):
        if d.GetLayer() in (pcbnew.Edge_Cuts, pcbnew.F_SilkS, pcbnew.B_SilkS, pcbnew.F_Fab, pcbnew.B_Fab):
            board.Remove(d)


def outline(board):
    r = CORNER

    def line(x1, y1, x2, y2):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pt(x1, y1)); s.SetEnd(pt(x2, y2)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.05))
        board.Add(s); KEEP.append(s)

    def arc(cx, cy, sx, sy, deg):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        s.SetCenter(pt(cx, cy)); s.SetStart(pt(sx, sy)); s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(deg, pcbnew.DEGREES_T), True)
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.05))
        board.Add(s); KEEP.append(s)

    line(X0 + r, Y0, X1 - r, Y0); line(X1, Y0 + r, X1, Y1 - r); line(X1 - r, Y1, X0 + r, Y1); line(X0, Y1 - r, X0, Y0 + r)
    arc(X1 - r, Y0 + r, X1 - r, Y0, 90); arc(X1 - r, Y1 - r, X1, Y1 - r, 90)
    arc(X0 + r, Y1 - r, X0 + r, Y1, 90); arc(X0 + r, Y0 + r, X0, Y0 + r, 90)


def reshape_big_zones(board):
    """Clip the two full-board pours to the new outline. Their shape is kept: Raspberry Pi's +3V3 pour has
    deliberate cut-outs (it only covers parts of the inner area), so it is intersected, not replaced."""
    inset = 0.3
    rect = pcbnew.SHAPE_POLY_SET()
    rect.NewOutline()
    for x, y in ((X0 + inset, Y0 + inset), (X1 - inset, Y0 + inset), (X1 - inset, Y1 - inset), (X0 + inset, Y1 - inset)):
        rect.Append(mm(x), mm(y))
    for z in board.Zones():
        if pcbnew.ToMM(z.GetBoundingBox().GetWidth()) > 40:          # the two full-board pours
            o = z.Outline()
            o.BooleanIntersection(rect)
            if z.GetNetname() == '+3V3':
                # Raspberry Pi's +3V3 pour joins its top and bottom halves through columns along the board
                # edges, which our narrower board cuts off: add a 1 mm column along our right edge (the left
                # side is busy with the link circuitry; one column is enough to join the halves)
                for xa, xb in ((X1 - inset - 1.0, X1 - inset),):
                    strip = pcbnew.SHAPE_POLY_SET()
                    strip.NewOutline()
                    for x, y in ((xa, Y0 + inset), (xb, Y0 + inset), (xb, Y1 - inset), (xa, Y1 - inset)):
                        strip.Append(mm(x), mm(y))
                    o.BooleanAdd(strip)
            if z.GetNetname() == 'GND':
                # Raspberry Pi's GND pour stops above our cable pads; a trace along that edge can seal off a
                # pocket of pour (seen: C104/J102 GND island). Run the pour down to the board edge.
                o.BooleanAdd(rect)


def step_dangling(gone):
    board = pcbnew.LoadBoard(OUT)
    n = remove_dangling(board, set(gone))
    board.Save(OUT)
    print(n)


def step_remove(gone):
    board = pcbnew.LoadBoard(OUT)
    for fp in [f for f in board.GetFootprints() if f.GetReference() in gone]:
        board.Remove(fp)
    board.Save(OUT)


def step_drawings():
    board = pcbnew.LoadBoard(OUT)
    remove_drawings(board)
    board.Save(OUT)


def step_clear():
    """Remove kept reference copper (tracks, vias) that overlaps a new footprint (+0.3 mm) or leaves the new outline."""
    board = pcbnew.LoadBoard(OUT)
    boxes = []
    for fp in board.GetFootprints():
        if fp.GetReference() in PLACE:
            bb = fp.GetBoundingBox(False)
            bb.Inflate(mm(0.3))
            boxes.append(bb)
    dead = []
    inside = lambda p: X0 <= pcbnew.ToMM(p.x) <= X1 and Y0 <= pcbnew.ToMM(p.y) <= Y1
    for t in board.GetTracks():
        bb = t.GetBoundingBox()
        pts = [t.GetPosition()] if t.Type() == pcbnew.PCB_VIA_T else [t.GetStart(), t.GetEnd()]
        if any(b.Intersects(bb) for b in boxes) or not all(inside(p) for p in pts):
            dead.append(t)
    hit = {}
    for t in dead:
        for fp in board.GetFootprints():
            if fp.GetReference() in PLACE:
                bb = fp.GetBoundingBox(False); bb.Inflate(mm(0.3))
                if bb.Intersects(t.GetBoundingBox()):
                    hit.setdefault(t.GetNetname(), set()).add(fp.GetReference())
    for t in dead:
        board.Remove(t)
    board.Save(OUT)
    print('removed reference copper under new parts:', len(dead), {k: sorted(v) for k, v in hit.items()})


def step_strays():
    board = pcbnew.LoadBoard(OUT)
    # copper on unused nets, and zero-length segments (trimming can leave them; Freerouting chokes on them)
    dead = [t for t in board.GetTracks() if t.GetNetname().startswith('unconnected-')
            or (t.Type() != pcbnew.PCB_VIA_T and (t.GetStart() - t.GetEnd()).EuclideanNorm() < pcbnew.FromMM(0.01))]
    for t in dead:
        board.Remove(t)
    board.Save(OUT)
    print('removed stray copper (unused nets, zero-length):', len(dead))


def step_fill():
    board = pcbnew.LoadBoard(OUT)
    board.SynchronizeNetsAndNetClasses(True)   # nets created by this script get the default class (clearance!)
    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(OUT)
    print('zones refilled:', len(list(board.Zones())))


def step_finish():
    comps, pin_net = schematic()
    board = pcbnew.LoadBoard(OUT)

    # 3. nets: reference names -> schematic names, then every pad gets its schematic net
    want_names = set(pin_net.values())
    netinfo = {}

    def net(name):
        if name not in netinfo:
            ni = board.FindNet(name)
            if ni is None:
                ni = pcbnew.NETINFO_ITEM(board, name)
                board.Add(ni); KEEP.append(ni)
            netinfo[name] = ni
        return netinfo[name]

    renames = set()
    for t in list(board.GetTracks()) + list(board.Zones()):
        old = t.GetNetname()
        if old.startswith('/') and old[1:] in want_names:
            renames.add(old[1:])
            t.SetNet(net(old[1:]))
    print('renamed nets:', sorted(renames))

    # 4. new footprints
    on_board = {fp.GetReference(): fp for fp in board.GetFootprints()}
    for ref, fp in on_board.items():                    # RPi core parts: value + LCSC from our schematic
        c = comps.get(ref)
        if c and c['fields'].get('LCSC'):
            fp.SetValue(c['value'])
            fp.SetField('LCSC', c['fields']['LCSC'])
            f = fp.GetField('LCSC')
            f.SetVisible(False); f.SetLayer(pcbnew.F_Fab)
    for ref, c in comps.items():
        if ref.startswith('#') or not c['footprint'] or ref in on_board:
            continue
        if ref not in PLACE:
            sys.exit(f'{ref}: no position in PLACE')
        lib, name = c['footprint'].split(':', 1)
        fp = pcbnew.FootprintLoad(os.path.join(KICAD_FP, lib + '.pretty'), name)
        if fp is None:
            sys.exit(f'{ref}: footprint {c["footprint"]} not found')
        fp.SetReference(ref)
        fp.SetValue(c['value'])
        fp.SetFPIDAsString(c['footprint'])
        fp.SetPath(pcbnew.KIID_PATH(c['sheet'].rstrip('/') + '/' + c['sym']))
        for fname in ('LCSC', 'Datasheet', 'Description'):
            if fname in c['fields']:                    # parity compares these with the symbol, empty or not
                fp.SetField(fname, c['fields'][fname])
                f = fp.GetField(fname)
                f.SetVisible(False); f.SetLayer(pcbnew.F_Fab)
        fp.SetExcludedFromBOM(c['exclude_bom'])
        x, y, rot, side = PLACE[ref]
        board.Add(fp); KEEP.append(fp)
        if side == 'B':
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetPosition(pt(x, y))
        fp.SetOrientationDegrees(rot)
        on_board[ref] = fp
    changed = 0
    for ref, fp in on_board.items():
        for pad in fp.Pads():
            want = pin_net.get((ref, pad.GetNumber()))
            if want and pad.GetNetname() != want:
                pad.SetNet(net(want))
                changed += 1
    print('pads given their schematic net:', changed)
    for pad in on_board['J101'].Pads():          # USB-C VBUS pads (tiny) and shield (at the edge): solid to their pours
        if pad.GetNetname() == 'VBUS' or pad.GetNumber() == 'SH':
            pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    for pad in on_board['J102'].Pads():          # cable GND/shield pads: solid (traces between the pads left one thermal spoke)
        if pad.GetNetname() == 'GND':
            pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)

    # silkscreen: designators moved to the fab layer (on a board this dense they only overlap); a few useful labels instead
    for fp in board.GetFootprints():
        fp.Reference().SetLayer(pcbnew.F_Fab if fp.GetLayer() == pcbnew.F_Cu else pcbnew.B_Fab)

    def silk(text, x, y, size=0.8, bold=False, width=None):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text); t.SetLayer(pcbnew.F_SilkS); t.SetPosition(pt(x, y))
        t.SetTextSize(pcbnew.VECTOR2I(mm(width or size), mm(size))); t.SetTextThickness(mm(0.15))
        t.SetBold(bold)
        board.Add(t); KEEP.append(t)
    jx, jy = PLACE['J102'][0], PLACE['J102'][1]
    for i, lab in enumerate(SILK_PADS):          # cable pad names, between the pads and the relief holes
        silk(lab, jx + 4 * i, jy + 2.6, 0.8, False, 0.5)   # narrow: fits the relief channel
    silk('gb-link-usb', 110.2, 121.0, 1.0, True)
    silk('rev A', 110.2, 122.8, 0.8)
    silk('LED', PLACE['D101'][0], PLACE['D101'][1] - 1.9, 0.8)

    # 5. pours + outline, 6. lock the kept routing
    reshape_big_zones(board)
    for t in board.GetTracks():
        t.SetLocked(True)
    outline(board)
    board.Save(OUT)
    print('wrote', OUT)


def main():
    """Driver: each step that removes items runs in its own KiCad Python process (the bindings
    degrade for the rest of a process after removals)."""
    import shutil
    comps, _ = schematic()
    board = pcbnew.LoadBoard(REF_PCB)
    gone = sorted(fp.GetReference() for fp in board.GetFootprints() if fp.GetReference() not in comps)
    print('removing footprints:', gone)
    shutil.copy(REF_PCB, OUT)
    me = [sys.executable, os.path.abspath(__file__)]
    total = 0
    while True:
        r = subprocess.run(me + ['dangling'] + gone, capture_output=True, text=True)
        lines = [l for l in r.stdout.splitlines() if l.strip().isdigit()]
        if r.returncode or not lines:
            sys.exit('dangling step failed:\n' + r.stdout[-2000:] + r.stderr[-2000:])
        n = int(lines[-1])
        total += n
        if n == 0:
            break
    print('removed dangling tracks/vias:', total)
    for step in (['remove'] + gone, ['drawings']):
        r = subprocess.run(me + step, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f'{step[0]} step failed:\n' + r.stderr[-3000:])
    def run(step, *args):
        r = subprocess.run(me + [step, *args], capture_output=True, text=True)
        print('\n'.join(l for l in r.stdout.splitlines() if ':' in l and 'Debug' not in l))
        if r.returncode:
            sys.exit(f'{step} failed:\n' + r.stderr[-3000:])
        return r.stdout
    run('finish')
    run('clear')
    total = 0
    while True:                                     # clearing can leave new dangling ends
        out = subprocess.run(me + ['dangling'], capture_output=True, text=True).stdout
        n = int([l for l in out.splitlines() if l.strip().isdigit()][-1])
        total += n
        if not n:
            break
    print('removed dangling after clearing:', total)
    run('strays')
    run('fill')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'dangling':
        step_dangling(sys.argv[2:])
    elif len(sys.argv) > 1 and sys.argv[1] == 'remove':
        step_remove(sys.argv[2:])
    elif len(sys.argv) > 1 and sys.argv[1] == 'drawings':
        step_drawings()
    elif len(sys.argv) > 1 and sys.argv[1] == 'finish':
        step_finish()
    elif len(sys.argv) > 1 and sys.argv[1] == 'clear':
        step_clear()
    elif len(sys.argv) > 1 and sys.argv[1] == 'strays':
        step_strays()
    elif len(sys.argv) > 1 and sys.argv[1] == 'fill':
        step_fill()
    else:
        main()
