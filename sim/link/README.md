# Link-line simulation (PCB rev A)

`python3 sim/link/run_sim.py` (ngspice, `brew install ngspice`) writes `results.txt`. 846 transient runs.

## What it checks
One rising and one falling edge per run, at the receiving pin:
- **to_gb**: our U104 B output (5 V) -> R106 -> TPD4E05U06 -> cable -> Game Boy input.
- **from_gb**: Game Boy output -> cable -> TPD4E05U06 + 100k pull-up -> R105 (and C108) -> U103 B input. SCK in printer mode is the same path (R104, C107, U102).
- Peak and dip against the receiver's limit, re-crossing of the logic thresholds after the edge (glitch), settle time.

## Result (2026-10-16)
| design | to the Game Boy | from the Game Boy |
|---|---|---|
| first draft: 33R, no cap | 12/18 runs overshoot (up to 5.77 V, clamped by the Game Boy's diodes) | 14/54 runs above the LVC1T45's 6.5 V abs max (up to 8.4 V) |
| **rev A: 220R, 100 pF at the LVC input** | 0/18, max 5.00 V, settles in 53 ns | 0/54, max 5.00 V, settles in 130 ns |
| rev A SIN line (R106 = 1k, limits back-feed into a switched-off Game Boy) | 0/18, max 4.99 V, settles in 223 ns | (not on this line) |

No run shows a glitch (threshold re-crossing). 130 ns is far below the PIO glitch filter (1.6 us) and the Game Boy's half-bit (61 us at 8 kHz). Why: 220R plus the LVC1T45's ~20 ohm roughly matches the cable, so our edge arrives clean (source termination). In the other direction the Game Boy's driver and the cable are not ours to fix; 220R with 100 pF is a 22 ns low-pass in front of our input that removes the ringing.

## Assumptions (all marked verify unless sourced)
| item | value | source |
|---|---|---|
| LVC1T45 B output | 20 ohm, 1.5 ns edge | TI SCES515N: VOH >= 3.8 V at -32 mA, VOL <= 0.55 V at 32 mA, VCC 4.5 V |
| LVC1T45 B input | 6 pF, diode to GND only, abs max -0.5 .. 6.5 V, VIH/VIL 0.7/0.3 VCC | TI SCES515N (Cio, IIK, abs max, VIH/VIL) |
| TPD4E05U06 | 0.5 pF, VBR max 8.5 V | TI datasheet (IO capacitance 0.42-0.5 pF typ, VBR 6.5-8.5 V) |
| Game Boy driver | 30 / 100 / 300 ohm, 10 ns edge | unknown (verify); 30 ohm is a deliberately harsh case |
| Game Boy input | 10 pF, diodes to 5 V and GND, limit 5.5 V | typical CMOS (verify) |
| Cable | lossless, 60 / 100 / 150 ohm, 5 ns/m, 0.3 / 1 / 2 m | typical PVC cable (verify); our built-in cable is <= 1 m |
| Supply | 5.0 V | USB VBUS nominal |

Not modelled: crosstalk between the cable's wires (seen on the breadboard with no buffers; on rev A the 22 ns input filter and the 1.6 us PIO filter both act on it), cable loss (makes things better), board traces (< 25 mm, < 0.2 ns).
