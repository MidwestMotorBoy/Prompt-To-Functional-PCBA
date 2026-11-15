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
| `straps.py`, `final_route.sh`, `final_json.py` | The routed-board check: hard PACK_P straps, one zone per outline, full route, then power paths, DRC and the seven hot loops of the routed board into `final.json` (last section) |
| `part_peek.py` | Courtyard, pads and legality faults of named parts, with `--set=REF:x,y,turn` overrides: a look before writing a put step |
| `quick_split_ghost.sh` | `quick_ghost.sh` on a plan-only run written with one zone per outline (a quick, optimistic split count between full screens) |
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

## Routed-board check (final scorecard): `final_route.sh` + `straps.py`
The pre-route screen cannot see what the full trial route does to the soft pours (`--softnets=GND,PACK_P,3V3`): signal
tracks may cross them and the router's last refill carves round the tracks. On r3a the In2 PACK_P bus fell into two
pieces and J113/R427 lost PACK_P. This check lays hard PACK_P strap tracks first, routes, and scores the ROUTED board.

**One command** (from `docs/layout-teams/B/`; it takes about 5 min for the screen, 15 to 25 min for the route and
10 min for the seven loops; run one at a time, nothing else of yours routing or solving loops meanwhile):
```
bash tools/final_route.sh runs/<screened run> runs/<new dir> [--route=45] [--no-straps] [--no-hot]
bash tools/final_route.sh runs/r3b-hot   runs/r3-final            # best board
bash tools/final_route.sh runs/hand_screen runs/hand-final        # the hand board, same command, for a fair comparison
```
`<screened run>` is any whole-board run of the shared scorecard (`tools/screen.sh` or `score_board.sh`): it must hold
`bare.kicad_pcb`, `spec.json` and `cu.json`. `--route=0` stops after the screen (blocked edges, DRC, loss).
`--no-straps` gives the same flow without straps (the comparison). The result is `runs/<new dir>/final.json`
(also printed as the last line, `FINAL {...}`).

**Phase 2 hooks (2026-11-15; nothing changes without them).** `--filters="<script> <options>;..."` runs copper-plan
filters after the straps, each as `python3 tools/<script> <spec.json in> <source run's cu.json> <spec.json out> <options>`
(the call form of `straps.py`; a filter that exits with a code other than 0 stops the run; logs `split/filter_<n>.log`).
`--post="<script> <options>"` runs a finishing pass after the full route as `bash|python3 tools/<script> <out dir> <options>`;
it reads `<out dir>/routed.kicad_pcb` (beside it `cu.kicad_pcb`, the board before routing, `drc.json` and `route.log`)
and writes `<out dir>/finished.kicad_pcb`, which is then the board the routed-board check scores (`scored_board` in
final.json; log `post.log`). The phase 2 baseline (plan in `PLAN2.md`):
```
ST="--net=PACK_P --layer=In2.Cu --source=Q102 --lanes=V;--net=3V3 --layer=In3.Cu --source=J301 --lanes=H --w=0.5 --wmin=0.5"
bash tools/final_route.sh runs/r4chg-hot runs/<new> --straps="$ST" [--filters="..."] [--post="..."] [--route=0] [--no-hot]
```
`runs/p2-base-screen` is that command with `--route=0`: 15 of 420 blocked, DRC 0, 1.124 W.

**What each number in final.json means**
| Field | Meaning | Pass mark |
|---|---|---|
| `straps[].tied`, `untied` | groups of PACK_P vias tied to Q102's group by strap tracks; any untied group is listed by name | untied empty |
| `straps[].length_mm`, `across_lanes_mm` | strap length; the part that runs east-west on In2 (it blocks the north-south signal lanes it crosses) | smaller is better |
| `drc_errors` | KiCad DRC errors of the copper board with the straps, before routing | 0 |
| `blocked_edges` | "N of M": edges with no path even on an empty board (ghost screen of the copper board) | no more than 2 above the same board `--no-straps` |
| `route.routed`, `failed`, `edges`, `timed_out` | full trial route; `timed_out: true` means the cap was hit and the counts are the last progress line | say so if it timed out |
| `route.unconnected_after_fill` | the router's own count after its last refill (failed edges plus anything the refill cut) | lower is better |
| `pre_route.loss_W`, `power_open` | dc_score on the copper board before routing | 3V3 at L201 allowed; GND at J301/J302 is joined by the router |
| `routed.loss_W`, `power_open` | dc_score on the routed board: the hard limit that counts | only 3V3 at L201 |
| `routed.loose` | tools/loose.py on the routed board (power pads joined only through other pads) | empty |
| `routed.drc_errors`, `unconnected_power` | KiCad DRC of the routed board; unconnected items of PACK_P, 3V3, GND (failed edges show here too) | report |
| `hot_routed` | the seven hot loops on the routed board: pass count, sum of loop totals (nH), each loop | 7 of 7 tier 1; compare each loop with `hot_pre_source` |
| `hot_pre_source` | the same from the screened run (before routing, no straps), when it ran with hot loops | - |

