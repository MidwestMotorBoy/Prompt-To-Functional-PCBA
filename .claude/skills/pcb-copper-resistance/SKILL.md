---
name: pcb-copper-resistance
description: Compute DC resistance, I²R loss, current density, per-via current and Kelvin sense-tap error of PCB copper straight from a .kicad_pcb with a 2-D grid solver over all layers. Use when sizing power paths, comparing layout fixes, checking current-sense routing, or feeding copper heat into a thermal model.
---

# PCB copper resistance and sense-tap analysis

A routed board's power paths are planes, pours and via fields, not single traces, so hand formulas are off by 2–10×. A grid solver over the real copper gives the resistance, where the current crowds, which via runs hot, and how far a sense line's reading is off. The repo copy is `docs/reviews/2026-10-30-routed-board/tools/` (`sx.py` S-expression parser, `board.py` loader, `solve.py` solver, `run2.py` path list). It needs numpy, scipy and Pillow.

```
cd docs/reviews/2026-10-30-routed-board/tools
python3 run2.py                                       # every path in its case table
PCB=/path/to/other.kicad_pcb python3 run2.py 0 1      # selected cases on another file
```

## Method

1. **Parse the board.** Footprints (pads rotated into board coordinates, with net, layers and drill), track segments, vias, and zone **filled polygons** (`filled_polygon` per layer, not the zone outline). Refill on a copy first if the fills might be stale.
2. **Rasterise one net**, layer by layer, onto a grid inside a box that holds the **whole** net. Use 0.1 mm normally and 0.03 mm when a gap under about 0.15 mm matters. Draw pads (rotated rectangles or circles), tracks (lines with round ends) and zone fills.
3. **Conductances.** On a square grid each neighbour link is one square, so its conductance is 1 / R_sheet.
   - R_sheet = ρ_Cu / t, with ρ_Cu = 1.72e-8 Ω·m: 0.5 oz (17.5 µm) = 0.983 mΩ/sq, 1 oz (35 µm) = 0.49 mΩ/sq, 2 oz (70 µm) = 0.246 mΩ/sq. Use the finished thickness of your fab's stack-up. Warm copper is about 0.4 %/K higher.
   - Vias and plated holes join the cells at their centre between each adjacent pair of layers present: R = ρ · Δz / (π · (d + t) · t), with d the drill and t the plating (about 20 µm), and Δz from the stack-up.
4. **Solve.** Build the sparse Laplacian G. Inject current I spread over the source pad's cells and tie the sink pad's cells to 0 V with a large conductance. Add a tiny leak to the diagonal so isolated islands don't make G singular, then solve G·V = b with `scipy.sparse.linalg.spsolve`. R = (mean V_src − mean V_sink) / I.
5. **Post-process.**
   - Loss per layer: Σ ΔV² / R_link.
   - Current density in A per mm of width from the voltage gradient. Plot it as a heat map: it shows instantly where the current detours around a cut.
   - Per-via current: |V_a − V_b| × G_via. Sort it and report the top few.

## Uses

### Path resistance and loss budget
Run every high-current path at its real current (battery side at the worst-case pack current, USB side at 5 A) and tabulate mΩ, drop and loss. On this project's routed board, the pack-side sum (2.06 mΩ) matched the 2 mΩ the thermal model already used. The per-port battery paths were new heat: 6.4 / 4.6 mΩ, later 1.9 / 1.3 mΩ after the fixes.

### Comparing fixes before the owner draws them
Add a candidate copper rectangle (a B.Cu link, extra vias, a joined pour) to the raster and re-solve. That turns "widen this" into "a B.Cu link at x 105.8–113.8, y 105.4–107.8 takes port 1 from 6.39 to 3.26 mΩ and the hottest via from 4.3 to 2.1 A". Fixes that do nothing show up too: a left-hand link did nothing.

### Kelvin sense-tap error
A sense line reads the voltage at the point where it joins the power copper. To check one:
1. Solve the power path through the sense resistor at a known current.
2. Find the node where each sense line touches copper that carries current (the end of the trace, or the via or pour it lands on).
3. Error = (V_tap+ − V_tap−) / (V across the resistor's own pads) − 1.

If the tap joins a plane via, a pour on another layer or a capacitor pad, the plane drop adds to (or subtracts from) the shunt voltage. Errors found this way: +78 % (SRN on a plane via), +23 % (ACN vias inside a pour on another layer), −7 % (SRP at a capacitor). A current limit set from a 1.8× reading trips at 56 % of its setting.

### Feeding a thermal model
Map each path's loss density into the thermal model's tiles in its own coordinates (here 2 mm tiles; model y = KiCad x − 100, z = 141.47 − KiCad y). Scale battery-side copper with battery current² and USB-side copper with USB current². On this board the routed copper added 0.63 W at 100 W out, which cut the full-power burst from 5.8 to 4.5 min.

## Pitfalls
- **The box clips the net.** A box that cuts off part of a pour forces the current into a narrower path. It gave 2.84 mΩ where the full net gives 1.87 mΩ.
- **The grid bridges gaps.** At 0.1 mm, a 0.08 mm gap between a keep-out and a via conducts in the model but not on the board. Re-run those regions at 0.03 mm. A via cut-out in a narrow pour neck is the same case: one signal via in a 0.85 mm neck took a battery path from 2.6 to 4.5 mΩ, and the 0.1 mm grid showed no change. Re-solve at 0.05 mm after any via or track is added near a neck.
- **Stale fills.** The `filled_polygon` data is whatever was saved last. Refill a copy first.
- **Pad layers.** A pad with `*.Cu` is on all copper layers; an SMD pad is on its own layer only. Through-hole pads get barrel links like vias.
- **Islands and wrong nets.** Check that the source and sink pads actually landed on cells of that net (`NO NODES` means a pad number or layer is wrong).
- **Use a current that matches the case.** Flat 9 A / 5 A is a fine screening current. For losses in a model, use the case's own current (P / V_bus for the USB side, P / V_pack(SOC) for the battery side).
