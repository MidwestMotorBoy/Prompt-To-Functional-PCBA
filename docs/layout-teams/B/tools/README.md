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
free via spot within `max` mm (existing same-net vias count as goals). `at`: `"dx,dy"` (mm, board axes, from the pad
centre; per port `"a|b"`) fixes the via spot instead of searching for one, for corners where the first free spot
closes the next pin (Port 1 corner of U405: C_CC1 pin 4 via over the tip of pin 5 at `-0.4,-0.75`, VBIAS pin 3 via at
`-0.02,-0.75`, C_CC2 J401.B5 via at `0.55,1.025` south-east of B5, pins 5 and 6 joined round the corner). `to`: a whole one-layer connection pad to pad.
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
(1b, and after each pass) stub trim (`tools/fin_trim.py <in> <its drc.json> <out>`): a track named in a clearance
   error whose end lies on a pad of its own net (and on nothing else) is shortened along itself to that pad's edge
   (0.03 mm inside). The router starts every fan-out stub at the pad centre, so stubs of neighbouring 0.4 mm pitch
   pins that leave in opposite directions are 0.225 mm apart inside the pads: the 3 'HighCurrent copper to small
   signals' errors at U101 (CELL_1N against TS1, BTP_INT, SMBD). The trim runs before the continuation, so the
   continuation does not lift CELL_1N for a stub error (on r4-final it lifted it and could not route it again).
   The input board needs its .kicad_pro / .kicad_dru beside it (the refill uses the project's rules; without them the
   PACK_P pour fills at 0.2 mm and DRC shows 200 new errors);
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
- A continuation pass that hits finish.sh's `timeout --min` writes NO board (exit 124; `runs/p2r1_full1fin` lost a pass
  that had routed 12 of 18 open connections). `router_b.py --deadline=S` (finish.sh passes `min*60-300`) stops pulls and
  new phases after S seconds and writes the board; keep `--riptime` x `--phases` in mind, each phase gets its own riptime.
