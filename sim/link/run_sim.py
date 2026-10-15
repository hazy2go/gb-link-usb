#!/usr/bin/env python3
"""Link-line signal check for PCB rev A (ngspice). Every assumption is listed in sim/link/README.md.

Two directions, one edge each (rising and falling), swept over cable impedance, cable length and the Game Boy's
unknown driver strength:
  to_gb   U104 B output (5 V, ~20 ohm) -> R106 33R -> TPD4E05U06 (0.5 pF) -> cable -> Game Boy input (10 pF)
  from_gb Game Boy output (R_gb) -> cable -> TPD4E05U06 + 100k pull-up -> R105 33R -> U103 B input (6 pF)
Checks per run, at the receiving pin:
  - peak / dip within the receiver's absolute maximum (-0.5 V .. 6.5 V for the LVC1T45 B input; for the Game
    Boy input we report it against 5.5 V, a common CMOS VCC + 0.5 V limit, verify)
  - glitch: after the edge first crosses the far threshold (VIH for rising, VIL for falling), does it cross back
    through the opposite threshold? Reported as the length of the disturbed window, which must be far below the
    firmware's 1.6 us glitch filter (gb_link.pio) and the ~61 us half-bit of the Game Boy clock.
  - settle: time from the source edge until the pin stays inside its final logic region.
Clamps: the Game Boy input gets the usual CMOS diodes to its 5 V and to GND (verify); the LVC1T45 B input has
only a diode to GND (datasheet: IIK for VI < 0; overvoltage tolerant, no diode to VCC); the TPD4E05U06 is a
diode to GND plus breakdown at its maximum VBR 8.5 V (worst case for what reaches the LVC input).
The series resistor (R104-R106) is swept: 0, 33 (rev A as drawn), 100, 220, 470 ohm.
Usage: python3 sim/link/run_sim.py   (writes sim/link/results.txt)"""
import itertools, os, subprocess, tempfile

VCC = 5.0
TD_PER_M = 5.0e-9          # s/m, typical for PVC-insulated cable (velocity ~0.66 c)
Z0S = (60, 100, 150)       # ohm
LENS = (0.3, 1.0, 2.0)     # m: our built-in half cable is <= 1 m; 2 m = plus an extension (verify)
RGB = (30, 100, 300)       # ohm: Game Boy CPU output driver, unknown (verify)
R_LVC = 20                 # ohm: LVC1T45 B port at 4.5 V: VOH >= 3.8 V at -32 mA, VOL <= 0.55 V at 32 mA
TR_LVC, TR_GB = 1.5e-9, 10e-9
C_TPD, C_LVC, C_GB = 0.5e-12, 6e-12, 10e-12
R_PULL = 100e3
VIH, VIL = 0.7 * VCC, 0.3 * VCC
FILTER = 1.6e-6
RS_LIST = (0, 33, 100, 220, 470)
C_IN = (0, 100e-12)          # extra capacitor at the LVC1T45 B input (C107/C108 on rev A); to_gb has none
MODELS = '.model DCL D(IS=1e-14 N=1 RS=2)\n.model DTPD D(IS=1e-14 N=1 RS=1 BV=8.5 IBV=1m)\n'
T_EDGE = 20e-9


def netlist(direction, z0, length, rs, rgb, rising, cin=0.0):
    td = length * TD_PER_M
    v0, v1 = (0, VCC) if rising else (VCC, 0)
    tr = TR_LVC if direction == 'to_gb' else TR_GB
    src = f"Vs src 0 PWL(0 {v0} {T_EDGE} {v0} {T_EDGE + tr} {v1})"
    if direction == 'to_gb':
        body = f"""Rdrv src a {R_LVC}
Rs a b {max(rs, 1e-3)}
Ctpd b 0 {C_TPD}
T1 b 0 far 0 Z0={z0} TD={td}
Cgb far 0 {C_GB}
Rgbin far 0 1Meg
Dgb_hi far vgb DCL
Dgb_lo 0 far DCL
Vgb vgb 0 {VCC}
Dtpd 0 b DTPD
"""
        probe = 'far'
    else:
        body = f"""Rdrv src a {rgb}
T1 a 0 near 0 Z0={z0} TD={td}
Ctpd near 0 {C_TPD}
Rpu near vcc {R_PULL}
Vcc vcc 0 {VCC}
Rs near b {max(rs, 1e-3)}
Clvc b 0 {C_LVC + cin}
Dlvc 0 b DCL
Dtpd 0 near DTPD
"""
        probe = 'b'
    return f"""* {direction}
{MODELS}{src}
{body}
.tran 0.05n 600n
.control
run
wrdata {{OUT}} v({probe})
.endc
.end
""", probe


