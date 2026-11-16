# Team B skill notes: how to place and route the Monolith board

For an agent that has not seen this work. Follow the parts in order: place the parts chip by chip (part 2), lay the
copper plan (part 3), route and finish the board (part 4). `tools/README.md` has the call form of every tool;
`REPORT.md` has the numbers each step reached.

## 0. Ground rules

- All commands run from `docs/layout-teams/B/`. KiCad steps run in docker `kicad/kicad:10.0`; host python3 needs
  numpy, scipy, shapely, PIL.
- One router or hot-loop job at a time per agent on a 4-core box. Every run gets its own directory `runs/<name>/`.
- A job over 10 min runs as a background job with a 2 h limit. The default limit of 30 min kills a resume run.
- Never edit a shared tool in `tools/score/` or `tools/copper/`: copy it into `tools/` here.
- Report only numbers that a run printed, with the run directory. Say when a route hit its time cap.
- Look at the pictures before calling a board good. A sprawling power part is a reject even with good numbers.
- Run `git commit` as a command of its own, not chained with other commands. No model names in files or commits.

What "done" means:

| Step | Pass |
|---|---|
| Placement, whole-board screen | DRC 0; `power_open` holds only GND at J301, J302; `tools/loose.py` prints nothing; 7 of 7 hot loops tier 1; blocked edges below the hand board's 56 of 452 |
| Copper plan, screen | 0 blocked edges; DRC 0; `power_open` empty |
| Routed board, `final.json` | `routed.unconnected_items` 0; `routed.drc_errors` 0; `routed.power_open`, `routed.loose`, `routed.unconnected_power` empty; `hot_routed.pass_count` 7 of 7; `hot_routed.sum_nH` within 0.05 of the value before routing; `routed.loss_W` 1.25 or less; `routed.pack_p_mohm` J113 and R427 3.0 or less; `routed.hot_pour_items` 0 tracks, 0 vias |

## 1. Before placing

1. **Fixed parts.** Do not move J, H, TP and SW parts, nor the cup-fixed ones: U301, L401, L501, TH101, TH104, TH401,
   TH501, C208 to C213, C421, C456, C521, C556. That leaves 245 movable parts (`plan/clusters_movable.json`).
2. **Check the floorplan boxes against the fixed parts** (`tools/draw_boxes.py`). A box that holds a fixed part of
   another section, or misses its own anchor, is amended and the reason written down (`plan/boxes_B1.json`). A stage
   goes where its fixed inductor is. A chip's own resistors and capacitors go in the chip's box.
3. **Groups.** Port 1 (x over 100, y under 113.6), Port 2 (x under 100, y under 113.6), pack side (y over 113.6).
   Each group stays 0.4 mm back from its region line.
4. **Border reserves, in every recipe** (`recipes/common/border.json`): two via fields free of parts on both sides
   (top 98.6..101.4, 83.8..87.8 and bottom 99.6..103.4, 113.0..115.2) and the centre area 96.5..103.5, 102.8..113.0,
   which takes no part except R527. The signals that cross between groups run through these.
5. **Pass marks.** Screen the hand placement whole (`bash tools/screen.sh runs/hand_screen ...`, 56 of 452 blocked,
   1.36 W) and each group alone (`--partial`: Port 1 27 of 180, Port 2 42 of 173, pack 7 of 156). A partial screen
   is compared only with the hand's partial screen of the same group.

## 2. Placement, chip by chip

### 2.1 The six steps for every section

A section is a recipe file `recipes/<group>/<nn>-<section>.json`, run by `tools/secplace.py`. In this order:

1. **Main chip**, explicit spot and turn (`put`). Power pins face their source or load. Pins of nets that leave the
   section face the border they leave by. At most three variants; keep the one the screen likes.
2. **Escape ring** (`ring`) round every chip with 12 pads or more: no other courtyard within 0.8 mm of a pad row with
   signal pins. Allowed inside: a capacitor that serves a pin of that row, at 0.3 mm, lying radially.
3. **Hot-loop capacitors, pad to pad** (`hot`): the first capacitor's supply pad within 1.5 mm of the switch's supply
   pads, its return pad within 1.5 mm of the return pads, no pad of another net between. Then the other capacitors
   of the loop (`"soft": true` and a looser `max_mm` for those).
