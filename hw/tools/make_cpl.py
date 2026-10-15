#!/usr/bin/env python3
"""JLC placement file (CPL) (adapted from the WiFi cart, ~/wifi-game-boy-cartridge/hw/rev-b/tools) with rotation/offset corrections DERIVED from the part JLC will actually place
(KiCad Python). No guessed rotation table: for every BOM part the EasyEDA/JLC footprint of its LCSC number is
downloaded and its pads are matched against the KiCad footprint's pads by pad number:
  find delta in {0, 90, 180, 270} and offset c minimising |R(delta) E - (K + c)|   (E = JLC pads, K = KiCad pads,
  both in their own footprint frames), then CPL rotation = KiCad rotation + delta and the CPL centre is moved by c
  so JLC's origin lands where its pads match ours.
Parts whose pads cannot be matched by number (or whose residual > 0.05 mm) are listed as REVIEW: check them in
JLC's placement preview before paying. Coordinates as kicad-cli's pos export (mm, Y up, absolute).
Usage: make_cpl.py PCB BOM_CSV OUT_CSV [--report out.txt]"""
import csv, json, math, os, sys, time, urllib.request
import pcbnew

MIL10 = 0.254   # EasyEDA unit = 10 mil
# LCSC numbers without an EasyEDA footprint (404): use a part with the same JLC package footprint
PROXY = {}
# JLC pad number -> our pad number where the two libraries number a polarised part differently.
# KT-0805G C2297: JLC/EasyEDA symbol pin 1 = A, pin 2 = K (pin_audit.py); KiCad LED_0805 pad 1 = K, pad 2 = A.
PAD_MAP = {'C2297': {'1': '2', '2': '1'}}
NONPOLAR = ('R', 'C', 'L', 'F')   # 2-pad parts whose orientation only matters modulo 180 deg (not CP_ footprints)


def easyeda_pads(lcsc, cache={}):
    if lcsc in cache:
        return cache[lcsc]
    url = f'https://easyeda.com/api/products/{lcsc}/components?version=6.4.19.5'
    import subprocess   # curl: KiCad's bundled Python has no CA bundle
    cdir = os.environ.get('EASYEDA_CACHE', '/tmp/easyeda_cache'); os.makedirs(cdir, exist_ok=True)
    cf = os.path.join(cdir, f'{lcsc}.json')
    if os.path.exists(cf):
        d = json.load(open(cf))
    else:
        time.sleep(1.5)                       # be gentle: EasyEDA rate-limits with HTTP 403
        for u in (url, url.replace('https://easyeda.com', 'https://lceda.cn')):   # same data; lceda.cn when easyeda.com rate-limits
            r = subprocess.run(['curl', '-s', '-m', '30', '-A', 'Mozilla/5.0', '-w', '\\n%{http_code}', u], capture_output=True, text=True).stdout
            body, code = r.rsplit('\n', 1)
            if code == '200':
                break
        if code != '200':
            print(f'  easyeda {lcsc}: HTTP {code}', file=sys.stderr); cache[lcsc] = None; return None
        d = json.loads(body); json.dump(d, open(cf, 'w'))
    try:
        ds = d['result']['packageDetail']['dataStr']
    except (KeyError, TypeError):
        cache[lcsc] = None; return None
    ox, oy = float(ds['head']['x']), float(ds['head']['y'])
    pads = {}
    for s in ds['shape']:
        if s.startswith('PAD~'):
            f = s.split('~')
            x, y, num = float(f[2]), float(f[3]), f[8]
            pads.setdefault(num, []).append(((x - ox) * MIL10, (y - oy) * MIL10))
    cache[lcsc] = (d['result']['packageDetail'].get('title'), pads)
    return cache[lcsc]


def rot(p, deg):
    """KiCad's rotation of a local offset (y down, positive angle = counter-clockwise on screen)."""
    a = math.radians(deg); x, y = p
    return (x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a))


