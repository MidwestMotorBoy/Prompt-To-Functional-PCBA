# Team A: extend the earlier ground-up scripted flow

Read ../CHARTER.md first.

Starting point: `tools/battery-bank/groundup/`, the script-built whole-board re-layout of Monolith. It placed every part except the fixed ones, drew every piece of copper, routed, and cleaned up. Its own trial route on the bare board (380 signal connections, power nets skipped) routed 373, the best placer result on record. Its README lists what is known to be weak: the power-stage handling, hardcoded coordinates and the copper method.

The job:
1. Rebuild its placement as a one-command script that starts from the bare template.
2. Score it with the scorecard, using generated power copper rather than its own.
3. Fix whatever blocks the hard limits: power opens, hot loops, DRC.
4. Remove the hardcoded Monolith coordinates where they can be derived from constraints.json, the netlist or the floorplan.

Optional: also score the board's own hand-tuned copper with `--keep-copper`, as a comparison.

Workers could split by: power-stage templates, support-part placement, copper, and generality (removing hardcoding).
