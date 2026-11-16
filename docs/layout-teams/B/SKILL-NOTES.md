# Team B skill notes: how to repeat the Monolith layout

Written for an agent that has not seen this work. All commands run from `docs/layout-teams/B/`; KiCad steps run in
docker `kicad/kicad:10.0`; host python3 with numpy, scipy, shapely, PIL. One router or hot-loop job at a time per
agent on a 4-core box. Read `tools/README.md` for the call form of every tool.

## Phase 1: placement (short)

1. Fixed parts stay (J, H, TP, SW and the cup's parts). Power stages first, from explicit coordinates: the hot-loop
   capacitors against the FETs, the inductor between the FET pairs. Then support parts by recipe
   (`tools/secplace.py`), one section at a time, each checked with `tools/screen.sh <run> <fragment> --partial`.
2. Stitch (`tools/stitch.py`), screen the whole board (`tools/screen.sh <run> best_placement.json --hot=all`), read
   `blame.py` for blocked edges by chip. Nudge a part at most 0.5 mm per blocked pin (`part_peek.py` first), never a
   power-stage or hot-loop part.
3. Look at `F.png` and `B.png`: a sprawling power part is a reject even if the numbers are good.

## Phase 2: from the placement to a routed, finished board

### Step 0: the one command
For the kept board (after round 3) see "After round 3 (lead)" at the end: `tools/rebuild_m6.sh ... --board=...`. For a new
route from the placement:
`bash tools/rebuild_best.sh runs/<new> --src=runs/p2a-r5src` runs steps 1 to 6 below (4 h limit, or its two printed
commands as two background jobs of 2 h each). Do the steps by hand when something changes.

### Step 1: source run
`bash tools/screen.sh runs/<src> best_placement.json --hot=all`: bare board, `spec.json` (the copper plan), `cu.json`,
the seven hot loops before routing. Keep it; every later step reads it (`runs/p2a-r5src` for placement r5).

### Step 2: straps and filters, in this order (strings in `runs/p2a-look/strings.sh`, then `runs/p2-m4plan/strings.sh`)
- `--straps="$ST"`: 3V3 on In3 (`--net=3V3 --layer=In3.Cu --source=J301 --lanes=H --w=0.5 --wmin=0.5`).
- `--filters="$FR6"`, each filter `python3 tools/<script> <spec in> <cu.json> <spec out> <options>`:
  1. `links.py` (explicit power links, e.g. the Port 2 BAT_SNS_P island);
  2. `ruleareas.py --protect=3V3:F.Cu,PACK_P:F.Cu`;
  3. **pin table BEFORE the trunk** (`pins.py --rules=table --table=plan/p2-pins-u403b.json`): the vias U403's pins
     need anyway. They decide where the trunk can go.
  4. `trunk.py --w=5 --narrow=U403:0.8:2.0 --g=0.05`: PACK_P on the 2 oz bottom from Q102 to J113 and R427. Read
     "squares" in `split/filter_<n>.log` (11.3 to 11.9 is right; 12.0 means the diagonal under U403).
  5. `straps.py --net=PACK_P --layer=In2.Cu --source=Q102 --lanes=V --across=15`;
  6. Port 1 VBUS link (`$LP1`), **pin table AFTER the trunk** (`pins.py --table=plan/p2-pins-r6.json`), Port 2 VBUS and
     3V3 links (`$LP3`).
- After every change of a pre-trunk table: look at the B.Cu picture
  (`python3 tools/pinlib.py look <spec> <cu.json> out.png "112.5,110.5@GND" --layer=B.Cu --r=6.5`).

### Step 3: screen
`bash tools/final_route.sh runs/<src> runs/<new>s --straps="$ST" --filters="$FR6" --route=0 --no-hot`: blocked edges
must be 0, copper-board DRC 0, power open none, loss before routing about 1.01 W. A blocked edge means a table row is
missing (rule rows: `ep` for a QFN GND pin, `gate` for a gate pad wrapped by its stage's pour; explicit rows: `via`,
`at`, `to`, `path`).

### Step 4: full route
`bash tools/final_route.sh runs/<src> runs/<new> --straps="$ST" --filters="$FR6" --route=80 --no-hot --post="finish.sh --no-route"`
(about 40 min; the stub trim cures the router's own clearance errors). Queue the same copper board on Logan's PC for
the spread (two routes of one board differ by about 4 edges); the PC returns counts only.

### Step 5: finishing pass
`bash tools/final_route.sh runs/<src> runs/<new> --straps="$ST" --filters="$FR6" --route=80 --resume --post="finish.sh --modes=aor,aork,loss,loss --min=35 --tol=0.01 [--hand=<hand.json>]"`
as a background job with a 2 h limit (`runs/p2b-r3fin` took 60 min for aor, aork, loss with `--long=30`, which spent
about 15 min on EN_5V1 alone; a second loss pass gained 6.7 mW more on `runs/p2b-r3en`). In order:
1. stub trim, dead power copper removed (`fin_islands.py`, `fin_dead.py`);
2. `aor`: one open connection (shortest first) or one hot-pour piece per task; kept only if KiCad's unconnected count
   drops (or holds with fewer hot-pour items) and the power check passes; else everything is put back;
3. `aork`: the same, Kelvin pieces may be pulled;
4. `loss`: In2 pieces ranked by what they cost the PACK_P sheet, the worst laid again with the sheet closed, kept only
   when the loss drops by 1 mW or more and nothing else gets worse;
5. hand tracks (`handroute.py`, exact check; coordinates belong to ONE board), dangling ends, power guard
   (`fin_guard.py`: the finished board is never worse than the routed one).

### Step 6: routed-board check
`final.json` of the run: `routed.unconnected_items`, `routed.drc_errors`, `routed.power_open`, `routed.loose`,
`routed.unconnected_power`, `routed.loss_W`, `routed.pack_p_mohm`, `routed.hot_pour_items`, `hot_routed`. Then the
renders: `python3 tools/zoom.py <run>/routed <out.png> 78,62.4,122,137.6 <layer> 20` for F.Cu, B.Cu, In2.Cu, In3.Cu.

### What to look at
- In2: the PACK_P sheet between Q102 (97.5,118.7) and J113 / R427 (119.4,109 / 119.9,104.9). Long north-south tracks
  through it are loss; `aor loss:` in `fin/r3.log` ranks them.
- B.Cu: the trunk is one strip along the south of U403 and north through the neck; no diagonal under U403.
- F.Cu / B.Cu: no signal track or via in a hot-loop pour (`routed/hot_tracks.json`).
- In3: the 3V3 bus whole; tracks moved there by the loss pass run east-west mostly; watch for long detours.

### Traps
- A via laid before `trunk.py` moves the whole trunk. Close unwanted paths with the vias the pins need anyway.
- Via pitch exactly 0.75 mm is refused (EPS): use 0.76.
- 3V3 / PACK_P pads tied through a via into a SOFT inner pour get cut off again by later tracks: tie in the plan.
- A finishing pass without the power check cuts the PACK_P sheet to close connections.
- A background job with the default timeout stops after 30 min: give resume runs 2 h.
- `router_b.py --split` pieces: a via inside a pad of its own net stays fixed (since round 3); before, lifting the
  piece lost the only way into a boxed pad (Port 1 TS at TH401.1).
- "no way even with every rip-able route gone" can mean the far end is boxed (the 5000-node back search): look at the
  pad before raising node caps. EN_5V1's U301.12 is boxed by pins 11, 13, 14 escapes and the 3V3 F.Cu pour.
- hand.json coordinates are valid only on the board they were made on; on another board the exact check refuses them
  (nothing is written) and finish.sh drops the step.
- Loss in the per-task power check (PACK_P + 3V3 + GND at 0.1 / 0.2 mm) is not the board's dc_score sum; finish.sh
  judges the pass with the full `dc_score.py` on the host.

### After round 3 (lead): from "one connection left" to 0, and the one command
- The kept board: `bash tools/rebuild_m6.sh runs/<new> --src=runs/p2a-r5src --board=best_routed/monolith_routed.kicad_pcb`
  (plan p2-m6 + screen, the board as routed.kicad_pcb, `final_route.sh --resume` with the pass and the hot loops).
- **A plan change after a good route: do not route again.** Diff the plan copper (tracks and vias of the two
  `cu.kicad_pcb`), check the routed copper against the new plan (`handroute.py --check`), cut the change down to what
  the board does not hold yet, then `transplant.py` and one `aor` pass. Two routes of nearly one plan fail different
  connections; one copper board (p2-m4) gave 341 of 342 locally and 333 of 342 on Logan's PC.
- **The last open connection: tolerances from the gates.** Read the refusal reason in `fin/r*.log`. "power: ..." with a
  few mW or a terminal 0.1 mohm up is the pass protecting itself, not a gate: `--long=30 --longx=--longptol=0.05
  --aorx=--prtol=1.0`, and check the gates on final.json afterwards (loss 1.25 W, J113 / R427 3.0 mohm).
- Then look where that connection runs (`zoom4.py`): a long north-south In2 run inside the PACK_P sheet is loss; the
  router prefers In2 for north-south even where In3 has room nearby. That is a hand job (`handroute.py` with
  `"lift": [net]`), not a loss-pass job.
- Traps: vias written by a script need the router's pad options (`SetRemoveUnconnected(True)`,
  `SetKeepStartEnd(True)`) or every plane loses copper; dropping only the vias of a layer change leaves an open that
  the router cannot see; `--longptol` applies to every long open edge.