def main():
    pcb, bom_csv, out = sys.argv[1:4]
    rep_path = sys.argv[sys.argv.index('--report') + 1] if '--report' in sys.argv else None
    b = pcbnew.LoadBoard(pcb)
    bom = {}
    for r in csv.DictReader(open(bom_csv)):
        for ref in r['Designator'].split(','):
            bom[ref.strip()] = r['LCSC Part #']
    rows, report, review = [], [], []
    per_fp = {}
    for f in b.GetFootprints():
        ref = f.GetReference()
        if ref not in bom:
            continue
        lc = bom[ref]
        th = f.GetOrientationDegrees()
        P = f.GetPosition()
        side = 'top' if f.GetLayer() == pcbnew.F_Cu else 'bottom'
        K = {}
        for p in f.Pads():
            q = p.GetFPRelativePosition()
            K.setdefault(p.GetNumber(), []).append((q.x / 1e6, q.y / 1e6))
        # self-check of the rotation convention against KiCad's own placement
        p0 = next(iter(f.Pads()))
        q = p0.GetFPRelativePosition(); rq = rot((q.x / 1e6, q.y / 1e6), th)
        if side == 'top' and math.hypot(P.x / 1e6 + rq[0] - p0.GetPosition().x / 1e6, P.y / 1e6 + rq[1] - p0.GetPosition().y / 1e6) > 1e-3:
            sys.exit(f'rotation convention check failed at {ref}')
        key = (f.GetFPID().GetLibItemName().wx_str(), lc)
        if key not in per_fp:
            e = easyeda_pads(lc) or (easyeda_pads(PROXY[lc]) if lc in PROXY else None)
            best = None
            if e:
                title, E = e
                if lc in PAD_MAP:
                    E = {PAD_MAP[lc].get(n, n): v for n, v in E.items()}
                    title += ' (pads renumbered A/K)'
                common = [n for n in K if n in E and n not in ('', '0') and len(K[n]) == len(E[n])]
                if len(common) >= 2:
                    scores = []
                    for d in (0, 90, 180, 270):
                        # c = mean(R(d) E - K) over matched pads (pads with the same number: mean position)
                        diffs = []
                        for n in common:
                            ex = sum(v[0] for v in E[n]) / len(E[n]); ey = sum(v[1] for v in E[n]) / len(E[n])
                            kx = sum(v[0] for v in K[n]) / len(K[n]); ky = sum(v[1] for v in K[n]) / len(K[n])
                            r = rot((ex, ey), d); diffs.append((r[0] - kx, r[1] - ky))
                        cx = sum(v[0] for v in diffs) / len(diffs); cy = sum(v[1] for v in diffs) / len(diffs)
                        res = max(math.hypot(v[0] - cx, v[1] - cy) for v in diffs)
                        scores.append((res, d, (cx, cy)))
                    scores.sort()
                    res, d, cxy = scores[0]
                    margin = scores[1][0] - res
                    best = (d, res, cxy, title + (f' (proxy {PROXY[lc]})' if lc in PROXY and not easyeda_pads(lc) else ''), len(common), margin)
            per_fp[key] = best
        best = per_fp[key]
        if best is None:
            d, c, note = 0, (0.0, 0.0), 'REVIEW: JLC footprint not matchable by pad number, KiCad rotation used'
        else:
            d, res, c, title, n, margin = best
            nonpolar = ref.rstrip('0123456789') in NONPOLAR and len(K) == 2 and not key[0].startswith('CP_')
            ok = margin > 0.3 or (nonpolar and d in (0, 180))
            note = f'{title}: {n} pads, fit {res:.3f} mm, next-best rotation {margin:+.3f} mm worse' + ('' if ok else ' REVIEW')
        # JLC origin goes where our pads say: M = P + R(theta) * (-c)   (c is JLC origin minus KiCad origin, JLC frame)
        cc = rot((-c[0], -c[1]), th)
        mx, my = P.x / 1e6 + cc[0], P.y / 1e6 + cc[1]
        r_out = (th + d) % 360
        rows.append([ref, f'{mx:.4f}mm', f'{-my:.4f}mm', 'Top' if side == 'top' else 'Bottom', f'{r_out:.1f}'])
        report.append(f"{ref:6} {lc:10} {key[0][:38]:38} rot {th:6.1f} + {d:3d} = {r_out:5.1f}  shift ({-c[0]:+.3f},{-c[1]:+.3f}) mm  {note}")
        if 'REVIEW' in note:
            review.append(ref)
    rows.sort(key=lambda r: (r[0].rstrip('0123456789'), int(''.join(ch for ch in r[0] if ch.isdigit()) or 0)))
    with open(out, 'w', newline='') as fo:
        w = csv.writer(fo); w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        w.writerows(rows)
    missing = sorted(set(bom) - {r[0] for r in rows})
    txt = [f'CPL: {len(rows)} parts, missing from board: {missing or "-"}, to review in JLC preview: {review or "-"}', ''] + sorted(report)
    if rep_path:
        open(rep_path, 'w').write('\n'.join(txt) + '\n')
    print('\n'.join(txt))
    sys.exit(1 if missing else 0)


if __name__ == '__main__':
    main()
