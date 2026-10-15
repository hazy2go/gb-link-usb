#!/usr/bin/env python3
"""Autoroute the open connections of hw/rev-a/gb-link-usb.kicad_pcb with Freerouting.

Board pipeline: pcb_build.py -> pcb_route.py hand -> pcb_gnd.py -> pcb_route.py   (see hw/README.md)

Run with KiCad's Python. Kept core routing is locked (pcb_build.py), so KiCad exports it to the DSN as
fixed wiring and Freerouting only adds copper. Steps run in separate processes (KiCad's Python bindings
degrade after some operations): export DSN -> Freerouting -> import SES -> refill zones.
"""
import os, subprocess, sys
import pcbnew
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
REV = os.path.join(HERE, '..', 'rev-a')
PCB = os.path.join(REV, 'gb-link-usb.kicad_pcb')
WORK = os.path.join(REV, 'route')
DSN, SES = os.path.join(WORK, 'board.dsn'), os.path.join(WORK, 'board.ses')
COPY = os.path.join(WORK, 'dsn-board.kicad_pcb')   # what Freerouting sees (see prep)
MIN_W = 0.15
JAVA = '/opt/homebrew/opt/openjdk/bin/java'
JAR = os.path.expanduser('~/tools/freerouting/freerouting.jar')


TAPS = {'+3V3': ('C15', '1'), 'VBUS': ('C1', '1')}   # where new 3.3 V / VBUS traces join the core

# Hand routes laid before Freerouting (locked), mm, F.Cu:
#  GPIO15: the three GPIO lines to the translator column must nest (the one to the bottom translator runs
#  outside); Freerouting kept blocking that outside path, so it is drawn by hand: down from U1 pad 19,
#  45 deg past C18, straight down at x 96.55 (left of the crystal's GND patch), into U104 pin 3 (A).
#  GND U105 8->3: the ESD chip's two GND pins sit opposite each other; no room for a via at pin 8.
HAND = [
    # The three data lines leave U1's bottom-left pads (16/17/18), go straight down and turn left at their
    # own height, 0.4 mm apart, nested: the line to the top translator turns first, the one to the bottom
    # translator last and outermost. Limits: C18's top pad edge (y 105.33) and the core +3V3 trace from
    # pad 20 down to C18 (why pad 19 / GPIO15 is not used).
    ('GPIO12', 0.15, [(97.2, 103.45), (97.2, 104.05), (94.3, 104.05)]),                                  # -> U102 A (SCK)
    ('GPIO13', 0.15, [(97.6, 103.45), (97.6, 104.45), (95.4, 104.45), (95.4, 108.85), (94.3, 108.85)]),   # -> U103 A (from GB)
    ('GPIO14', 0.15, [(98.0, 103.45), (98.0, 104.85), (96.4, 104.85), (96.4, 113.85), (94.3, 113.85)]),   # -> U104 A (to GB)
    # Direction: U1 left-side pad 15 (GPIO11) exits above the fan, runs over U102 and down the 0.95 mm gap
    # between U102's pin rows into its DIR pin (pin 5)
    ('GPIO11', 0.15, [(96.55, 102.8), (92.8, 102.8), (92.8, 104.8), (92.0, 104.8)]),
    # U104 DIR (pin 5) is tied to 3.3 V: across the pin-row gap to its own VCCA (pin 1)
    ('+3V3', 0.2, [(92.0, 114.8), (92.8, 114.8), (92.8, 115.75), (93.6, 115.75)]),
    # The ESD chip's two GND pins sit opposite each other; no room for a via at pin 8
    ('GND', 0.2, [(85.215, 110.0), (85.985, 110.0)]),
]


def hand():
    b = pcbnew.LoadBoard(PCB)
    keep = []
    n = 0
    for net, w, pts in HAND:
        ni = b.FindNet(net)
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(x1), pcbnew.FromMM(y1)))
            t.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(x2), pcbnew.FromMM(y2)))
            t.SetWidth(pcbnew.FromMM(w)); t.SetLayer(pcbnew.F_Cu); t.SetNet(ni); t.SetLocked(True)
            b.Add(t); keep.append(t); n += 1
    b.Save(PCB)
    print('hand-routed segments:', n)


def tidy():
    """Remove vias that end up connected on one layer only (Freerouting leftovers)."""
    b = pcbnew.LoadBoard(PCB)
    tracks = [t for t in b.GetTracks() if t.Type() != pcbnew.PCB_VIA_T]
    dead = []
    for v in b.GetTracks():
        if v.Type() != pcbnew.PCB_VIA_T or v.IsLocked():
            continue
        p = v.GetPosition()
        layers = {t.GetLayer() for t in tracks if t.GetNetCode() == v.GetNetCode() and (t.GetStart() == p or t.GetEnd() == p)}
        in_zone = any(z.GetNetCode() == v.GetNetCode() and z.Outline().Contains(p) for z in b.Zones())
        if len(layers) < 2 and not in_zone:
            dead.append(v)
    for v in dead:
        b.Remove(v)
    b.Save(PCB)
    print('removed one-layer vias:', len(dead))


def prep():
    """Copy for Freerouting, step 1 (removals run in their own process): drop the two full-board pours.
    As planes, Freerouting would not cross them, leaving almost no room; on the real board they stay and
    simply pour around the new traces."""
    b = pcbnew.LoadBoard(COPY)
    big = [z for z in b.Zones() if pcbnew.ToMM(z.GetBoundingBox().GetWidth()) > 20]
    for z in big:
        b.Remove(z)
    b.Save(COPY)
    print('copy: removed full-board pours:', len(big))