4. **Switches, inductor, sense**: FETs at the inductor pads, bootstrap parts, sense resistors in the current path
   with the two Kelvin taps leaving as a pair from the inner pad edges.
5. **Own resistors and capacitors at their pins** (`at_pin`), most constrained first. GND, PACK_P and 3V3 are never a
   target.
6. **Screen and look**: `python3 tools/check.py <fragments> --group=<g> --png=...` (0 hard faults), then
   `bash tools/screen.sh runs/<name> fragments/<g>.json --partial --hot="<this section's loops>"` (about 5 min plus
   1.5 min per loop), then `python3 tools/blame.py runs/<name>`, then read `F.png` and `B.png`.

Reserve boxes before parts (`reserve`): a strip the power copper needs, a via field, an escape yard.

### 2.2 Port 1 (`recipes/port1/01-stage.json` to `06-9v.json`)

**a. Stage** (L401 is fixed; box 100.2..121.1, 88.0..102.8).
1. Q401 (port leg) and Q402 (battery leg) south of L401, side by side, pad 9 (SW) toward the L401 pad of its net.
2. C430 across Q401 pads 2 to 4 and 5 to 7; C438 the same across Q402.
3. C420, C423 (loop HL_IN), C431, C434 (HL_OUT), then C424, C427. Keep the vias to the bottom capacitors C456 and
   C421 free on top.
4. Gate resistors R444 to R447 on the charger side; bootstrap C412, C413, D404, D405 between the FETs and U403.
5. R424 between U401 pad 20 and the input capacitors; R427 between Q402's supply pads and J113.
6. Screen with `--hot="USB Port 1/HL_IN,USB Port 1/HL_OUT"`. Reached: 0.78 and 0.74 nH.
   Read `hot.json` per capacitor: a value in the thousands of nH means the capacitor is not reached by copper. The
   planner refuses a B.Cu detour over 10 mm; C420 had to move 0.3 mm east to join.

**b. Charger U403** (box 103.5..117.3, 102.8..113.6; gate-drive pads 19 to 28 face the FETs). Ring first, then each
part at its pad (`PLAN.md` section 4 lists part by pad). Do these from the start; they each cost a blocked edge
when missed:
- No capacitor pad straight in front of signal pins. C409 stands 1.9 mm from pin 33, not 0.67 mm in front of pins
  34 and 35. C412 sits over pin 28, not pin 27.
- R410 stands at the stub ends of pins 34 and 35; its pads keep the PPHV copper out of the lane.
- Leave a lane 0.5 mm wide from pin 12 to R419 (C417, C419 clear of it).
- A Kelvin tap must sit on its own net's planned copper, because the router never routes to a sealed tap. R426 pad 1
  0.6 mm under C427 pad 1; R428 in the west mouth between R427's pads; R429 lying with its tap pad on the PACK_P
  copper beside R427 pad 2.

**c. 5 V buck U404** (east column, `03-buck5v.json`). C446 with its PACK_P pad over VIN pad 3 and its GND pad over
GND pad 4, about 0.5 mm off the pins; give the `hot` step `"ret": ["1", "4"]`. Then C444, L402 pad 1 at pad 5, the
small parts at their pins, C441 to C443 at L402 pad 2. C443 stands as a bridge at 112.75, 81.9 so PP5V reaches U401
pad 34; reserve the B.Cu box 103.6..113.6, 75.6..82.65 for that detour. Screen with `--hot="USB Port 1/HL_5V"`
(reached 0.70 nH). `bash tools/plan_only.sh <outdir> <placement.json>` (plan and DC only, about 45 s) shows whether
PP5V joins.

**d. PD controller U401 with U402** (`04-pd.json`).
- South row: a yard free of parts on both sides, (102.8, 82.85) to (108.4, 84.08), and a wall south of it: C408,
  U402, R402, R403, R404 in a row. PPHV leaves pad 20 to the east past R424 and runs west south of the wall.
  `python3 tools/yard_check.py` tells whether power copper can leak into the yard.
