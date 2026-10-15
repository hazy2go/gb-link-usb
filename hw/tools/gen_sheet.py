#!/usr/bin/env python3
"""Generate a hierarchical sheet from a JSON netlist (here: the Link sheet, hw/rev-a/link.json).
Adapted from ~/wifi-game-boy-cartridge/hw/rev-b/tools/gen_radio_sheet.py.

Every symbol pin gets a label (global for shared nets, local for sheet-internal nets) or a power
symbol, so connectivity comes 100% from the JSON netlist and ERC can check it. The same JSON
drives the PCB footprint/net assignment, so schematic and board cannot drift apart.

Usage: gen_sheet.py NETLIST.json OUT.kicad_sch ROOT_UUID SHEET_UUID PROJECT_NAME
"""
import json, os, sys, uuid
from sexp import parse, dump, Str, find, first

KICAD_SYM = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols'
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ_SYM = None

POWER_NETS = {'GND': 'power:GND', 'VCC': 'power:VCC', 'VBUS': 'power:VBUS', '+3V3': 'power:+3V3'}
_lib_cache = {}


def lib_file(lib):
    return os.path.join(KICAD_SYM, lib + '.kicad_sym')


def load_lib(lib):
    if lib not in _lib_cache:
        tree = parse(open(lib_file(lib)).read())
        _lib_cache[lib] = {s[1]: s for s in find(tree, 'symbol')}
    return _lib_cache[lib]


def resolve_symbol(lib_id):
    """Return a flattened symbol definition named lib_id (handles 'extends')."""
    lib, name = lib_id.split(':', 1)
    syms = load_lib(lib)
    sym = syms[name]
    ext = first(sym, 'extends')
    if ext:
        base = resolve_symbol(f'{lib}:{ext[1]}')
        props = {p[1]: p for p in find(sym, 'property')}
        out = [x for x in base if not (isinstance(x, list) and x and x[0] == 'property' and x[1] in props)]
        out += list(props.values())
        # rename sub-units from base name to this name
        bname = ext[1]
        res = []
        for x in out:
            if isinstance(x, list) and x and x[0] == 'symbol' and isinstance(x[1], str) and x[1].startswith(bname + '_'):
                x = [x[0], Str(name + x[1][len(bname):])] + x[2:]
            res.append(x)
        out = res
        out[1] = Str(lib_id)
        return out
    sym = list(sym)
    sym[1] = Str(lib_id)
    return sym


def pins_of(sym):
    """{pin_number: [(unit, x, y, angle)]} from a resolved symbol (lib coordinates, y up)."""
    res = {}
    for sub in find(sym, 'symbol'):
        parts = sub[1].rsplit('_', 2)
        unit = int(parts[-2])
        for p in find(sub, 'pin'):
            at = first(p, 'at')
            num = first(p, 'number')[1]
            res.setdefault(str(num), []).append((unit, float(at[1]), float(at[2]), int(float(at[3])) if len(at) > 3 else 0))
    return res


def units_of(sym):
    us = set()
    for sub in find(sym, 'symbol'):
        us.add(int(sub[1].rsplit('_', 2)[-2]))
    us.discard(0)
    return sorted(us) or [1]


_NS = uuid.UUID('c41e8f2a-6d3b-4f19-9a7e-2b5c8d0e1f63')
_n = [0]


def U():
    """Deterministic UUIDs: regenerating the sheet gives an identical file when nothing changed."""
    _n[0] += 1
    return Str(str(uuid.uuid5(_NS, f'item/{_n[0]}')))


def SU(ref, unit):
    """Symbol UUID from reference + unit, stable across regenerations: the PCB links footprints to it."""
    return Str(str(uuid.uuid5(_NS, f'symbol/{ref}/{unit}')))


def prop(name, value, x, y, hide=False, angle=0):
    p = ['property', Str(name), Str(value), ['at', round(x, 2), round(y, 2), angle],
         ['effects', ['font', ['size', 1.27, 1.27]]] + ([['hide', 'yes']] if hide else [])]
    return p