A loop that opens or rises after routing: compare `hot_routed.loops` with `hot_pre_source.loops`; the routed board is
`runs/<new dir>/routed/cu.kicad_pcb` (local only).

**straps.py alone** (adds strap tracks to a copper plan; `--png` draws them: grey pour, red obstacles, blue groups, green straps):
```
python3 tools/straps.py runs/r3b-hot/spec.json runs/r3b-hot/cu.json /tmp/spec_straps.json --png=/tmp/straps.png
python3 tools/straps.py spec_straps.json cu.json spec2.json --net=3V3 --layer=In3.Cu --source=J301 --lanes=H   # a second net
```
Defaults: PACK_P on In2.Cu from Q102, width 1.0 mm where it fits and 0.5 mm minimum, 0.25 mm from every other net's via,
through-hole pad, track, pour and keep-out on the layer, inside the planned pour outline. Exit 1 = an untied group or a
clearance fault (both printed). Files of a run: `split/spec.json` (plan with straps), `split/straps.log`,
`split/straps_PACK_P.png`, `score.json`, `dc.json`, `ghost.log`, `route_failed.txt`, `routed/dc.json`, `routed/hot_gate.json`.

**Two things the routed-board check showed (2026-11-15, r3 and hand):**
- *Straps keep PACK_P joined, not its resistance.* In2 is 0.5 oz (about 1 mohm per square): a 1 mm strap is about
  1 mohm per mm of length, so the straps only guarantee that nothing opens. J113/R427 (10 A and 5 A) draw their current
  through what the router leaves of the In2 sheet: J113 2.23 mohm before routing, 6.8 mohm after (r3, PACK_P only) and
  16.2 mohm in another route of the same board (PACK_P + 3V3 straps); routed loss 1.75 and 2.93 W against 1.12 W before
  routing. Keep comparing routed loss between boards with this in mind (it moves with each route).
  `--main=J113:4,...` lays a wide strap straight to a terminal; on r3 the only way that fits runs 69 mm round the north
  (the south-east is full of MCU pads), so it is no cure and final_route.sh does not use it.