- North row: C450 stands over pad 32 (VBUS), C402 over pads 29 and 30 (CC2), C401 over pads 26 and 27, each 0.5 mm
  over the row, so no VBUS copper can run along the row. C407 at pad 34 (PP5V).
- C406 (4.7 uF) stands east of pad 23 with its VBUS pad 0.56 mm from the pad. Without it the 5 A pad 23 is left on
  an island that the scorecard does not flag. Run `python3 tools/loose.py runs/<name>` on every screen.
- Its 4 mm rule to the connector is waived for C406 (and C506): they serve the PD chip's pad, the TVS guards the
  connector.

**e. Port protection U405, D401** (`05-protect.json`). U405 between J401's CC pads and U401 pads 28, 29, with C_CC1
and C_CC2 toward the connector. D401 (TVS) and the VBUS trunk at the connector, in the path. Keep U405 far enough
north that C407's PP5V copper, which grows 1.5 mm, does not reach the escape room of U405 pins 11 and 12. C451 went
to the bottom (no top spot within 2 mm of pin 3).

**f. 9 V supply** (`06-9v.json`): on the bottom (7 parts); the top variant does not fit. D411 and C458 on top north
of the stage, D410 in the strip west of the stage.

### 2.3 Port 2 (`recipes/port2/01-stage-charger.json` to `05-9v.json`)

- **Stage and charger are Port 1's, shifted by (-23.02577, +0.006368) mm.** Write them as explicit spots with
  `python3 tools/twin_recipe.py`; secplace's `translate` turns some twins wrong. While placing Port 1, keep
  `twin_check` on so no Port 1 spot is taken whose copy cannot exist. Not copied: R524, R527 (R527 at 96.87, 104.91 in
  the centre area), R513, R514, and in the end R509, D505, R528 and the bottom D511, each for a Port 2 cause.
- **5 V buck** in the north-west corner (U504 near 83.9, 68.0; L502 at 83.85, 73.68), C546 laid like C446.
- **PD controller U501** at 91.5, 81.7. South yard x 88.95..94.15, y 84.22..85.48 with a wall: C505 standing at the
  west end, R502 to R504 in a row at y 85.9, R541 standing at the east end. North row: C550 lies flat over pad 32
  with its VBUS pad over the pad (x 91.70; 91.65 gave a DRC error), C501 and C502 over the CC and GND pads. C506 stands
  east of pad 23 as C406 does. U502 and its pull-ups stay on top, west of U501.
- **TVS D501 at the connector** (97.9, 71.67), not at the PD chip. U505 east of H102.
- **9 V supply on the bottom**, with D510 and D511 (10 parts).

### 2.4 Pack side (`recipes/pack/`, order in `recipes/pack/ORDER`)

1. Cell path: F102 at J112, Q102 at 97.46, 118.74 and Q101 at 104.93, 118.74 (both turn 0, as on the hand board),
   RS101 between J108 and J114. Screen both FET orders and keep the lower loss with all paths joined.
2. Keep the CELL_P corridor west of H103 free with reserves (CELL_P 0.241 to 0.107 W).
3. Gate parts at Q101 pad 4 and Q102 pad 4.
4. Gauge U101: ring, supply parts, the cell filters at the VC pads, Kelvin parts R107, R108 at RS101's inner pad edges.
5. MCU parts in the rim round U301, each at its pin.
6. Q104's gate parts, then the second-level protector U102 on top beside the gauge. On the bottom it walled the
   TS1 path.
7. 3V3 buck U204: C206 across the VIN and PGND pads, L201 at pad 9. Screen with `--hot=HL_3V3` (reached 1.02 nH).

### 2.5 Stitch, whole-board screen, fix loop

```
python3 tools/stitch.py fragments/port1.json fragments/port2.json fragments/pack.json --out=candidates/<rN>.json
bash tools/screen.sh runs/<rN>-hot candidates/<rN>.json --hot=all        # blocked edges, DRC, loss, 7 hot loops
python3 tools/blame.py runs/<rN>-hot                                     # blocked edges by chip and group
python3 tools/loose.py runs/<rN>-hot                                     # must print nothing
bash tools/split_screen.sh runs/<rN>-hot runs/<rN>-split [--route=45]    # the fair count: one zone per outline
```

