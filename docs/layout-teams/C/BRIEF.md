# Team C: the constructive placer, whole board, both sides

Read ../CHARTER.md first.

Starting point: `tools/floorplan/team_round3/w1/greedy_fill.py` (round 3 winner, see `tools/floorplan/team_round3/REPORT.md`). It places each part at a legal spot next to the pins it serves, with no overlaps ever. Large chips go first, each followed by its own support parts, and then rip-up and re-place passes run. In round 3 it only filled around a frozen power skeleton. That frozen copper caused 93 of the remaining 96 failures.

The job:
1. Extend it to place the whole board: the power parts too, with hot-loop capacitors pad to pad as hard constraints.
2. Let it use the bottom side.
3. Make power copper and loop area part of its cost, not something frozen beforehand. For example, reserve a corridor estimate per power path instead of real copper.
4. Run many seeds, screen them with the blocked-edge count, and run the full scorecard on the best.

Workers could split by: power-stage handling inside the placer, two-sided placement, the copper-corridor estimate, and the seed sweep with screening.
