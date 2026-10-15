#!/usr/bin/env python3
"""Pin-by-pin audit of every placed part against the JLC/LCSC part record we order (EasyEDA symbol of the LCSC
number: pin number -> pin name). Our side: the schematic netlist (pin number -> our symbol's pin function + net).
Prints, per part, every pin whose names do not obviously agree after normalisation, for review; 2-pin passives
are skipped. Polarised 2-pin parts (diodes, tantalum caps, LEDs) ARE checked (anode/cathode, +/-).
Usage: pin_audit.py NETLIST.xml BOM_JLC.csv [--all]"""
import csv, json, os, re, subprocess, sys, xml.etree.ElementTree as ET

CACHE = os.environ.get('EASYEDA_CACHE', '/tmp/easyeda_cache')
PROXY = {}


def easyeda(lcsc):
    f = os.path.join(CACHE, f'{lcsc}.json')
    if not os.path.exists(f):
        url = f'https://lceda.cn/api/products/{lcsc}/components?version=6.4.19.5'
        out = subprocess.run(['curl', '-s', '-m', '30', '-A', 'Mozilla/5.0', url], capture_output=True, text=True).stdout
        try:
            json.dump(json.loads(out), open(f, 'w'))
        except Exception:
            return None
    d = json.load(open(f))
    return d.get('result') if d.get('success', True) else None


def sym_pins(res):
    pins = {}
    shapes = res['dataStr']['shape']
    for s in shapes:
        if not s.startswith('P~'):
            continue
        segs = s.split('^^')
        head = segs[0].split('~')
        num = head[3]
        name = segs[3].split('~')[4] if len(segs) > 3 and len(segs[3].split('~')) > 4 else ''
        pins[num] = name
    return pins


def norm(n):
    n = n.upper().replace('#', 'N').replace('/', '').replace('_', '').replace('-', '').replace(' ', '')
    n = re.sub(r'^(EP|EPAD|PAD|THERMALPAD|TAB)$', 'GND', n)
    n = {'VSS': 'GND', 'AGND': 'GND', 'PGND': 'GND', 'DGND': 'GND', 'K': 'CATHODE', 'KA': 'CATHODE', 'C': 'CATHODE',
         'A': 'ANODE', '+': 'PLUS', '-': 'MINUS', 'VCC': 'VDD', 'V+': 'VDD', 'V': 'VDD'}.get(n, n)
    return n


def main():
    netlist, bom_csv = sys.argv[1:3]
    t = ET.parse(netlist).getroot()
    ours = {}
    for net in t.iter('net'):
        for node in net.iter('node'):
            ours.setdefault(node.get('ref'), {})[node.get('pin')] = (node.get('pinfunction') or '', net.get('name'))
    for r in csv.DictReader(open(bom_csv)):
        lc = r['LCSC Part #']
        for ref in r['Designator'].split(','):
            ref = ref.strip()
            kind = ref.rstrip('0123456789')
            pins = ours.get(ref, {})
            if len(pins) <= 2 and kind in ('R', 'L', 'F') and '--all' not in sys.argv:
                continue
            if len(pins) <= 2 and kind == 'C' and not r['Footprint'].startswith('CP_'):
                continue
            res = easyeda(lc)
            if not res:
                print(f'{ref:6} {lc:10} {r["Comment"][:20]:20} NO JLC SYMBOL DATA ({len(pins)} pins) -> check by datasheet'); continue
            ep = sym_pins(res)
            title = res.get('title', '')
            bad = []
            for num in sorted(set(pins) | set(ep), key=lambda x: (len(x), x)):
                a = ep.get(num); b = pins.get(num, ('', ''))
                if a is None or num not in pins:
                    bad.append(f'      pin {num:4} JLC "{a}"  ours "{b[0]}" net {b[1]}')
                    continue
                if norm(a) != norm(b[0]) and norm(a) not in norm(b[0]) and norm(b[0]) not in norm(a):
                    bad.append(f'      pin {num:4} JLC "{a}"  ours "{b[0]}"  net {b[1]}')
            status = 'ok  ' if not bad else 'LOOK'
            print(f'{status} {ref:6} {lc:10} {r["Comment"][:20]:20} JLC part "{title[:30]}" {len(ep)} pins vs our {len(pins)}')
            for b in bad:
                print(b)


if __name__ == '__main__':
    main()