Then, for each blocked edge, in this order:
1. Find the cause before moving anything: `bash tools/quick_ghost.sh` for the one net, `python3 tools/zoom.py` for
   the picture, `python3 tools/part_peek.py` for the room round a part.
2. Make the smallest move of one small part that removes the cause. Never move a power-stage or hot-loop part.
3. Partial screen of that group with its hot loops; then stitch and screen the whole board.
4. Fix Port 1's charger first; rebuild Port 2's twin from it.

Stop placing when the blocked edges that are left have no part standing in the way: pins wrapped by their own
stage's pour (HG2), QFN GND pins with no via room, CC pins under the protection chips. Those are copper-plan rows
(part 3). On this board that point was 19 of 437 (15 of 415 with zones split).

### 2.6 What to look at

- `F.png`, `B.png`: each stage is a compact block with the inductor between the FET pairs and the hot-loop
  capacitors against the FETs. No power pour runs across a section.
- The pin rows of U401, U501, U403, U503 (`tools/zoom.py`): no power copper along a row, a free lane out of each
  signal pin.
- `hot.json`: every loop tier 1 and no capacitor in the thousands of nH.

### 2.7 Traps

- The placer's hot-loop cost does not see the copper planner. A capacitor 0.27 mm off opened the loop and GND at
  U404. Screen after every `hot` step; hold the capacitor with `within` or `put` where the loop closes.
- The placer is greedy: a small part placed early strands its neighbour. Big parts first, `reserve` what a later
  part needs, `within` boxes, `step: 0.05` in tight gaps.
- `power_open` empty does not mean every pad is joined. Run `loose.py`.
- The plain scorecard loses every zone outline but the first. Compare split with split.
- More planner escape room (`--plan="--escape=0.8"`) lowers blocked edges and opens PP5V at U401. Not usable.
- Whole small-signal sections may go to the bottom; a stray part, a hot-loop capacitor or a Kelvin part may not.
  A part in the planner's B.Cu power pour is boxed in.
- Do not round positions (6 decimals). Compare losses at 0.01 W; the 4th decimal is noise.
- Two routes of one copper board differ by about 4 connections. A difference of 1 to 3 is no result.

## 3. Copper plan before routing

The router closes only what it can reach. Everything else is laid first, as hard copper, by filters on the plan.
The strap and filter strings live in `tools/rebuild_m6.sh` and nowhere else; change them there.

1. **Source run**, once per placement: `bash tools/screen.sh runs/<src> best_placement.json --hot=all`. It holds the
   bare board, `spec.json` (the plan), `cu.json` and the seven loops before routing (`runs/p2a-r5src` for r5).
2. **Straps and filters, in this order.** Each filter is `python3 tools/<script> <spec in> <cu.json> <spec out> ...`.

   | Order | Filter | Why |
   |---|---|---|
   | straps | `--net=3V3 --layer=In3.Cu --source=J301 --lanes=H --w=0.5 --wmin=0.5` | the route cuts the soft 3V3 pour on In3 |
   | 1 | `links.py` (explicit links, e.g. the Port 2 BAT_SNS_P island) | pieces the planner leaves apart |
   | 2 | `ruleareas.py --protect=3V3:F.Cu,PACK_P:F.Cu` | keeps signals out of the soft F.Cu power pours |
   | 3 | `pins.py --rules=table --table=plan/p2-pins-u403b.json` | the vias U403's pins need anyway, BEFORE the trunk: they decide where the trunk can go |
   | 4 | `trunk.py --w=5 --narrow=U403:0.8:2.0 --g=0.05` | PACK_P on the 2 oz bottom from Q102 to J113 and R427 |
   | 5 | `straps.py --net=PACK_P --layer=In2.Cu --source=Q102 --lanes=V --across=15` | keeps the In2 sheet joined |
   | 6 | `links.py` for the Port 1 VBUS pin pairs (B.Cu link at y 69.25) | the router never joins two zones |
   | 7 | `pins.py --table=plan/p2-pins-r8.json` | every pin escape, AFTER the trunk |
   | 8 | `links.py` for the Port 2 VBUS pin pairs and the 3V3 In3 links | as 6; 3V3 ties belong in the plan |

