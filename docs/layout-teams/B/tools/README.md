# Team B placement framework

All commands run from `docs/layout-teams/B/`. Host python3 (numpy, shapely, PIL); KiCad steps run in `kicad/kicad:10.0`
through docker, as the shared scorecard does. Shared tools are only called, never edited.

| File | What it does |
|---|---|
| `blib.py` | Board as data (board_dump.json + real outline), fixed list, the transform (flip, turn), legality, cost terms |
| `secplace.py` | Runs recipe files, writes `fragments/<group>.json` + `.meta.json` |
| `check.py` | Legality, rings, escape faults, pin distances, box/region, bottom count, hpwl, picture |
| `stitch.py` | Fragments to one placement (refuses missing, double, foreign refs and overlaps) |
| `apply_b.py` | KiCad python: placement to board, with flips and `--partial` |
| `screen.sh` | Whole-board screen (shared scorecard) or partial screen (`score_part.sh`, `partcons.py`) |
| `blame.py` | Blocked edges, open power pins, DRC errors by ref, chip and group; what stands next to each blocked pad |
| `loose.py` | Power pads off the planned copper although their terminal counts as joined (`pads_not_joined` in dc.json); run it on every screen |
| `write_copper_split.py`, `split_screen.sh` | The same planned copper written with one zone per outline, then the shared scorecard with `--keep-copper` (blocked edges, optional full route). Run it on every whole-board screen and on the hand (`runs/hand-split`: 58 of 422) |
| `hand_fragments.py` | The hand placement as fragments (`fragments/hand/`), the usual `--base` |
| `hpwl.py`, `draw_boxes.py` | Wiring estimate and box picture (both take 4-element entries) |

## Formats
- Fragment `fragments/<group>.json`: `{ref: [x, y, turn, side]}`. turn 0/90/180/270 relative to the template; per quarter
  turn a local pad offset (lx, ly) becomes (-ly, lx). side `"F"`/`"B"`; a side other than the template's flips the
  part: lx -> -lx first, then the turn. Groups: `port1`, `port2`, `pack` (file name = group).
- Meta `fragments/<group>.meta.json`: rings, reserved, claims, bottom, deviations, failed steps, costs (written by secplace).
- Shared claims `fragments/claims.json`: `[{"ref", "box", "group", "why"}]`, first claim holds.
- Recipe `recipes/<group>/<nn>-<section>.json`: a list of steps; see the docstring of `secplace.py`
  (`put`, `ring`, `reserve`, `hot`, `at_pin`, `auto`, `translate`, `twin_check`, `side`, `claim`, `deviation`, `remove`;
  `hot`/`at_pin` also take `within` (a box the part must stay in) and `step` (finer grid)).
  Worked example: `recipes/port1/05-buck5v.json`. Border reserves for every group: `recipes/common/border.json`.

## Commands, in order (section worker)
```
# 1. place your section(s); base = the hand placement (or your last fragment), others = the other groups' fragments
python3 tools/secplace.py recipes/common/border.json recipes/port1/01-stage.json ... \
    --group=port1 --out=fragments/port1.json --base=fragments/hand/port1.json --others=fragments
#    exit 1 = a step failed (the FAIL line says which and why). Every placed part prints its spot, cost and pad gaps.
# 2. check it, with the picture; look at it
python3 tools/check.py fragments/port1.json fragments/port2.json fragments/pack.json --group=port1 --png=runs/p1-stage-1/check.png
# 3. partial screen: only fixed parts + your group's parts, your group's hot loops (about 5 min + 1.5 min per loop)
bash tools/screen.sh runs/p1-stage-1 fragments/port1.json --partial --hot="USB Port 1/HL_IN,USB Port 1/HL_OUT"
#    compare with runs/hand_port1/score.json (the pass mark), then look at runs/p1-stage-1/F.png and B.png
python3 tools/blame.py runs/p1-stage-1
# 4. whole board (lead, or a worker on a stitched copy)
python3 tools/stitch.py fragments/port1.json fragments/port2.json fragments/pack.json --out=runs/stitch-1/placement.json
bash tools/screen.sh runs/stitch-1 runs/stitch-1/placement.json --route=0           # add --hot=all for the 7 loops
python3 tools/blame.py runs/stitch-1
```
Partial hot-loop names: `USB Port 1/HL_5V`, `USB Port 1/HL_IN`, `USB Port 1/HL_OUT` (Port 2 the same), `HL_3V3`.
One router or hot-loop job at a time per worker; run dirs under `runs/<unique-name>/`.