def run(direction, z0, length, rs, rgb, rising, cin=0.0):
    net, _ = netlist(direction, z0, length, rs, rgb, rising, cin)
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, 'o.txt')
        cir = os.path.join(d, 'c.cir')
        open(cir, 'w').write(net.replace('{OUT}', out))
        subprocess.run(['ngspice', '-b', cir], capture_output=True, check=True)
        rows = [tuple(map(float, l.split()[:2])) for l in open(out) if l.strip()]
    t = [r[0] for r in rows]; v = [r[1] for r in rows]
    far, back = (VIH, VIL) if rising else (VIL, VIH)
    beyond = (lambda x: x >= far) if rising else (lambda x: x <= far)
    wrong = (lambda x: x <= back) if rising else (lambda x: x >= back)
    final = (lambda x: x >= VIH) if rising else (lambda x: x <= VIL)
    first = next((i for i, x in enumerate(v) if beyond(x)), None)
    glitch = 0.0
    if first is not None:
        bad = [t[i] for i in range(first, len(v)) if wrong(v[i])]
        glitch = (bad[-1] - t[first]) if bad else 0.0
    last_out = max((t[i] for i in range(len(v)) if not final(v[i])), default=0.0)
    return dict(vmax=max(v), vmin=min(v), glitch=glitch, settle=last_out - T_EDGE, ok_end=final(v[-1]))


def main():
    lines, worst = [], {}
    for direction in ('to_gb', 'from_gb'):
        rgbs = RGB if direction == 'from_gb' else (None,)
        cins = C_IN if direction == 'from_gb' else (0.0,)
        for z0, length, rgb, rs, cin, rising in itertools.product(Z0S, LENS, rgbs, RS_LIST, cins, (True, False)):
            r = run(direction, z0, length, rs, rgb, rising, cin)
            lim_hi = 6.5 if direction == 'from_gb' else 5.5
            fail = r['vmax'] > lim_hi or r['vmin'] < -0.5 or r['glitch'] > FILTER / 10 or not r['ok_end']
            tag = 'FAIL' if fail else 'ok  '
            lines.append(f"{tag} {direction:7} Z0 {z0:3} len {length:3.1f} m Rgb {str(rgb):4} Rs {rs:3} C {cin*1e12:3.0f}p {'rise' if rising else 'fall'}  "
                         f"max {r['vmax']:5.2f} V min {r['vmin']:5.2f} V  glitch {r['glitch']*1e9:6.1f} ns  settle {r['settle']*1e9:6.1f} ns")
            k = (direction, rs, round(cin * 1e12))
            w = worst.setdefault(k, dict(vmax=-9, vmin=9, glitch=0, settle=0, fails=0, n=0))
            w['vmax'] = max(w['vmax'], r['vmax']); w['vmin'] = min(w['vmin'], r['vmin'])
            w['glitch'] = max(w['glitch'], r['glitch']); w['settle'] = max(w['settle'], r['settle'])
            w['fails'] += fail; w['n'] += 1
    summary = ['Worst case per direction (limits: from_gb -0.5..6.5 V = LVC1T45 abs max; to_gb -0.5..5.5 V assumed for the Game Boy;',
               f'glitch must stay below {FILTER/10*1e9:.0f} ns = 1/10 of the 1.6 us PIO glitch filter)']
    for (d, rs, c), w in sorted(worst.items()):
        mark = '  <- rev A' if (rs, c) == (220, 100 if d == 'from_gb' else 0) else ('  <- first draft' if (rs, c) == (33, 0) else '')
        summary.append(f"  {d:7} Rs {rs:3} C {c:3}p: max {w['vmax']:5.2f} V  min {w['vmin']:5.2f} V  glitch {w['glitch']*1e9:6.1f} ns  "
                       f"settle {w['settle']*1e9:6.1f} ns  fails {w['fails']}/{w['n']}{mark}")
    txt = '\n'.join(summary + [''] + lines) + '\n'
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results.txt'), 'w').write(txt)
    print('\n'.join(summary))


if __name__ == '__main__':
    main()
