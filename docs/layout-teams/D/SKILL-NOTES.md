# Team D method: a lead plans, cheaper workers place and route by hand

Written so a cheaper model can follow it. Two roles: the **lead** (strong model) decides the floorplan and the
interconnect plan and reviews; **workers** (cheaper model, one per room or region) decide every coordinate inside
their area with scripted helpers that check each step. Everything is under `docs/layout-teams/D/`.

## Placement

### Lead, before any worker starts
1. Score the reference board first (`bash tools/qs.sh hand`) and read `dc.json`: which power paths lose the most,
   which connections are blocked and where. On Monolith: PACK_P to the pack connector, the Port 1 input sense path,
   and 30 of 56 blocked connections at the PD and charger chips.
2. Fix the floorplan as data in `tools/make_rooms.py`: room boxes, part list per room, reserved lanes, and for each
   power net the hand-off point between rooms. Decide per power path where its two ends face each other. Decisions
   that paid off: each 5 V buck beside the chip it feeds; shunt feeding the input capacitor column from above; pack
   FET turned so its output pads face the pack connector; mirrored ports share one design (Port 2 = Port 1 - 23.1 mm).
3. Write one brief per room (`rooms/<room>.brief.md`): the parts, what enters and leaves and where, the hot loops
   with their first capacitor, the known faults of the reference in that room, the numbers to report.
4. Give every worker `WORKER-GUIDE.md` + its brief. Rooms in parallel; at most two whole-board scores at a time.

### Worker, per room
1. `python3 tools/pinmap.py <chip>` for every chip: which pad is on which side.
2. Write `rooms/<room>.py` with `Room`: `put` the big parts, `beside` for every passive (its pad faces the pin it
   serves), `row` for groups. Run it, read the picture, fix. `done()` lists overlaps, out-of-room parts, lane
   violations and decoupling distances.
3. Order of work inside a room: switch + first capacitor of each hot loop, bulk capacitors behind it, power path
   parts in a straight line, then the chip's support parts with 0.4 to 0.5 mm escape room, last the rest.
4. Score at most 4 times (`bash tools/qs.sh <name> --no-hot`), read `tools/blocked.py` and `tools/cu.sh` crops.

### Lead, feedback rounds
- Assemble (`tools/assemble.py`, done inside `qs.sh`) and score with hot loops. Check in this order: `power_open`
  (must be empty except 3V3 at L201 and GND at J301/J302), DRC 0, hot loops 7 of 7, then blocked list, then loss.
- Round 2 is **surgical**: give a fixer the exact blocked connections with the cause you see, forbid re-placement of
  power parts, cap it at 3 scores. Two fixers (one per port) took the board from 37 to 28 blocked and removed a
  ground open without touching loops or loss.
- What cannot be fixed by moving small parts goes to the routing phase (gate pad inside a pour, pins under VBUS copper).

### Traps (placement)
- "no room for a via" in `plan.log` is not an open; only `score.json` `power_open` counts.
- A capacitor's ground pad over a bottom-side capacitor pad of another net cannot get a return via: the loop does
  not close and the ground pin reads open (U404 in round 1).
- A shunt lying across the south pins of a QFN walls three signal pins: stand it upright.
- Never pipe the room script into `head`: it is killed before it saves.
- Kelvin taps and thermistor lines are blocked on every board by design of the router; they are hand routes.

## Routing

### Order (each step builds on the board of the step before)
1. **Lead: power straps** (`routes/lead_packp.py`). Any power path the copper plan carries on an inner pour that
   signals may cross (PACK_P on In2) gets a wide **track** on In2 and B first. A pour of a soft net is not an
   obstacle for the router; a track is.
2. **Lead: Kelvin pairs and escapes** (`routes/lead_kelvin.py`): tap at the inner edge of each shunt pad, via,
   In3 pair to the sense resistors; a via in each high-side gate pad that sits inside a pour.
3. `python3 tools/hr.py <placement run> <out> routes/lead_packp.json routes/lead_kelvin.json` builds the board:
   generated copper + lead routes, zones one per outline, real DRC. Must print 0 errors.
