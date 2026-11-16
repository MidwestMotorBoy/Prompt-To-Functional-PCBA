# Team F method notes (adds to team D's SKILL-NOTES.md; written so a cheaper model can follow them)

## Placement
- One round was enough once the brief carried the previous team's faults as rules: a free via spot at every pin that
  leaves the room, an own via spot for every 3V3 / GND pad, shunts upright beside QFN pins, known non-fits listed.
- Ask each worker to report a checked via spot per leaving net. The lead can pre-lay them.
- Do not run a second placement round for connections that are blocked by the copper plan (Kelvin taps, pads inside
  pours, thermistor pads). They are lead copper.

## Routing order that worked
1. `hr.py` placement + `routes/lead0.json` (power straps, Kelvin taps, ground necks) + pour cuts. Signal vias must be
   added with `hr2.py` (KiCad refill), not `hr.py`: the planner's fill ignores the 0.25 mm HighCurrent rule round them.
2. `ml.py close()` on the nets the router always walls in (CC, SBU, PPHV sense) BEFORE the router.
3. One router run, whole board, fan-out stubs on, full rip-up. Do not tier with `--nopre`. Do not use `--cont` on a
   hand-finished board: it lifted 220 good routes and left 12 open.
4. Workers by region with `CLOSE-GUIDE.md`. Give each its own copy of the board, a list with coordinates and the
   router's reason, and a 12 DRC-run cap (they used 2 each).
5. Lead merges with `hr2.py`. Expect collisions only where a worker's net left its region; keep one side and re-lay
   the other with `rip.py`.

## Tools
- `tools/ml.py` (ML): multi-layer path search with the real rules. `route` with `start_geoms` / `goal_geoms` joins
  copper sets; `plane` drops a via to a plane; `force` lays exact tracks the 0.05 mm grid cannot find.
- `tools/crop.py`: four layers side by side with net names. Look before routing.
- `tools/rip.py` (RML): `comps(net)` lists the pieces of a net; `join(net)` joins them with free paths; `rip(net, A, B)`
  searches with other signal tracks removed, pulls only the tracks the new path hits, re-lays them (nested once or
  twice), and undoes everything if one does not come back; `pull`, `lay`, `anchor`.

## Traps found
- A set-to-set route can end at the rim of a via: KiCad then reports it open. End every track ON a centre point
  (`anchor`).
- `hr2.py` drops by segment end points and drops vias in the box; a model that drops by outline disagrees. Use
  `"tracks_only"` boxes for single segments.
- Two zones of one net that overlap after the refill are still not connected. Join via to via or pad to via.
- "Zone to zone" open items name zone corners. List the pour pieces and the vias inside each to find the real gap.
- A row of ground vias 0.8 mm apart is a wall on every layer. Leave a 1.2 mm gap in stitching rows for inner tracks.
- A track that walls a connector pin in can often be replaced by a link from the other side of its own net (J301
  pin 1: C314 fed from C313 under the capacitor instead of down the column).
- Pruning dead-end stubs by geometry is not safe when tracks end in pours or pads of other layers; check piece counts.
- Score the routed board with `--keep-copper --route=0`. Here: no opens, but 0.24 W more loss than the placement score.