def main(netlist_path, out_path, root_uuid, sheet_uuid, project):
    data = json.load(open(netlist_path))
    parts = data['parts']
    lib_symbols, used = [], {}
    items = []
    inst_path = f'/{root_uuid}/{sheet_uuid}'
    col_w, per_row = 63.5, 6
    x0, y0 = 25.4, 30.48
    # row layout: each row is as tall as its tallest symbol plus room for labels and fields
    ext = []
    for part in parts:
        ys = [py for lst in pins_of(resolve_symbol(part['symbol'])).values() for (_u, _x, py, _a) in lst] or [0]
        ext.append((min(ys), max(ys)))
    row_top, top = [], y0
    for r in range(0, len(parts), per_row):
        row_top.append(top)
        top += max(hi - lo for lo, hi in ext[r:r + per_row]) + 30.48
    flags_y = top
    power_count = 0
    shared = set(data.get('global_nets', []))

    def need_symbol(lib_id):
        if lib_id not in used:
            used[lib_id] = resolve_symbol(lib_id)
            lib_symbols.append(used[lib_id])
        return used[lib_id]

    for i, part in enumerate(parts):
        lib_id = part['symbol']
        sym = need_symbol(lib_id)
        pmap = pins_of(sym)
        units = units_of(sym)
        missing = set(part['pins']) - set(pmap)
        if missing:
            sys.exit(f"{part['ref']}: pins {sorted(missing)} not in symbol {lib_id}")
        for k, unit in enumerate(units):
            gx = x0 + (i % per_row) * col_w + k * 20.32
            gy = row_top[i // per_row] + 12.7 + ext[i][1]   # top pin 12.7 mm below the row top (lib y is up)
            sx, sy = round(gx / 2.54) * 2.54, round(gy / 2.54) * 2.54
            inst = ['symbol', ['lib_id', Str(lib_id)], ['at', round(sx, 2), round(sy, 2), 0], ['unit', unit],
                    ['exclude_from_sim', 'no'], ['in_bom', 'yes'], ['on_board', 'yes'], ['dnp', 'no'], ['uuid', SU(part['ref'], unit)],
                    prop('Reference', part['ref'], sx, sy - 12, False),
                    prop('Value', part['value'], sx, sy + 12, False),
                    prop('Footprint', part.get('footprint', ''), sx, sy, True),
                    prop('Datasheet', part.get('datasheet', ''), sx, sy, True),
                    prop('Description', part.get('description', ''), sx, sy, True),
                    prop('LCSC', part.get('lcsc', ''), sx, sy, True)]
            for num, net in part['pins'].items():
                for (u, px, py, ang) in pmap[num]:
                    if u not in (0, unit):
                        continue
                    if u == 0 and k > 0:
                        continue
                    inst.append(['pin', Str(num), ['uuid', U()]])
                    wx, wy = round(sx + px, 2), round(sy - py, 2)
                    lab_ang = (ang + 180) % 360
                    if net in ('NC', None, ''):
                        items.append(['no_connect', ['at', wx, wy], ['uuid', U()]])
                    elif net in POWER_NETS:
                        psym = need_symbol(POWER_NETS[net])
                        power_count += 1
                        # power symbols connect at their (0,0) pin; GND points down, others up
                        items.append(['symbol', ['lib_id', Str(POWER_NETS[net])], ['at', wx, wy, 0], ['unit', 1],
                                      ['exclude_from_sim', 'no'], ['in_bom', 'yes'], ['on_board', 'yes'], ['dnp', 'no'],
                                      ['uuid', U()],
                                      prop('Reference', f'#PWR0{2000 + power_count}', wx, wy + 5, True),
                                      prop('Value', net, wx, wy + 3, True),
                                      prop('Footprint', '', wx, wy, True), prop('Datasheet', '', wx, wy, True),
                                      prop('Description', '', wx, wy, True),
                                      ['pin', Str('1'), ['uuid', U()]],
                                      ['instances', ['project', Str(project), ['path', Str(inst_path),
                                                                                ['reference', Str(f'#PWR0{2000 + power_count}')],
                                                                                ['unit', 1]]]]])
                    else:
                        kind = 'global_label' if net in shared else 'label'
                        lab = [kind, Str(net)]
                        if kind == 'global_label':
                            lab += [['shape', 'passive']]
                        lab += [['at', wx, wy, lab_ang], ['fields_autoplaced', 'yes'],
                                ['effects', ['font', ['size', 1.0, 1.0]], ['justify', 'left' if lab_ang in (0, 90) else 'right']],
                                ['uuid', U()]]
                        if kind == 'global_label':
                            lab.append(['property', Str('Intersheetrefs'), Str('${INTERSHEET_REFS}'), ['at', wx, wy, 0],
                                        ['effects', ['font', ['size', 1.0, 1.0]], ['hide', 'yes']]])
                        items.append(lab)
            # unconnected pins defined by the symbol but absent from the JSON are a hard error
            for num, lst in pmap.items():
                if num not in part['pins'] and any(u in (0, unit) for (u, *_r) in lst):
                    if not (k > 0 and all(u == 0 for (u, *_r) in lst)):
                        sys.exit(f"{part['ref']}: pin {num} of {lib_id} has no net in JSON (use 'NC')")
            inst.append(['instances', ['project', Str(project), ['path', Str(inst_path), ['reference', Str(part['ref'])], ['unit', unit]]]])
            items.append(inst)

    # PWR_FLAG on nets that are powered through passive parts only (e.g. VRES behind the PMOS pair), so ERC
    # knows they are driven; listed explicitly in the JSON, never inferred
    for j, net in enumerate(data.get('power_flags', [])):
        need_symbol('power:PWR_FLAG')
        fx, fy = round((x0 + j * 25.4) / 2.54) * 2.54, round((flags_y + 10.16) / 2.54) * 2.54
        power_count += 1
        items.append(['symbol', ['lib_id', Str('power:PWR_FLAG')], ['at', fx, fy, 0], ['unit', 1],
                      ['exclude_from_sim', 'no'], ['in_bom', 'yes'], ['on_board', 'yes'], ['dnp', 'no'], ['uuid', U()],
                      prop('Reference', f'#FLG0{200 + j}', fx, fy - 5, True), prop('Value', 'PWR_FLAG', fx, fy - 3, False),
                      prop('Footprint', '', fx, fy, True), prop('Datasheet', '', fx, fy, True),
                      prop('Description', '', fx, fy, True), ['pin', Str('1'), ['uuid', U()]],
                      ['instances', ['project', Str(project), ['path', Str(inst_path), ['reference', Str(f'#FLG0{200 + j}')], ['unit', 1]]]]])
        kind = 'global_label' if net in shared else 'label'
        lab = [kind, Str(net)] + ([['shape', 'passive']] if kind == 'global_label' else [])
        lab += [['at', fx, fy, 270], ['fields_autoplaced', 'yes'], ['effects', ['font', ['size', 1.0, 1.0]], ['justify', 'right']], ['uuid', U()]]
        if kind == 'global_label':
            lab.append(['property', Str('Intersheetrefs'), Str('${INTERSHEET_REFS}'), ['at', fx, fy, 0],
                        ['effects', ['font', ['size', 1.0, 1.0]], ['hide', 'yes']]])
        items.append(lab)

    sch = ['kicad_sch', ['version', 20250114], ['generator', Str('eeschema')], ['generator_version', Str('9.0')],
           ['uuid', Str(sheet_uuid)], ['paper', Str('A3')],
           ['title_block', ['title', Str(data.get('title', 'Sheet'))], ['rev', Str(data.get('rev', 'A'))],
            ['comment', 1, Str('Generated by hw/tools/gen_sheet.py from ' + os.path.basename(netlist_path) + '. Do not hand-edit.')]],
           ['lib_symbols'] + lib_symbols] + items + [['sheet_instances', ['path', Str('/'), ['page', Str('1')]]]]
    open(out_path, 'w').write(dump(sch) + '\n')
    print(f'wrote {out_path}: {len(parts)} parts, {len(lib_symbols)} symbols, {len(items)} items')


if __name__ == '__main__':
    main(*sys.argv[1:6])