## Traps we hit
- **The hand placement is not legal by our rule.** Its courtyards touch everywhere (121 touching pairs, 34 overlaps over
  0.05 mm, C108/Q103 0.97 x 0.85 mm). With the hand as `--base`, every hand part is an obstacle at 0.02 mm, so the
  free room is smaller than it looks; `stitch.py` needs `--allow-overlaps` for any placement that still holds hand parts.
- **Greedy takes the single best spot.** A small part placed early sits in the middle of the only gap and strands its
  neighbour (the FB divider in the example). Fixes, in order: put big power parts first, `reserve` the area a later part
  needs (with `except` for that part), give a part a `within` box, use `step: 0.05` for tight gaps.
- **Hand spots cross region lines.** C441 to C443, R433, R434 sit on Port 2's side and C444 in the pack region on the
  hand board. A part outside its group's region needs a `claim` step (and an entry in `fragments/claims.json` for the stitch).
- **The hot cost does not see the copper planner.** In the example C446's cheapest spot (0.27 mm above the hand's)
  passed every placer test, but the planner's return pour there had no room for return vias: GND at U404 open and
  HL_5V "no closed loop through C446". Screen each section with its hot loops (`--partial --hot=...`) right after the
  hot step; when a loop opens, hold the capacitor with `within` (or `put`) where the loop closes. The placer's hot
  penalties (a clear L-shaped way per link, supply way not crossing return way, a free return-via spot) are proxies only.
- **A hot cap may return to either GND pin.** `pin_pads` lists only U404 pad 4 as GND; give `"ret": ["1", "4"]` or the
  bulk capacitor is turned to face pad 4 and the planner's loop pour loses pad 1.
- **`hot` max_mm is hard by default.** When the first capacitor already holds the pins, the second cannot be within
  1.5 mm (C444: 1.7 to 1.8 mm); give the later capacitors `"soft": true` and a looser `max_mm`.
- **Do not round positions.** Rounding the hand positions to 5 decimals moved pads by 2 nm and changed the bare board
  the scorecard plans copper on; fragments keep 6 decimals, and the hand round trip then gives the same bare board,
  copper plan and blocked edges as the shared scorecard.
- **Loss has run-to-run noise in the 4th decimal** (the copper file is written in another order and KiCad's zone fill
  differs: GND 0.3352 vs 0.3350 W on identical inputs). Compare losses at 0.01 W.
- **Pads with no copper** (paste apertures, empty pad number) are in KiCad but not in blib; apply_b skips them in its check.
- **Partial screens compare only with partial screens** (`runs/hand_<group>`): power nets whose other end is in an
  absent group read as open there, and the blocked-edge total counts only edges between present pads.
- The 5 V buck's B1 box (115.2..121.1, 66.4..85.8) cannot hold the three 22 uF output capacitors while the hand's
  9 V supply sits beside it; PLAN section 6 moves the 9 V supplies to the bottom first.
- **A joined terminal can still have a loose pad.** dc.json joins a terminal when any one of its pads reaches the
  source; power_open in score.json stays empty. The PD controllers have two VBUS pad groups (23 = the 5 A switch to
  PPHV, 32 = the 5 V source switch); r1 and r2 left Port 1's pad 23 on an island. `tools/loose.py <run dir>` lists them.
  Put a capacitor of the same net against each such pad so the grown copper merges with the capacitor's pad.
- **A zone with several outlines loses all but the first when KiCad loads the board.** The shared copper writer puts
  every outline of a net and layer into one zone. The saved fill still blocks the router, but KiCad's connectivity no
  longer counts the lost pieces, so pads on them come back as extra edges to route (r3: U401 pad 32, R525, R529) and the
  routed board's last refill drops those pours. `tools/split_screen.sh <screened run> <new dir> [--route=MIN]` writes
  the same plan with one zone per outline and scores it; compare split with split (r3 30 of 421, hand 58 of 422).
