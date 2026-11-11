# Solver calibration: copper resistance and loop inductance

Run 2026-11-11 in the cloud container. Gap 6 of the research synthesis: both home-made solvers read
optimistic, and no number from them should gate a design until that is fixed or bounded. Nothing here is
measured hardware.

## Summary

| Solver | Before | After | Use it for |
|---|---|---|---|
| DC copper resistance (`review-tools/solve.py`) | reads low by one grid cell of width: 5 % on a 2 mm strip, 17 % on a 0.5 mm neck, 1 to 10 % on Monolith's real power paths | within 0.2 % on straight copper at any grid from 0.05 to 0.2 mm; a 1 mm track at 45 degrees reads 4 % high at 0.1 mm | absolute limits |
| Loop inductance (`groundup/compare/peec.py`) | same one-cell error: plates 7 % low at 0.25 mm cells | plates within 2 to 4 % of an independent reference and stable with cell size | large plate-like loops: absolute. Small hot loops: bracket only, see below |

## DC copper solver

Cause: the rasteriser marked every cell the copper outline touches, so every strip was one cell too wide. Fix
(`build(..., aa=8)`, now the default): copper is drawn eight times finer than the grid, each cell keeps its
covered share, and an edge's conductance is scaled by the geometric mean of the two shares. `aa=1` is the old
behaviour.

| case | reference, mOhm | old, 0.2 / 0.1 / 0.05 mm grid | new, 0.2 / 0.1 / 0.05 mm grid |
|---|---|---|---|
| strip 2.0 mm | 6.068 (formula) | -8.9 % / -4.8 % / -2.3 % | +0.2 % / -0.0 % / +0.1 % |
| strip 1.0 mm | 12.136 (formula) | -16.4 % / -9.1 % / -4.6 % | +0.2 % / +0.0 % / +0.1 % |
| strip 0.5 mm | 24.272 (formula) | -37.3 % / -16.7 % / -9.0 % | +0.2 % / -0.0 % / +0.1 % |
| strip 0.3 mm | 40.453 (formula) | -24.8 % / -25.0 % / +0.1 % | +0.2 % / -0.0 % / +0.1 % |
| strip 0.5 mm, 0.037 mm off the grid | 24.272 (formula) | -37.3 % / -16.7 % / -9.0 % | +0.2 % / -0.0 % / +0.1 % |
| track 1.0 mm at 45 degrees | 9.824 (0.025 mm grid) | +73.2 % / -0.7 % / +7.1 % | +10.9 % / +3.6 % / +0.6 % |
| 4 mm strip with a 0.5 x 5 mm neck | 5.454 (0.025 mm grid) | -20.9 % / -9.6 % / -5.2 % | -0.1 % / -0.2 % / -0.1 % |

worst error at the 0.1 mm grid: old 25.0 %, new 3.6 %

Straight strips have a closed-form answer. The diagonal track and the neck are compared with the solver itself
on a 0.025 mm grid. The remaining error is on diagonals, where a square grid always reads a little high, which
is the safe direction.

Effect on the scripted Monolith board, 16 power paths (`real_paths.py`): every path goes up, by 0.8 to 9.8 %,
median 4.8 %. Largest: the two battery-side sense-resistor to FET paths, 0.58 to 0.64 mOhm.

## Loop inductance solver

Same cause, same kind of fix (`Model(..., centre=True)` or `PEEC_CENTRE=1`, now the default): zone and pad copper
counts only where it covers at least half the cell; tracks and vias keep every cell they touch so thin tracks
stay connected.

Reference. FastHenry is the usual reference. Its source downloaded, but building outside code was blocked in
this container, so the reference is `plates_reference.py`: an independent calculation of two parallel plates
with the current free to crowd to the edges (exact finite-length filament formula, up to 800 filaments), bounded
above by the uniform-current value, which is exact.

| Two plates, 10 mm wide, 18 mm between pads, 0.244 mm apart | nH |
|---|---|
| Reference: free current, 800 filaments (still rising slowly) | 0.499 |
| Reference: uniform current (upper bound) | 0.514 |
| Solver before, 0.5 / 0.25 mm cells | 0.461 / 0.473 |
| Solver after, 0.5 / 0.25 mm cells | 0.497 / 0.491 |