4. **Router tier 1**: `tools/stage_route.sh <dir> g1 g0.kicad_pcb '<regex of gate, bootstrap, sense, driver nets>'`.
5. **Router tier 2**: `tools/stage_route.sh <dir> g2 g1.kicad_pcb - --nopre` (everything else). Later tiers cannot
   pull earlier copper.
6. **Workers by region** (`ROUTING-GUIDE.md`): each takes the open connections and DRC errors of its region from
   `<board>.drc.json`, writes `routes/<name>.py` with `HR` (`free_vias`, `auto`, `link`, `seg`, `drop`), applies with
   `tools/hr2.py`, which runs the real DRC.
7. **Lead merges**: `python3 tools/hr2.py <dir> g2 final routes/<w1>.json routes/<w2>.json ...`; must be 0 errors.
8. Score with own copper: `bash tools/score/score_board.sh <out> <dir>/final.kicad_pcb --keep-copper --route=20`.
   Compare loss and hot loops with the pre-route score: routing must not cost a power path.

### Traps (routing)
- **Zones with several outlines lose all but the first when KiCad saves the board again.** The router refills at
  the end, so F/B power pours silently vanish (VBUS F 51 to 2.4 mm2, PACK_P F 104 to 1.2 mm2). The scorecard scores
  power before the route and does not see it. `hr.py` splits every zone into one zone per outline. Check pour areas
  before and after a route.
- Signal tracks on In2 cut the PACK_P In2 pour into islands: after routing PACK_P was open at the pack connector.
  Hence step 1. Always score the routed board with `--keep-copper`.
- Lay power straps before Kelvin pairs, and load the earlier file as obstacles (`h.load`), or they collide.
- A via in a thermistor pad next to the inductor fails DRC against the SW pour on B and PACK_P on In2.
- The checker (0.2 mm, 0.3 to pours) is stricter than DRC; `auto(clr=0.15)` finds more. HighCurrent nets need 0.25.
- `auto` cannot start inside a 0.4 mm pin row: draw a 0.15 mm stub out of the pin first.
- Two workers must not share scratch names: `hr2.py` names its scratch files after the output board.
- Workers' routes are tied to the routed board they were made on. If the lead changes anything before the router
  tiers, the worker tier has to be redone, so settle power straps and key routes first.
- Background jobs in the container stop after 30 min unless started with a longer limit; the docker container keeps
  running, so wait on `docker ps` rather than restarting.

## Closing the last connections by hand (lead, 2026-11-15)

- Rip-up over whole nets or whole regions stops working when 10 to 15 connections are left: every re-lay breaks a pin
  escape somewhere else. Go local instead: pull a neighbour only inside a 1 mm circle round the crossing point the
  path search reports (`hand_lib.cross2`), and undo the lot if any pulled line does not come back.
- Look before routing. `tools/crop.py <dir> <board> x0 y0 x1 y1 out.png [nets]` draws the four signal layers with
  net names; `routes/lane_map.py` prints free lanes as text. Three "impossible" nets were one hand stub away once
  the picture was read (a pin escape 0.03 mm too close to its neighbour, a via that needed a strap 1 mm narrower).
- Long nets: lay forced pieces. Put hand seeds (short stubs, vias) where the net must go, then let the path search
  join seed to seed with a 2 to 4 mm margin. A free search takes the cheapest path, and on this board the cheapest
  path for a signal is a long In2 column through the pack pour.
- A signal on the pour layer is a cut in the pour. Before laying an In2 column, find which neck or via feeds each
  load behind it, and hop to another layer across that neck. Then score with the board's own copper
  (`score_board.sh ... --keep-copper --route=0`): a walled pour reports nothing open, only a loss several times higher.
- The model treats power pours as hard copper. KiCad refills a pour round a new via, so a via that nicks a pour edge
  is legal after the refill; let hand stubs do that, but never across a pour's only neck.
- Join pour pieces between hard copper (a via and a pad). A pour-to-pour link is cut again by the next refill.
- A DRC "unconnected" item between two zones prints the zones' corners. List the filled islands of the zone that hold
  no via of the net to find the real one.
- Moving a line 0.1 to 0.2 mm by hand (exact numbers from the rules: via 0.225 radius + 0.15 + half the track) often
  frees a lane the 0.05 mm grid search cannot see.
