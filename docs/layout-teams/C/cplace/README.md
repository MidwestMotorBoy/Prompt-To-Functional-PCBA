# cplace: team C common placer (shared contract)

One placer file, `cplace.py`, that every work package builds on. It is round 3's `greedy_fill.py` run on the whole
board, with hook points. Each package adds ONE module beside it and touches `cplace.py` only where a hook is missing.

## Files

| File | What it is |
|---|---|
| `gen_inputs.sh [dir]` | Regenerates every input into `/home/claude/work/C/in/` from repo files (2 s, no KiCad) |
| `pp_bodies.py` | Copy of round 3 `pp_w1.py`; only its `DUMP_BODIES` export is used (bodies, keep-outs) |
| `cplace.py` | The placer. `cplace.py dump clusters intent floorplan bodies out.json`, knobs by environment |
| `run.sh <out.json>` | `cplace.py` on the generated inputs (10 s with no hooks) |
| `cscore.sh <outdir> <placement.json> [opts]` | The scorecard for a placement; handles side changes through `c_apply.py` |
| `c_apply.py` | Team copy of `tools/floorplan/apply_placement.py`; the side flip is package B's to implement |
| `metrics.py <dump> <placement>` | Signal half-perimeter and crowding round the ICs (not side-aware) |
| `cplace.py.base` | The base as handed out. `diff cplace.py.base cplace.py` is your core patch |

Legality check without KiCad: `python3 tools/floorplan/overlaps.py /home/claude/work/C/in/dump.json <placement.json>`
and diff against the same command with no placement (the hand board itself has 133 mm2 of sliver overlaps; a legal
placement shows only overlaps between fixed parts: 123.96 mm2, all J/TH/C456/C556 against keep-outs).

## Inputs (`/home/claude/work/C/in/`)

- `dump.json`: template board as the placer sees it. `fps[]` (ref, x, y, side, rot, court), `pads[]` (ref, num, net,
  x, y, box, layers), `keepouts[]` (box, layers, no_footprints, ...), `box` (board box). Same poses as
  `tools/score/template/board.kicad_pcb` (checked).
- `clusters.json`: section name -> parts TO PLACE (247 parts). Any part not in it is fixed (42 parts, `fixed.json`):
  J, H, TP (the template has no SW), and the cup-fixed parts U301, L401, L501 and all 12 back-side parts
  (C208-C213, C421, C456, C521, C556, TH101, TH104). Never move a fixed part.
- `intent.json`: `near` (113 + power-path statements, weight 4), `keepapart`, `kelvin`.
- `floorplan.json`: Logan's reviewed boxes (r2-d), keyed by section name. Base runs with `BOXW=0` (boxes not enforced).
- `constraints.json`, `netlist.json`: hot loops (`hot_loops`: caps in order, switch_pins, `pin_pads`), `draw` (stage
  parts: cin, cout, inductor, rin, rout), `nets` (kind power, current_a), `serves`, `kelvin`, `heat`.
- `bodies.json`: `refs`, `bbx` (body box per part: offsets from the part origin in the board frame at the dump pose),
  `tbx`/`thru` (through-hole box), `TM`, `KO` (keep-out box, on F, on B), `box`, `fixed`.

## Placement file

`{ref: [x, y, angle]}`: part origin in mm, angle = 90 x quarter turns AGAINST THE DUMP POSE (not KiCad's absolute
rotation). A pad at local offset (lx, ly) from the origin in the dump lands at origin + rotv(lx, ly, k), with
`rotv`: k=1 -> (-ly, lx). Fixed parts are left out. A part on the other side than the dump has it carries a 4th
element `"F"` or `"B"`; its pads and body are the dump offsets mirrored in x (lx -> -lx) BEFORE the turn.
`score_board.sh` takes only 3-element entries (its apply step unpacks exactly three), so always score through
`cscore.sh`, which turns a placement with side changes into a board first.

## Hooks (`HOOKS=cpower,cside,ccorr`, modules in this folder, called in that order)

| Hook | When | Use |
|---|---|---|
| `setup(ctx)` | inputs loaded, fixed parts are obstacles, nothing placed | read constraints, add obstacles/reservations, change bodies |
| `pre_place(ctx)` | right after setup | place parts yourself: `ctx.set_side(r, s); ctx.P[r] = (x, y, k); ctx.add_obstacle(r); ctx.LOCK.add(r)` |
| `side_options(ctx, r)` | inside `place()` for each part | return the sides to try, list of bool (True = F). Default: current side only |
| `extra_illegal(ctx, r, k, xs, ys)` | per candidate grid | bool array [len(ys), len(xs)], True = forbidden (hard reservation) |
| `extra_cost(ctx, r, k, xs, ys)` | per candidate grid and in `cur_cost` | float array [len(ys), len(xs)] or a number, added to the cost (mm units) |
| `post_place(ctx)` | after the re-place passes, before writing | checks, reports, last repairs |

`ctx` fields: `P` (placed: ref -> (x, y, k)), `sideF` (ref -> on F?), `side0`, `LOCK` (parts the passes, swaps and
evictions must not touch), `fill` (parts to place -> section), `lp` (ref -> [(lx, ly, net, pad num)], already mirrored
for the current side), `netpads`, `power`, `sig`, `near`, `bbx`, `tbx`, `thru`, `KO`, `obs`, `OB`, `KEEPB`, `box`,
`boxof`, `d`, `it`, `env`, and the functions `pad_xy(r, j)`, `body_of`, `add_obstacle(r)`, `legal_mask(r, k, xs, ys)`,
`place(r, win, step, extra=None, sides=None)` -> (cost, x, y, k, side) or None, `put(r, best)`, `set_side(r, s)`,
`place_small(r)`, `total_cost`, `wiring`, `near_cost`, `occ_map`, `integral`, `free_in`, `cur_cost` (set before post_place).
`CONSTRAINTS` in the environment is the path of constraints.json.

Rules for a package:
1. Your feature lives in your module and is OFF unless your module is in `HOOKS`. With `HOOKS` empty `cplace.py` must
   give the same placement as `cplace.py.base` (check with `cmp` on the output for SEED=2).
2. If you must change `cplace.py`, keep the change small, mark it `# [A]`, `# [B]` or `# [C]`, and list it in your
   report so the lead can merge three patches by hand.
3. Work in your own subfolder (`docs/layout-teams/C/<your key>/`) for notes and test scripts; the module itself goes
   in `cplace/`. Scratch output goes under `/home/claude/work/C/<your key>/`.
4. Every number you report comes from `cscore.sh` (score.json). Look at F.png and B.png before calling anything good.

## Baselines measured 2026-11-14 in this container (screen = `--route=0 --no-hot`, about 6 min)

| Placement | Blocked edges | Loss | power_open | DRC errors |
|---|---|---|---|---|
| Hand placement (`/home/claude/work/C/hand_screen`) | 56 of 452 | 1.359 W | P1 PP5V at U401, 3V3 at L201, GND at J301/J302 | 0 |
| Base `cplace.py`, no hooks, SEED=2 (`base_seed2_placement.json`, `/home/claude/work/C/base/screen`) | 98 of 465 | 2.001 W | P1 PP5V and VBUS at U401, P2 PP5V at U501, GND at U504, 3V3 at L201, GND at J301/J302 | 0 |

The base run places 247 of 247 parts in 10 s with no new overlap. Its blocked edges sit at U501 (19), U401 (17),
U503 (13), U403 (10), U405 (8). Hot loops were not solved for either (no `--no-hot` run yet).