- *The 3V3 In3.Cu bus is cut too* (r3a 1 piece -> 2, r3 with PACK_P straps -> 5; the pieces hold the PD chips' 3V3 vias).
  dc_score does not see it (3V3 has only L201 as a terminal), KiCad's unconnected list does. Add 3V3 straps with
  `--straps="--net=PACK_P --layer=In2.Cu --source=Q102 --lanes=V;--net=3V3 --layer=In3.Cu --source=J301 --lanes=H --w=0.5 --wmin=0.5"`
  (on r3: In3 3V3 stays one piece, 28 of 427 blocked, 391 of 427 routed). Run the hand board with the same option.

## Phase 2: pin escapes and finishing pass

Two hooks for `tools/final_route.sh`, plus the tools behind them. All geometry checks go through `tools/pinlib.py`
(shapely, exact): other nets' pads, tracks, vias, pours, keep-outs, the antenna box and the board edge; copper 0.15 mm,
HighCurrent to small signals 0.25 mm (pads excepted, as the DRC rule), edge 0.25 mm, zone clearance 0.2 mm, the
router's via rules (0.6 mm same net, 0.75 mm other nets, 0.9 / 1.1 mm to through-hole pads), no via on an SMD pad of
1.6 mm or less. New copper keeps 3 um more than each rule (KiCad measures its own polygons).

**pins.py: a copper-plan filter** (`--filters="pins.py"`): lays the copper for connections no router can start, before
routing. Rules, in order: `ep` (QFN GND / 3V3 pin stubbed into its own exposed pad), `gate` (a gate pad wrapped by its
own stage's pour: the pour is cut back by clearance + track + clearance and a 0.3 mm gate track laid), `table`
(explicit escapes, `plan/p2-pins.json`), `rail` (GND / 3V3 pads the planner left to the router: a via with a stub, on
the planes for GND, never in another pin's escape lane when anything else fits). A pour is cut only where a rule or a
table entry names its net, never a hot-loop pour, and a cut that would split a pour into more held pieces is refused.
Every item is checked again at the end; on any fault nothing is written and the run stops (exit 1).
```
python3 tools/pins.py runs/r4chg-hot/spec.json runs/r4chg-hot/cu.json /tmp/spec_pins.json --png=/tmp/pins_png
python3 tools/pins.py in.json cu.json out.json --rules=table --table=my.json --only=C304.2 --dry   # try one entry
python3 tools/pinlib.py look <spec.json | board.kicad_pcb> <cu.json> out.png U405.5 --r=2.6 --w=0.15   # look at a pin
bash tools/spec_ghost.sh <spec.json> runs/r4chg-hot <out dir> [--only=<net regex>] [--no-ghost]   # copper + DRC + ghost of a plan
```
Table format (`plan/p2-pins.json`, a list; refs and pads relative to the part, so the entries survive a nudge and
serve both ports with `"ref": "U405|U505"`; any value may be per port with `"a|b"`):
```
{"ref": "U405|U505", "pad": "4", "dir": "N", "via": true, "w": 0.15, "max": 1.6,
 "cut": ["/USB Port 1/VBUS|"], "keep": ["U405.3:N:0.6|"], "via_gap": "0.65|0.75", "why": "..."}
{"ref": "U401", "pad": "27", "to": "C401.2", "w": 0.2, "max": 2, "cut": ["/USB Port 1/VBUS"], "why": "..."}
```
`dir` N/S/E/W/out: lead out of the pad (`lead` mm beyond its edge, default 0.15), then the shortest exact way to a
free via spot within `max` mm (existing same-net vias count as goals). `to`: a whole one-layer connection pad to pad.
`cut`: nets whose (non-hot) pours may be cut. `keep`: `REF.PAD:DIR:LEN` strips kept free for another pin's escape.
`via_gap`: minimum distance to other nets' vias (default 0.75, the router's; 0.65 only where both pins are escaped
here). Entry order matters: an earlier via can close a later pin (put the tight pin first, with a keep strip for its
neighbour).

**finish.sh: the finishing pass** (`--post="finish.sh"`): reads `<out>/routed.kicad_pcb` and `<out>/cu.kicad_pcb`,
writes `<out>/finished.kicad_pcb` (work files in `<out>/fin/`, log `post.log`):
1. KiCad DRC of the routed board;
2. up to `--passes` (2) continuation routes with `tools/router_b.py --cont` while anything is open or a DRC error
   is left: those nets lose their routed copper and are routed again with more pulls, time and search (`--rips=900
   --riptime=1500 --maxrip=6 --phases=4 --capx=2`, `--min=30` minutes each), HighCurrent copper with `--hcx=0.16`
   (the 0.25 mm rule holds on the grid's diagonal steps too), hot-loop pours closed to other nets (`--hotko`); a pass
   is kept only if it leaves fewer open connections + DRC errors;
3. `--hand=<json>`: hand-laid tracks and vias (`tools/handroute.py`);
4. dangling ends removed (`tools/fin_clean.py`, only items the router laid), zones refilled, DRC again;
5. power guard (`tools/fin_guard.py`): dc_score loss no more than the routed board's + `--tol` (0.001 W), no new power
   open, no new track or via of another net in a hot-loop pour. The best candidate that passes is copied; if none
   does, the routed board itself.
The last line of `post.log`: `finish: finished (<candidate>) unconnected N {net: n} ; DRC errors M {type: n} ; loss ...`.
```
bash tools/final_route.sh runs/r4chg-hot runs/p2b-<name> --straps="$ST" --filters="pins.py" --post="finish.sh"
cp -r runs/r4-final/. runs/p2b-<name>/ && bash tools/finish.sh runs/p2b-<name>            # an earlier routed run (copy it first)
bash tools/finish.sh runs/p2b-<name> --no-route --hand=runs/p2b-<name>/hand.json          # hand tracks only
```
**handroute.py** lays the last connections by coordinates read off zoom pictures (`tools/zoom.py` or
`pinlib.py look` on the routed board):
```
python3 tools/handroute.py in.kicad_pcb out.kicad_pcb hand.json [--cu=<cu.json of in>] [--check] [--no-drc]
{"board": "runs/p2b-x/fin/r1.kicad_pcb",
 "tracks": [{"net": "/USB Port 1/C_CC2", "layer": "F.Cu", "w": 0.15, "points": [[104.75, 69.17], [104.9, 69.9]]}],
 "vias": [{"net": "/USB Port 1/C_CC2", "x": 105.85, "y": 70.9}]}
```
The check uses the board's filled copper (GND / PACK_P / 3V3 fills may be crossed: the refill carves round the new
copper; hot-loop pours may not). Any fault: nothing is written, exit 1. Keep the json beside the run; `board` says which
board the coordinates belong to (they are only valid on that board).

**Traps.**
- A via escape can close the next pin (U405.4's via closed VBIAS and SBU_FLT): the table order and `keep` strips fix it.
- A pour cut on a power net costs loss: C304.2 cut west of the pad cost 5.8 mW of CELL_P, the same via north 0.9 mW.
  Look at dc.json per net before and after (`runs/p2-base-screen/dc.json` is the plan without the filter).
- Closing GND opens (J301 / J302 via the rail rule) adds their loss to the sum: the plan without the filter hides it.
- `router_b.py` with no options is the shared router; finish.sh passes `--hcx=0.16 --hotko=<hot parts>` (r4-final had 3 HighCurrent-to-signal clearance errors at CELL_1N with the shared 0.1).
- `fin_clean.py` removes only dangling items not in the plan; a dangling pins.py escape (its net failed) stays.
- `final_route.sh --post` only runs with a full route (`--route` not 0).