3. **Plan only, then screen.**
   ```
   bash tools/rebuild_m6.sh runs/<new> --src=runs/<src> --chain=runs/<new>.spec.json  # plan only, about 1 min
   bash tools/rebuild_m6.sh runs/<new>s --src=runs/<src> --screen                  # blocked edges, DRC, loss
   ```
   Pass: 0 blocked, copper-board DRC 0, `power_open` empty, loss before routing about 1.01 W.
4. **A blocked edge means a table row is missing.** Rule rows: `ep` (a QFN GND or 3V3 pin stubbed into its exposed
   pad), `gate` (a gate pad cut out of its stage's pour). Explicit rows: `via` with `dir` or `at`, `to` (a whole
   one-layer connection, also `"to": "zone"`), `path`. To add one:
   ```
   python3 tools/pinlib.py look <spec.json> <cu.json> out.png U405.5 --r=2.6                      # look at the pin
   python3 tools/pins.py in.json cu.json out.json --rules=table --table=my.json --only=U405.5 --dry
   ```
   Row order matters: an earlier via can close a later pin. Put the tight pin first with a `keep` strip for its
   neighbour.
5. **Check the trunk** after any change to a table that runs before it. Read "squares" in
   `<run>/split/filter_<n>.log`: 11.3 to 11.9 is right, 12.0 means the diagonal under U403. Look at the B.Cu
   picture (`python3 tools/pinlib.py look <spec> <cu.json> out.png "112.5,110.5@GND" --layer=B.Cu --r=6.5`): one
   strip along the south of U403 and north through the neck.

Traps:
- A via laid before `trunk.py` moves the whole trunk. Use that on purpose: close the unwanted path with vias the
  pins need anyway.
- Straps on In2 keep PACK_P joined but not low in resistance (J113 15.6 mohm with straps alone). The 10 A path
  must be the bottom trunk.
- Via pitch of exactly 0.75 mm is refused; use 0.76.
- A 3V3 or PACK_P pad tied through a via into a soft inner pour is cut off again by later tracks. Tie it with a
  hard link or a track into the pour (`"to": "zone"`).
- Never cut a hot-loop pour except where it is off the loop's path, and solve the loop again (0.01 nH at most).
- Do not put everything into the plan at once. More plan copper changes which connections the route fails.

## 4. Routing to completion

### 4.1 Full route and stub trim

```
bash tools/final_route.sh runs/<src> runs/<new> --straps="$ST" --filters="$F" --route=80 --no-hot \
     --post="finish.sh --no-route"
```
About 40 min. The stub trim (`tools/fin_trim.py`) cures the router's own clearance errors at 0.4 mm pitch pins.
Queue the same copper board on Logan's PC for the spread (charter, "Full routes on Logan's PC"); it returns counts
only. `tools/rebuild_best.sh runs/<new> --src=runs/<src>` chains 4.1 and 4.2 for the plan of round 2; it was never run
end to end, its two commands were run by hand.

### 4.2 Finishing pass

```
bash tools/final_route.sh runs/<src> runs/<new> --straps="$ST" --filters="$F" --route=80 --resume \
     --post="finish.sh --modes=aor,aork,loss,loss --min=35 --tol=0.01"
```
Background job, 2 h limit (60 min on `runs/p2b-r3fin`). The modes, in order:
- `aor`: one open connection (shortest first) or one piece of copper in a hot-loop pour per task. The task is kept
  only if KiCad's unconnected count drops (or holds with fewer hot-pour items) and the power check passes;
  otherwise the board is put back.
- `aork`: the same, and Kelvin pieces may be pulled.
- `loss`: the In2 pieces inside the PACK_P sheet are ranked by what each costs, the worst is laid again with the
  sheet closed, kept only when the loss drops by 1 mW or more. A second `loss` pass gained 7 mW more.

Then read `final.json` (`--resume` also runs the seven hot loops) and `fin/r*.log`.

### 4.3 What is left, by cause