- The router never routes an unconnected item whose two ends are zones: the VBUS island of J401.B4 / J501.B4 (the
  receptacle's second VBUS pin pair) and the Port 2 BAT_SNS_P island at R528.1 stay open after any route or
  continuation. BAT_SNS_P: `hand.json` beside the run (one 0.2 mm F.Cu track) or worker A's `links.py`; VBUS: a plan
  join (the room south of B4 holds the C_CC1 via of U405.4 / U505.4), not done in round 1.
- pins.py table `at` offsets are board axes, not part axes: they hold for a nudge, not for a rotated part; the Port 2
  entries of U505 keep the searched via spots.

## Phase 2: power copper under routing (worker A)

Copper-plan filters for `final_route.sh --filters` (call form `python3 tools/<f> <spec in> <cu.json> <spec out> [opts]`),
so that PACK_P to J113/R427 keeps its pre-route resistance on the ROUTED board. Write a space in a net name as `~`.

| Tool | What it does |
|---|---|
| `trunk.py` | A HARD (tracks, not pour) wide trunk of a net on an outer layer (default PACK_P on B.Cu, Q102 -> J113, R427): least-resistance Steiner path on a 0.1 mm grid (step cost (w / width that fits)^pw), width capped at `--w`, closed where `--wmin` does not fit; clear of other nets' pads, vias, tracks, pours and keep-outs by `--clr`, and of small signal pads by `--under` (their escapes); `--narrow=REF:mm:w` caps the width near a part (keeps its pin escapes open), `--avoid=REF:mm` closes the room near it; `--stitch=MM` adds through vias where one is free on every layer. Every track is checked exactly (shapely); `--png` draws it. Exit 1 on a missed terminal or a clearance fault. |
| `ruleareas.py` | KiCad rule areas in the plan (`spec["rule_areas"]`, written by `write_copper_split.py`): `--protect=NET:LAYER,...` no-tracks over every planned pour of a soft net on that layer; `--hot` no-tracks over the hot loops' GND F.Cu return pours (`--hot_mode=vias`: no vias only); `--corridor="In2.Cu:2.5:x,y/x,y"` a no-signal corridor. Areas are cut back from plan tracks/vias (KiCad flags any track in a no-tracks area) and from other nets' pads by `--esc`. The router obeys them (`router.py mark_ko`). |
| `links.py` | Short explicit power links by coordinates (`--link="NET|LAYER|W|x,y/x,y"`, `--via="NET|x,y"`), each checked exactly; exit 1 and nothing written on a fault. Used for the Port 2 BAT_SNS_P island at R528.1. |
| `quick_dc.sh` | `bash tools/quick_dc.sh <spec.json> <out dir>`: plan -> board (one zone per outline), KiCad DRC, dc_score; prints DRC errors and PACK_P J113/R427 mohm. About 1 min; not a scorecard number. The out dir's `cu.kicad_pcb/.kicad_pro/.kicad_dru` are what goes into `route_queue/` for Logan's PC. |
| `netclusters.py` | `docker run ... kicad/kicad:10.0 python3 tools/netclusters.py <board> <net> [...]`: KiCad's connectivity clusters of a net (pads, vias, zones per cluster): which piece of a power net is cut off. |

**The recommended filter string** (r4, `runs/r4chg-hot`; 3V3 straps stay in `--straps`, the PACK_P In2 straps move
AFTER the trunk so they tie to it instead of running east-west across the In2 lanes):
```
ST3="--net=3V3 --layer=In3.Cu --source=J301 --lanes=H --w=0.5 --wmin=0.5"
FA="links.py --link=/USB~Port~2/BAT_SNS_P|F.Cu|0.25|95.2,104.9/95.2,104.3/95.7,103.8;ruleareas.py --protect=3V3:F.Cu,PACK_P:F.Cu;trunk.py --w=3 --narrow=U403:0.8:2.0;straps.py --net=PACK_P --layer=In2.Cu --source=Q102 --lanes=V --across=15"
bash tools/final_route.sh runs/r4chg-hot runs/<new> --straps="$ST3" --filters="$FA" --route=80     # PACK_P route needs > 45 min here
```
Add `;ruleareas.py --hot` (no tracks) or `;ruleareas.py --hot --hot_mode=vias` at the end for the hot-loop areas.

**Traps.**
- Order matters: with the links and protect areas, PACK_P straps BEFORE the trunk (189 mm, 72 mm east-west across
  the In2 lanes) gave 22 of 422 blocked (`runs/p2a-combo-s`); the same filters with the straps AFTER the trunk and
  `--across=15` tie to it (142 mm, 36 mm across) and gave 15 of 422 (`runs/p2a-n1`). Trunk alone with the straps
  before: 15 of 422 (`runs/p2a-t3s`).
- A 3 mm trunk under U403 (the Port 1 charger) takes the room its south pins escape through: the route loses U403
  TS / CE_N / ICHG / I2CC_SDA / CHG_INT edges. `--narrow=U403:0.8:2.0` gave the best route count; `--avoid=U403`
  (round it, 40 mm) and a plain 1.5 mm trunk were worse or no better.
- Route counts move by about 4 edges between two routes of what is the same copper plan (`p2a-n1`: 391 of 422 on
  Logan's PC, 387 locally; the local board file differs in bytes after the scorecard rewrite). Do not pick between
  variants on differences of 1 to 3 edges from one route each.
- The router never routes an unconnected item whose two ends are both zones (`router.py parse_edges`: `if A and B
  both Zone: continue`). A pour planned in two pieces that no pad joins (Port 1 and Port 2 VBUS at the USB-C
  receptacle's two VBUS pin pairs, Port 2 BAT_SNS_P at R528.1) stays open on the routed board whatever the route
  does: it must be joined in the copper plan (`links.py`, `trunk.py` for the net) or by a hand track.
- The local route of a trunk board is slow (60 min for `p2a-n1`): use `--route=80`, and say when it times out.

## Phase 2: the merged command, `--resume`, `hot_tracks.py` (lead, after round 1)

The merged flow of round 1 (placement r4 from `runs/r4chg-hot`; `F1`/`F2` are written out in `LOG.md`, entry of
2026-11-15 23:35, and in `best_routed/summary.json`):
```
bash tools/final_route.sh runs/r4chg-hot runs/<new> --straps="$ST" --filters="$F2" --route=80 --post="finish.sh ..."
```
Filter order matters: links and protect areas, then the trunk, then the PACK_P straps (they tie what the trunk left),
then `pins.py`, then the links that need the pins' vias (the In3 link of U401.38). A merged route takes 65 to 70 min
on this box (0 blocked edges means the router has more to argue about), so use `--route=80`.

- `final_route.sh ... --resume [--post=...]` runs only the finishing pass and the routed-board check on an out dir that
  already holds `routed.kicad_pcb` (same `--straps`, `--filters`, `--route` as the first call; they are only recorded).
  Without `--post` an existing `finished.kicad_pcb` is kept and scored. Use it to try finishing options on one routed
  board, or when a job had to be cut after the route. A background job of a session ends after 2 h at most: start the
  route and the finishing pass as two jobs when the two together may pass that.
- `tools/hot_tracks.py <board before routing> <cu.json> <routed board> [out.json]` lists every track and via the router
  added inside a hot-loop pour of another net (the hot pours of `pinlib.hot_polys`, read from the board before
  routing), per net with its window. `final_route.sh` calls it; `final.json` has `routed.hot_pour_items`
  (`tracks`, `vias`, `nets`), next to the new `routed.unconnected_nets` and `routed.pack_p_mohm` (J113, R427, R527).
- Layer pictures of a routed board, whole board: `python3 tools/zoom.py <run>/routed <out.png> 78,62.4,122,137.6 In2.Cu 20`
  (any copper layer; `<run>/routed` holds `cu.kicad_pcb` and `cu.json` of the scored board).
- `best_routed/` holds the best routed board so far with its `final.json`, `summary.json` (numbers, the gates met and
  not met, the rebuild command) and the four layer pictures.

Traps met in the merge:
- The ghost screen passes connections that the full route then reports as "no way even with every other route gone"
  (U102.2 to C112.1, C413.1 to U403.20, C402.1 to U405.11, TP113.1 to R118.2, Q101.4 to R110.1 on `runs/p2-m1`, in the
  local and in the PC route alike). A connection that fails that way in two routes needs copper before routing
  (a `pins.py` table entry), not more router time.
- A table track can close its neighbours: EN_5V2 under the U504 body closed SS_5V and both FB edges (4 blocked), an
  F.Cu track from U401.38 closed U401.37. Screen after every table change; lay the neighbour's escape first.
- A 3V3 or PACK_P track of the table may not cross a `ruleareas.py --protect` area (KiCad: "items not allowed").
- The continuation route of `finish.sh` can end worse than it started (810 pulls for 24 open connections on
  `runs/p2-m1`); the pass rule drops it, so nothing is lost, but nothing is closed either.

## Phase 2 round 2: copper before routing for the connections no route makes (worker A)

Placement r5 (`candidates/r5.json`, source `runs/p2a-r5src`, 7 of 7 hot loops at r4's values) and one filter string
that gives every connection that failed in both round-1 routes its copper before routing. The strings are written out
in `runs/p2a-look/strings.sh` (`ST`, `FU`, `LP1`, `LP2`, `FR5`; `FR5W4` = the same with a 4 mm trunk):
```
FR5="$FU;$LP1;pins.py --table=plan/p2-pins-r5.json;$LP2"
bash tools/final_route.sh runs/p2a-r5src runs/<new> --straps="$ST" --filters="$FR5" --route=80 --post="finish.sh --no-route"
```
`FU` is round 1's `F1` without the final `pins.py`, plus `pins.py --rules=table --table=plan/p2-pins-u403.json`
BEFORE `trunk.py` (U403.7 CE_N and U403.9 ICHG get their vias before the trunk takes the via sites under U403's
south-east corner). `LP1` is the Port 1 VBUS join (three vias and a B.Cu link at y 69.25, stem 0.4 mm wide because
of the GND via at 103.25,70.17). `plan/p2-pins-r5.json` is r4's table plus the entries for U405 (Port 1 CC/VBIAS
vias in one row), EN_5V1 (U404.2 under the body to R432.1, with a hot-pour trim), SS_5V, the U504 knot (EN 84.15,67.2,
FB 85.02,67.22), U102 (V4 via, C112), BTST2 (U403.20 to C413.1), Port 1 CC2 (U405.11 to C402.1 west of the CC1 way),
WAKE (TP113.1 to R118.2), CELL_P (R110.2 to R118.1, R118.1 into the CELL_P pour, Q101.4 via) and CHG_G (two vias,
the router joins them on an inner layer). r4's `plan/p2-pins.json` is unchanged.

New `pins.py` table keys (see the docstring): `cut_hot` + `cut_box` (hot-loop pours of the named nets may be cut,
clipped to the box, logged in mm2, refused when a held piece loses its last via; solve the loop again after it, limit
+0.01 nH), `drop` (remove planner vias of the pad's net at given offsets, with the tracks ending on them; undone when
the entry fails), `"to": "zone"` (into the net's own pour on the pad layer) and `"path"` (an explicit polyline of
offsets from the pad centre, every segment checked exactly). New copper is cut back from the spec's rule areas.
`--table=` may be relative to the team folder.

Helpers (team folder, python only, no scorecard):
- `tools/spec_chain.sh <run> <out.json> --straps=".." --filters=".."`: steps 1 and 1b of `final_route.sh` (straps,
  then filters) with a log per step beside the out spec, in seconds; for designing entries before a screen.
- `tools/plan_whole.sh <out dir> <placement.json>`: whole-board plan of a placement without the scorecard (about
  1 min); the out dir works as a source for `spec_chain.sh`, `pinlib.py look` and `win_items.py`.
- `tools/win_items.py <spec.json> <cu.json> x0,y0,x1,y1 [--layers=..]`: every pad, plan track, via and pour piece in a
  window, with nets: the coordinates behind a table entry.

Traps:
- `final_route.sh` runs the filters in `<out>/split`: a relative `--table=` was "not found" there, and the screen
  showed 12 blocked edges. `pins.py` now resolves it against the team folder; other filters with file options do not.
- The 5 mm trunk takes every via site under R109/R110/TP113/Q101 and under U403's south-east corner, and the FET_MID
  pour closes the way south: those pins need explicit `at`/`path` entries, and a via spot chosen on one trunk breaks
  when the trunk changes (108.0,111.5 did). Screen again after any trunk change.
- The via search only looks at the 600 nearest candidates; in a crowded spot give `at`.
- The planner's GND tie chains can close a pad turned the wrong way (R432 turned 180); look at the plan first.
- Router via pitch is 0.75 mm between nets (0.752 was refused within EPS); KiCad DRC needs copper clearance only.
- One table entry can close its neighbour (CC2's east way closed CC1, EN under U404 closed SS_5V): lay the neighbour's
  escape as its own entry first, and screen after every change.

## Phase 2 round 2: accept-or-revert finishing pass (worker B)

The lead's call: `final_route.sh ... --route=80 --resume --post="finish.sh --modes=aor,aork --min=20 --tol=0.01"`
(add `--hand=<json>` for hand tracks). `--modes=aor,aork` = two accept-or-revert passes of 20 min each (the second may
pull Kelvin pieces); a pass is kept only when unconnected + DRC errors drop, or hold with fewer hot-pour items, and the
power guard (`fin_guard.py`, `--tol` W) still picks the finished board, so the pass never returns a worse board.

**What one pass does** (`router_b.py --cont --keepre --split --aor --pieces --lift --pcheck`, all in KiCad's container):
- `--split`: each net's routed copper is cut into pieces (joined end to end or at a T, never through a pad); a piece is
  laid again as Prim MST edges over its anchors (pads, fixed copper, the net's zone).
- One task at a time, shortest open connection first, then every piece with copper in a hot-loop pour of the plan board
  (`--lift=<hot_tracks.json>`, laid again with `--hotko`). A task may pull other pieces (`--taskrips=12`,
  `--tasktime=90` s, a deadline inside A* too) but must lay every pulled piece again. Accepted only when KiCad's own
  `GetUnconnectedCount` drops (open task) or holds (lift task, which must also leave fewer of the net's hot-pour
  items on the board) and the power check passes; otherwise grids, routes and
  board items are put back exactly (`_aor_save` / `_aor_restore`, board items by uuid). Sweeps repeat while one accepts.
- `--pcheck=cu.json:constraints.json:tol:budget`: after each task the GND / PACK_P / 3V3 zones are refilled (2 s) and
  `dc_score.score_net` scores PACK_P and 3V3 (0.1 mm) and GND (0.2 mm): loss may rise `--ptol` (2 mW) per task and
  `--pbudget` (5 mW) in all; no PACK_P terminal may cross 3.0 mohm or rise > 0.1 mohm past it; no new power open.
  Needs shapely in the container: finish.sh copies the host's (same cp313 ABI) into `fin/pylib`.
- Power pieces: `isl.py --pieces` (shared, used read-only) names every cut-off In2 / In3 piece; `fin_report.py` puts
  its edges in place of KiCad's `Zone | Zone` pairs; the router then starts anywhere on the piece and must end on the
  main body (the goal window grows 12 / 30 / 80 mm until it holds main-body cells; never the piece itself).
- Kelvin nets (ACP_F, ACN_F, SRP_F, SRN_F, SR[PN]) are frozen unless `--aorkelvin` (mode aork); a Kelvin piece laid
  again may be at most 1.3 x + 1 mm its old length.
- `fin_islands.py <board> <cu.json> --out=pieces.json` (host) lists the pieces of PACK_P / 3V3 / GND as KiCad sees them
  (dead = no pad, pads = a real open); `fin_dead.py` (KiCad) removes the tracks / vias of dead pieces and refills.
  finish.sh runs both before the pass. On p2-m1 every cut-off piece held pads (none dead).
- `handroute.py`: `--keep=<plan board>` adds the plan's hot pours as obstacles; `"lift": [nets]` removes routed copper
  of those nets that is not in the plan; track entries may give `"from"` / `"to"` ("REF.PAD" or [x,y]) and the path is
  found (free area + `pinlib.path_in`) and printed.

Traps met:
- An escape stub that lands on the start's own copper counted as a goal hit (U403-FB "connected" to itself): a hit is
  valid only on goal cells, and KiCad's count per task is the arbiter. A plane goal window with no main-body cells fell
  back to the start's own island (R314 3V3): the window now grows.
- Without the power check a pass closes connections by cutting the PACK_P sheet on In2 (324 to 388 mW, R527 1.57 to
  3.38 mohm); closing all PACK_P fills to new channels instead (`--closefill=PACK_P`) is too strict.
- A cut-off In3 3V3 island (R313.1 / TP301.1, 43 mm2) is fenced by the In3 tracks of 3V3_SLEEP and SCL across the
  strap end at 90.05,118.17; tying it back by route costs 12.6 mW (refused by the check) and no legal 3V3 via exists in
  the island (no-via area, In2 BTP_INT / TS1): it needs a plan fix (an In3 corridor there), not the finishing pass.
- A background job started with the default timeout is stopped after 30 min: give the resume run `timeout` 2 h.

## Phase 2 round 2: the lead's merge (plan p2-m4, one rebuild command)

`bash tools/rebuild_best.sh runs/<new> [--src=runs/p2a-r5src] [--route=80] [--fin=20]` is the one command from
`best_placement.json` to the routed, finished and scored board: source run (`screen.sh --hot=all`, skipped when
`--src` holds one), `final_route.sh` (straps, filters, full route, stub trim), then `final_route.sh --resume` with the
accept-or-revert pass and the seven hot loops. The straps and the filter string live in that script and nowhere else
(the same string as `FR6` in `runs/p2-m4plan/strings.sh`). Give the job a 4 h limit, or run its two printed commands
as two background jobs of 2 h each.

What the merged plan changed against worker A's `FR5`:
- **The trunk is back on the path of `runs/p2-m1`** (along the south of U403, north in a neck under pins 8 to 10).
  The two vias of `plan/p2-pins-u403.json` (pins 7 and 9 straight south) had pushed it onto a diagonal under pins 1
  to 6: I2CC_SCL, I2CC_SDA and CHG_INT lost every via site ("no way even with every other route gone" in the local
  and the PC route of `p2a-r5f`), SW2 lost its via site east of pin 18, and J113 went from 2.11 to 2.65 mohm.
  `plan/p2-pins-u403b.json` (before `trunk.py`) now lays the whole via row south of U403 first: pins 1, 2, 3, CE_N
  (pin 7 and R435.2), REGN (R415.1), and ICHG / ILIM (pins 9 / 10) EAST of the neck, north of TH104's B.Cu pads, plus
  the SW2 via. The row closes the diagonal, so the trunk can only take the old path; `trunk.py --g=0.05` (0.1 put the
  neck 0.1 mm off centre and lost a width step: 12.2 squares, 11.9 with 0.05).
- `plan/p2-pins-r6.json` = worker A's `p2-pins-r5.json` plus: CHG_G on F.Cu (R110.1 to Q101.4, the via of r5 is under
  the trunk again), the FBG / FB / SRN_F fan as three explicit paths east of the ILIM via, FSW (pin 36 west and south
  at x 107.92), ACOV (pin 35 to R410.2), TS (pin 8 to R416.1, R415.2 to R416.1), CE_N at R417.1 (via), SBU_FLT
  (U405.9 to R441.2), CELL_P at C110.1 (via in a notch of the FET_MID pour), and the 3V3 ties that the router used
  to make through the soft In3 pour: TP301.1 and R313.1 by F.Cu tracks into the 3V3 pour at C207.1, U204.10 by a via
  and a hard In3 link to the strap (`links.py --link=3V3|In3.Cu|0.3|86.12,117.52/90.14,117.52`, last filter).

Traps met:
- A via laid before `trunk.py` moves the whole trunk, not only its edge: look at the B.Cu picture after every change
  of the pre-trunk table (`pinlib.py look <spec> <cu.json> out.png "112.5,110.5@GND" --layer=B.Cu --r=6.5`), and
  read the trunk's "squares" in the filter log (11.3 on p2-m1, 12.0 on the diagonal, 11.9 now).
- Close the unwanted path with the vias the pins need anyway (the row south of U403) instead of an avoid box.
- Via pitch 0.75 mm exactly is refused (0.75 < 0.75 within EPS): use 0.76 or more.
- A table entry on a pad that already has a planner via says "already has copper, skipped"; `"force": true` runs it,
  but a via inside the pad is refused, so a planner via in a pad cannot be nudged with `drop` + `at`.
- A 3V3 or PACK_P pad tied by the router through a via into a SOFT inner pour is cut off again by later tracks (the
  In3 island of TP301.1 / R313.1 on both finished boards): tie such pads in the plan on F.Cu (`"to": "zone"`) or by a
  hard link.

## Phase 2 round 3: plan p2-m5, copper for the last four connections and the hot-pour nets (worker A)

`bash tools/rebuild_m5.sh runs/<new> --src=runs/p2a-r5src [--chain=<spec out>] [--screen] [--step=2|3]` is
`rebuild_best.sh` with the new tables `plan/p2-pins-u403c.json` (before `trunk.py`) and `plan/p2-pins-r7.json`, plus two
filters at the end. `--chain` builds only the plan (`spec_chain.sh`, under 1 min, for `pinlib.py look` pictures);
`--screen` is `final_route.sh --route=0 --no-hot`; `--step=2` / `--step=3` run the route step / the finishing step
alone (each a background job of 2 h); `--no-hotvia` leaves out the last filter (no-via areas) for a comparison.
`rebuild_best.sh` and the round 2 tables are unchanged.

What the plan adds to p2-m4's (each item screened, pictures in `runs/p2r3_work/*.png`):
- Port 1 SRN_F / SRP_F at R428 / R429: SRN_F via of R429.2 at 116.35,105.95 in the PRE-trunk table (the trunk covers
  that spot when it is laid first; the trunk moves round it, still 11.9 squares), then SRP_F as a table path R428.2 west
  along y 105.3 and south at x 115.65 into C417.1 (0.2 mm from the SW2 via, 0.4 mm from the SRN_F via).
- Net-(C313-Pad2): path C314.1 down to y 118.545, east, up into C313.2, in the 0.47 mm strip between the cap row and
  U301's pads (the window for a 0.15 mm track centre is 118.538 to 118.552). C313.1 (RFIO) must then leave north.
- Port 2 LDO_3V3: the R504.1 / R541.1 piece is boxed (PPHV track and pour, R504.2, U501 pins 17 to 19): table path
  R504.1 north to 93.95,85.05 and on to R541.1, with a via at that corner (`force` entry on R541.1).
- EN_5V1 / EN_5V2 long runs: **waypoint islands** (`links.py --via=NET|x,y --link=NET|In2.Cu|0.15|x,y/x,y+0.4`).
  KiCad lists a track island of a net as a ratsnest end, so the 53 mm edge becomes two edges under 30 mm (EN_5V1:
  island at 101.0,95.5; 27 and 28.6 mm) and EN_5V2's 60 mm edge three (islands 99.0,84.0 and 99.2,100.8; 20.8, 16.8,
  25.5 mm). A LONE via is not listed by KiCad (tested, `runs/p2r3_viatest`), so the island needs its stub track. The
  router starts from an island through `item_cells` / `island_cells` like from any pre-laid copper.
- Net-(U404-FB): table path pin 8 to R434.1 with `cut_hot` GND in a box east of C444.2 (0.18 mm2 of the HL_5V pour's
  corner, not on the loop's path). Port 1 HL_5V solved again on the copper board: 0.501 nH, per cap C446 0.306 /
  C444 0.741, the same as `runs/p2-m4s`.
- `ruleareas.py --hot --hot_mode=vias` as the last filter: no-via areas over the 14 hot-loop GND F.Cu return pours
  (70.5 mm2), so no router (the full route and the finishing pass both obey rule areas) drops a signal via into them
  (the Port 2 I2CC_SCL / SDA crossover vias of p2-m4).

Traps:
- A via search (`dir` + `via` without `at`) next to a same-net via laid by the entry before may put a SECOND via
  beside it instead of using the first: give `at` and `force` when an entry must join an existing via.
- `links.py` checks vias at 0.2 mm against inner-layer tracks (the In3 3V3 strap): a spot that `pinlib.check_via`
  passes at 0.15 may still fail there.

## Phase 2 round 3: loss pass, long edges, via-in-pad anchors (worker B)

The lead's call (same straps and filters as the route, `--resume` on an out dir with `routed.kicad_pcb`):
`final_route.sh ... --route=80 --resume --post="finish.sh --modes=aor,aork,loss --min=35 --tol=0.01 --long=30 --hand=<hand.json>"`
(start it as a background job with a 2 h limit). Mode `loss` is a third pass after the two accept-or-revert passes.

**Loss pass** (`finish.sh --modes=...,loss`, `router_b.py --aor --aororder=loss`):
- Rank: every rip-able piece with track cells (or vias) on In2 inside the outline of the PACK_P In2 pour is taken off the
  board, the PACK_P pours are refilled and `dc_score.score_net` solves PACK_P (0.1 mm); gain = PACK_P loss now minus
  loss without the piece (about 3 s a piece, 60 pieces in 3 min). Pieces of one net that each gain are also ranked
  together. Log line `aor loss: PACK_P ... best: <piece> <gain> mW, ...`.
- Task (best first, gain >= `--lossrank` 0.5 mW, at most `--lossn` 12 per sweep): the piece is pulled and laid again
  with the sheet closed: In2 cells inside the outline cost `--losscost` (250 history units, shut in practice) for every
  net but PACK_P, vias there `--lossvia` (20 mm-equivalent steps, i.e. dear). `--lossclose=full,box:3`: the whole
  outline first, then only the piece's box + 3 mm. Hot-loop pours stay closed (`--hotko`).
- Accepted only when every pulled piece is laid again, KiCad's unconnected count does not rise, the power check passes
  (no power open, no PACK_P terminal past 3.0 mohm or > 0.1 mohm up) and PACK_P + 3V3 + GND loss drops by `--lossmin`
  (1 mW) or more; otherwise grids, routes, history costs and board are put back. A piece refused in every mode is not
  tried again in a later sweep. finish.sh keeps the pass only when unconnected + DRC errors and hot-pour items do not
  rise and the board's dc_score loss drops by 1 mW or more (host-side `dc_score.py` on every candidate, cached as
  `fin/<board>.dc.json`). Options to the router: `--lossx="--lossn=20 --lossclose=full"`.
- `--lossonly=<regex>` (router) restricts the ranking to matching pieces, for a quick look at one net.

**Long edges** (`finish.sh --long=30` = `router_b.py --longmm=30 --longlegs`): an open connection at least 30 mm long
gets its own budget in an aor task: node cap `--longcap` (30 M, above the 12 M ceiling of every other search),
`--longtime` 900 s and `--longrips` 40 pulls; a failed search is tried again in two legs through a free via spot near
the middle (`--legband` 12 mm across the line, `--legtries` 6 spots, the second leg starts where the first ended and
keeps the via spacing, `astar(..., sv0=)`). Each long search prints `long edge <net> <mm>: search found|none, seen N`.
`--longx=--longptol=0.02` lets the power check of one long open task cost up to 20 mW (a later loss pass wins it
back); `--longx=--longclose` lays a long open task with the In2 PACK_P sheet closed, as the loss pass does.

**Via-in-pad anchors** (`--split`, on unless `--novip`): a routed via inside a pad of its own net (the router's
via-in-pad escapes, about 35 on p2-m4) is kept in the fixed world and the pieces end on it. Before, lifting such a
piece lost the via, and the pad (boxed in on F.Cu, e.g. TH401.1 of Port 1 TS inside the Port 1 pour) could not be
reached again ("no way even with every rip-able route gone" at once). Also: an edge whose two ends already share copper
(two anchors joined by fixed copper, 0.05 mm apart) counts as laid (A* never stops on a goal that is also a start).

Traps met:
- The two biggest cuts of the sheet were long Kelvin-free signal pieces (CELL3 32.8 mW, EN_5V2 31.8 mW on p2-m4): one
  task each, laid again off the sheet in 44 s and 27 s. Re-ranking after each sweep matters: Port 1 TS rose from
  3.2 to 15.4 mW once the other cuts were gone.
- Closing only the piece's box (box:3) seldom wins where the whole outline failed; most refusals are cascades
  (a pulled neighbour cannot be laid again within 12 pulls) or the power check (CHG laid again cost 3V3 / GND more
  than it saved on PACK_P).
- EN_5V1 (R432.1 to U301.12, 50 mm) is not a node-cap problem once the far end is known to be boxed: U301.12 has no
  free cell or via site on the real grid (`boxed`, 5000-node back search), the 3V3 F.Cu pour on its west and the
  escape vias of pins 11, 13 and 14 round it (`runs/p2b-r3dev/look/en5v1_u301.png`). With pulls the edge itself lays
  (42 k nodes), but the pulled pins (TS, NRST, SDA, CHG_INH, SWDIO, SWCLK, UART_TX) do not all go back.
