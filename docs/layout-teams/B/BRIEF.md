# Team B: place power and signal parts together, chip by chip, inside Logan's boxes

Read ../CHARTER.md first.

Starting point: Logan's reviewed floorplan `tools/floorplan/example/monolith/floorplan_r2d.json`. With every part at its box centre, signal wiring is 2238 mm; the hand board has 2064. So the boxes are sound.

Method: place one section at a time, the way a layout engineer does.
1. Place the main chip first.
2. Then its hot-loop capacitors, pad to pad.
3. Then its switches, inductor and sense parts.
4. Then its own resistors and capacitors, at the pins they serve.
5. Plan that section's power copper, then move on to the next section.

Nothing is frozen board-wide before signal parts are down. Each section keeps escape room at the pins of its fine-pitch chips: the round 3 failures were pins boxed in by copper and pads. Use the blocked-edge count after each section, or after each few sections, to catch a boxed-in chip early.

Useful tools in the repo:
- `tools/floorplan/place_pack.py` and `fastcore.py`;
- `tools/floorplan/team_round3/w1/greedy_fill.py`, a constructive legal placer;
- `stage_copper.py` and `hot_score.py` for the hot loops.

The bottom side is mostly empty on every board so far. Small signal sections may go there.

Workers could split by section groups (Port 1, Port 2, cells and gauge, MCU and 3V3), with the lead stitching them together and resolving the borders.