The research note's "10 to 20 % low" was mostly its hand value: it took the plate length as 19 to 20 mm and
ignored fringing. Against a proper reference the solver was about 7 % low and is now within 2 to 4 %.

**Small hot loops are not converged, with either rasteriser.** Port 1's 5 V buck loop on the scripted board,
all capacitors in parallel with their ESL (`hot_convergence.py`):

| Cell size | Old rasteriser | New rasteriser | Midpoint |
|---|---|---|---|
| 0.30 mm | 0.296 nH | 0.500 nH | 0.398 |
| 0.20 mm | 0.382 nH | 0.428 nH | 0.405 |
| 0.15 mm | 0.352 nH | 0.496 nH | 0.424 |

The old one reads low, the new one high, and neither settles as the cells shrink, because the pads and gaps of
this loop are the size of a cell. The 3.3 V buck loop moves less (1.22 to 1.35 nH at 0.3 mm). So for a loop
under about 1 nH the honest statement today is a bracket of roughly plus or minus 20 %, and the 0.30 to 0.56 nH
figures in the Battery-Bank comparison carry that uncertainty. Ranking two layouts is safe only when they
differ by more than the bracket.

## What this changes

- Copper-resistance numbers can gate a design. Regenerate any stored Battery-Bank value before comparing with it.
- A hot-loop limit must be checked against the high (new) value, and a comparison must quote both.
- Still needed: FastHenry on two or three real loops to say where inside the bracket the truth lies, and a
  sub-cell treatment of small pads in the loop solver. The coupling solver has not been tested.

## Run it

```
python3 dc_tests.py                                  # exit 1 if the new rasteriser is worse than 5 % at 0.1 mm
PCB=<board> python3 real_paths.py
python3 plates_reference.py
PCB=<board> PEEC_CENTRE=0|1 python3 hot_convergence.py 4 0.2
```

## Outside check against FastHenry2 (2026-11-11)

`fh_loops.py` writes three test loops made of rectangles, ideal shorts and one port, as FastHenry inputs and as
tiny boards for the loop solver, so both see the same copper. FastHenry2 3.6.1 ran them on Logan's PC at
100 MHz with default settings. The two via inputs needed the change FastHenry asks for (a via segment may not
end on a plane node, so a normal node is added and tied to it); `fh_loops.py` does not write that yet.

| Loop | FastHenry2, coarse / fine cells, nH | Loop solver, old rasteriser, nH | Loop solver, new rasteriser, nH |
|---|---|---|---|
| plates, 18 x 10 mm, two layers | 0.476 / 0.470 | 0.461 to 0.473 | 0.491 (0.25 mm); 0.606 (0.5 mm) |
| small, 1 x 3 mm strip over a plane | 0.468 / 0.454 | 0.443 to 0.469 | 0.518 to 0.572 |
| via, 2 x 6 mm strips and two vias | 0.650 / 0.671 | 0.592 to 0.659 | 0.696 to 0.722 |

Loop solver ranges are over cell sizes 0.3, 0.2, 0.15 and 0.1 mm (0.5 and 0.25 for the plates).

What it says:

- FastHenry lands at the low end of the bracket. The old rasteriser is within about 5 % of it at 0.2 mm cells
  and finer on all three loops. The new (centre) rasteriser reads 4 to 8 % high on the plates and the via loop,
  and 14 to 26 % high on the small loop.
- So the earlier "plus or minus 20 %, truth unknown" becomes: the truth is near the old value, and the new
  value is a safe upper bound. A hot-loop limit should still be checked against the new value. Comparisons
  between layouts should use the old one.
- The new rasteriser's jump at coarse cells (0.606 nH on the plates at 0.5 mm) is a grid-alignment error: the
  18.6 mm plate does not sit on a 0.5 mm grid. Loop work should use cells of 0.25 mm or less.
- FastHenry itself moved 1 to 3 % when its cells were halved, so these are good to a few percent, not exact.
- The vias in the loop solver agree with FastHenry's to within the same few percent.
- Still open: these loops have no capacitors or pads smaller than a cell, and the coupling solver is untested.