def prep2():
    """Copy for Freerouting, step 2:
    - small core pours (1V1, VREG_LX, VBUS, +3V3/GND patches) stay as pours: Freerouting does not route
      other nets across them (as no-go areas they made the core's own copper count as 279 violations)
    - the right-edge +3V3 column that joins the big +3V3 pour (pcb_build.py) becomes a no-go area
    - power pins: GND is done by pcb_gnd.py (every Link GND pad has its own via), so all GND pads get no
      net here; core +3V3/VBUS pins are already connected through pours, so they get no net except one
      tap each (TAPS), where the new 3.3 V and VBUS traces join"""
    import pcb_build
    b = pcbnew.LoadBoard(COPY)
    small = len(list(b.Zones()))      # small core pours stay as pours: Freerouting won't cross them
    keep = []
    inset = 0.3
    # no-go areas (rectangles, mm): x0, y0, x1, y1, layer
    nogo = [
        (pcb_build.X1 - inset - 1.0, pcb_build.Y0 + inset, pcb_build.X1 - inset, pcb_build.Y1 - inset, pcbnew.F_Cu),  # +3V3 edge column
        (92.5, 80.0, 112.0, 115.0, pcbnew.B_Cu),     # bottom under the core: keep the GND pour whole
        (100.7, 82.0, 106.0, 96.4, pcbnew.F_Cu),     # +3V3 pour feeding U1's top +3V3 pins, right of USB D+/D-
        (pcb_build.X0, pcb_build.Y0, pcb_build.X0 + 0.7, pcb_build.Y1, pcbnew.F_Cu),   # keep vias off the left edge
        (pcb_build.X0, pcb_build.Y0, pcb_build.X0 + 0.7, pcb_build.Y1, pcbnew.B_Cu),
    ]
    for xa, ya, xb, yb, layer in nogo:
        z = pcbnew.ZONE(b)
        z.SetIsRuleArea(True)
        z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(False); z.SetDoNotAllowZoneFills(False)
        z.SetLayer(layer)
        o = z.Outline(); o.NewOutline()
        for x, y in ((xa, ya), (xb, ya), (xb, yb), (xa, yb)):
            o.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
        b.Add(z); keep.append(z)
    hidden = 0
    for fp in b.GetFootprints():
        new = fp.GetReference() in pcb_build.PLACE
        for pad in fp.Pads():
            n = pad.GetNetname()
            if n == 'GND' or (not new and n in TAPS and (fp.GetReference(), pad.GetNumber()) != TAPS[n]):
                pad.SetNetCode(0)
                hidden += 1
    b.Save(COPY)
    print('copy: small core pours kept', small, '; no-go areas', len(nogo), '; power pins hidden:', hidden)


def export():
    b = pcbnew.LoadBoard(COPY)
    ok = pcbnew.ExportSpecctraDSN(b, DSN)
    print('dsn export:', ok)


def importses():
    b = pcbnew.LoadBoard(PCB)
    ok = pcbnew.ImportSpecctraSES(b, SES)
    widened = 0
    for t in b.GetTracks():        # Freerouting necks down near small pins; we want >= MIN_W everywhere
        if t.Type() != pcbnew.PCB_VIA_T and not t.IsLocked() and t.GetWidth() < pcbnew.FromMM(MIN_W):
            t.SetWidth(pcbnew.FromMM(MIN_W))
            widened += 1
    b.Save(PCB)
    print('ses import:', ok, 'widened to', MIN_W, 'mm:', widened)


def fill():
    b = pcbnew.LoadBoard(PCB)
    b.SynchronizeNetsAndNetClasses(True)
    b.BuildConnectivity()
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PCB)
    print('zones refilled')


def drc_open():
    """Unconnected items + copper errors after routing (kicad-cli DRC on the real board)."""
    import json, tempfile
    out = os.path.join(tempfile.mkdtemp(), 'drc.json')
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '-o', out, PCB], capture_output=True)
    d = json.load(open(out))
    errors = [v for v in d['violations'] if v['severity'] == 'error']
    return len(d.get('unconnected_items', [])) + len(errors)


def main(passes, attempts=6):
    """Freerouting is not deterministic: route, check with DRC, and retry from the same start until clean."""
    import shutil
    me = [sys.executable, os.path.abspath(__file__)]
    os.makedirs(WORK, exist_ok=True)
    start = os.path.join(WORK, 'pre-route.kicad_pcb')
    shutil.copy(PCB, start)
    best = None
    for attempt in range(1, attempts + 1):
        shutil.copy(start, PCB)
        shutil.copy(PCB, COPY)
        for step in ('prep', 'prep2', 'export'):
            subprocess.run(me + [step], check=True, capture_output=True)
        log = open(os.path.join(WORK, 'freerouting.log'), 'w')
        subprocess.run([JAVA, '-jar', JAR, '-de', DSN, '-do', SES, '-mp', str(passes), '--gui.enabled=false'],
                       stdout=log, stderr=subprocess.STDOUT)
        if not os.path.exists(SES):
            continue
        for step in ('importses', 'tidy', 'fill'):
            subprocess.run(me + [step], check=True, capture_output=True)
        n = drc_open()
        print(f'attempt {attempt}: {n} open connections / DRC errors')
        if best is None or n < best[0]:
            best = (n, open(PCB).read())
        if n == 0:
            break
    open(PCB, 'w').write(best[1])
    print('kept the best result:', best[0], 'open/errors')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] in ('hand', 'prep', 'prep2', 'export', 'importses', 'tidy', 'fill'):
        globals()[sys.argv[1]]()
    else:
        main(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