| What the log or picture shows | Cause | Cure |
|---|---|---|
| "no way even with every other route gone", also on the PC route | a pin is boxed, or a trunk or pour took its via site | a table row in the plan (part 3), then 4.4 |
| the same, for a long edge, with "seen -12000001" | node cap, or the far end is boxed | look at the far pad first (`tools/zoom4.py`); `--long=30` in the pass |
| "power: ..." refusal of a few mW or 0.1 mohm on the last connection | the pass protects itself; this is no gate | 4.5 |
| a task refused in every sweep because pulled neighbours do not go back | the piece cannot move alone | hand tracks (4.6) |
| a short gap between two vias or pads that the grid misses | grid router | hand tracks (4.6) |
| unconnected item between two zones of one net | the router never joins two zones | `links.py` in the plan |
| items in `routed.hot_pour_items` that every lift task fails | the layer change has no other spot the router sees | 4.6 |

### 4.4 A plan change after a good route: carry the copper over, do not route again

Two routes of nearly one plan fail different connections, and the pass may close neither set.
1. Cut the plan change down to what the board does not hold yet.
2. Check the routed copper against the new plan: `python3 tools/handroute.py <plan board B> x.kicad_pcb all.json
   --check --keep=<plan board B>`. Faults "on pad", "via spacing 0.752 / 0.75" and "board edge 0.25 / 0.25" are
   the checker's strictness, not real.
3. `python3 tools/transplant.py <routed board A> <A's plan board> <plan board B> <out> [--drop=<json>]`, or
   `bash tools/rebuild_m6.sh runs/<new> --src=runs/<src> --transplant=<run dir A>`.
4. One `aor` pass lays what the change opened.

### 4.5 The last open connection: tolerances from the gates

The pass's limits (2 mW a task, 5 mW a pass, 0.1 mohm a terminal) protect a board with many open connections. For
the last one use `--long=30 --longx=--longptol=0.05 --aorx=--prtol=1.0`, then check the gates on `final.json`.
`--longptol` covers every open edge of 30 mm or more, so use it only when the long edge is the one you mean.

### 4.6 The last items by measurement and hand copper

For a signal via in a hot-loop pour, or a signal that costs too much loss:

1. **Name the item and its cost.**
   - Hot-pour items: `python3 tools/hot_tracks.py <plan board> <cu.json> <board>`.
   - Cost of one signal: a hand file with only `"lift": [net]`, apply it with `handroute2.py`, then
     `python3 ../../../tools/copper/dc_score.py <board> <run>/routed/cu.json
     ../../../tools/floorplan/example/monolith/constraints.json out.dc.json` (40 s; `runs/p2r4_en/ev.sh` does both).
     The difference to the board is what the net costs.
   - Put parts of the net back and measure again to find which part costs. On this board 26 of EN_5V1's 38 mW were
     its last 10 mm, not its 40 mm run.
2. **Look at the current, not the sheet**: `python3 tools/sheet_flow.py <board> <cu.json> out.png`. A signal may
   cross a sheet where little current flows. The dear place is where the current is squeezed: here the south edge
   of the In2 PACK_P sheet into J113 and R427.
