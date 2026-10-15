#!/usr/bin/env python3
"""Rebuild hw/rev-a: root from the Raspberry Pi minimal design (edit_root.py) + the generated Link sheet.

Usage: add_sheet.py   (run from anywhere)
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REV = os.path.join(HERE, '..', 'rev-a')
REF = os.path.join(HERE, '..', 'reference', 'RPI-RP2350A-MINIMAL_R4-S1_public', 'RPI-RP2350A-MINIMAL_R4-S1.kicad_sch')
ROOT = os.path.join(REV, 'gb-link-usb.kicad_sch')
PROJECT = 'gb-link-usb'
SHEET_UUID = '7d2e4b91-3c5a-4e8f-b6d0-9a1c2e3f4b58'   # fixed so regeneration keeps references stable

SHEET_BLOCK = f'''	(sheet
		(at 25.4 200)
		(size 40 20)
		(exclude_from_sim no)
		(in_bom yes)
		(on_board yes)
		(dnp no)
		(fields_autoplaced yes)
		(stroke (width 0.1524) (type solid))
		(fill (color 0 0 0 0.0000))
		(uuid "{SHEET_UUID}")
		(property "Sheetname" "Link" (at 25.4 199.2 0) (effects (font (size 1.27 1.27)) (justify left bottom)))
		(property "Sheetfile" "link.kicad_sch" (at 25.4 220.6 0) (effects (font (size 1.27 1.27)) (justify left top)))
		(instances (project "{PROJECT}" (path "/ROOTUUID" (page "2"))))
	)
'''


def main():
    py = sys.executable
    subprocess.run([py, os.path.join(HERE, 'edit_root.py'), REF, ROOT], check=True)
    s = open(ROOT).read()
    root_uuid = s.split('(uuid "', 1)[1].split('"', 1)[0]
    i = s.index('\t(sheet_instances')
    s = s[:i] + SHEET_BLOCK.replace('ROOTUUID', root_uuid) + s[i:]
    s = s.replace('(title "RP2350A QFN-60 Minimal Design Example")', '(title "gb-link-usb rev A (core: Raspberry Pi RP2350A minimal design R4, MIT)")')
    open(ROOT, 'w').write(s)
    subprocess.run([py, os.path.join(HERE, 'gen_sheet.py'), os.path.join(REV, 'link.json'),
                    os.path.join(REV, 'link.kicad_sch'), root_uuid, SHEET_UUID, PROJECT], check=True)


if __name__ == '__main__':
    main()