3. **Find which pours are hot** before moving a via (the hot loops' pours on the plan board). A layer change may sit
   in a quiet DC pour (here PPHV). Not in a hot-loop pour, and not in a switch-node pour.
4. **Lay it again.** By hand coordinates when the room is plain in `python3 tools/zoom4.py <board> <cu.json> out.png
   x0,y0,x1,y1`; with `python3 tools/lane_search.py` when the path is long (about 100 s for a 14 x 57 mm box; it
   charges per mm inside power pours).
5. **Apply**:
   ```
   python3 tools/handroute2.py <board> <out board> <hand.json> --cu=<run>/routed/cu.json \
        --keep=<plan board> ["--soft=<quiet pour net>"]          # add --check first
   ```
   It must print 0 faults, DRC 0, unconnected 0. Give every new via `"rmun": true`. Two hand files can be joined
   into one when their copper does not meet.

### 4.7 Final check

```
bash tools/rebuild_m6.sh runs/<new> --src=runs/<src> --board=<handroute2 output>           # about 7 min
bash tools/rebuild_m6.sh runs/<new>v --src=runs/<src> --board=runs/<new>/finished.kicad_pcb
cmp runs/<new>/finished.kicad_pcb runs/<new>v/finished.kicad_pcb                           # must be equal
```
Keep `finished.kicad_pcb` of the first run, not the handroute output: the first check may still remove dangling
ends. Then the pictures, each with the Read tool:
`python3 tools/zoom.py runs/<new>/routed <out.png> 78,62.4,122,137.6 <layer> 20` for F.Cu, B.Cu, In2.Cu, In3.Cu, and
a `zoom4.py` picture of every spot that was changed by hand. Copy the board, its `.kicad_pro` and `.kicad_dru`,
`final.json` and the four pictures to `best_routed/`.

### 4.8 What to look at on the routed board

- In2: the PACK_P sheet between Q102 (97.5, 118.7) and J113 / R427 (119.4, 109 / 119.9, 104.9) is one piece. Long
  north-south signal tracks through it are loss; `aor loss:` in the `fin/` log ranks them.
- B.Cu: the trunk is one strip, with no diagonal under U403.
- F.Cu and B.Cu: no signal track or via in a hot-loop pour (`routed/hot_tracks.json`).
- In3: the 3V3 bus is whole. Removing a signal track can let a pour flow into the room it held; look again after
  every hand file.

### 4.9 When to stop

Stop when every gate in part 0 is met and what is left of the loss is named per net (`dc.json` against
`routed/dc.json` of one run). On this board that is PACK_P +125 mW and GND +32 mW, with EN_5V1 still at 7 mW. Going
further is step 4.6 on the next dearest In2 signal, not a new route: two routes of one plan differ by more than
these last steps gain.

### 4.10 Traps

- A finishing pass without the power check closes connections by cutting the PACK_P sheet.
- `tools/handroute.py` removes no In2 or In3 item on this board (KiCad user layer names) and its writer fails in
  KiCad 10. Use `tools/handroute2.py`.
- Hand-file coordinates are valid only on the board they were made on. On another board the exact check refuses
  them and nothing is written.
- A via written by a script needs the router's pad options (`"rmun": true`; in pcbnew `SetRemoveUnconnected(True)`
  and `SetKeepStartEnd(True)`), or every plane gets a wider antipad (+29 mW here).
- In a carry-over, do not drop only the vias of a layer change: the two track ends lie on one spot, the router
  counts the edge as laid and KiCad does not. Drop the whole piece or carry it over.
- No-via areas over the hot pours are for a new route only. On a board that already has vias there the pass lifts
  the pieces and cannot lay them all again.
- The loss in the pass's per-task power check (PACK_P + 3V3 + GND on a coarse grid) is not the board's loss.
  Judge by `dc_score.py` on the whole board, which is what `final.json` holds.
- The loss pass cannot move a net whose neighbours must move too, and it laid EN_5V1 worse. Such nets are 4.6.

## 5. Tools by step

| Step | Tools |
|---|---|
| Place a section | `secplace.py`, `twin_recipe.py`, `recipe_put.py`, `part_peek.py`, `check.py`, `yard_check.py` |
| Screen | `screen.sh` (`--partial`, `--hot=`), `plan_only.sh`, `quick_ghost.sh`, `split_screen.sh` |
| Read a screen | `blame.py`, `loose.py`, `zoom.py`, `near.py`, `padconn.py` |
| Stitch | `stitch.py` |
| Copper plan | `straps.py`, `links.py`, `ruleareas.py`, `pins.py`, `pinlib.py look`, `trunk.py`, `spec_chain.sh` |
| Route and check | `final_route.sh` (`--resume`, `--post=`), `final_json.py`, `hot_tracks.py`, `netclusters.py` |
| Finish | `finish.sh` (`fin_trim.py`, `router_b.py --aor`, `fin_islands.py`, `fin_dead.py`, `fin_clean.py`, `fin_guard.py`) |
| Change after a route | `transplant.py`, `handroute2.py`, `lane_search.py`, `sheet_flow.py`, `zoom4.py` |
| One command | `rebuild_m6.sh` (kept board, or `--transplant`), `rebuild_best.sh` (a new route) |
