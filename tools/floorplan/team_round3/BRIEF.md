# Team brief: make the skeleton-first Monolith placement routable

## The board and the goal
Monolith is a 2-port USB-PD battery bank (KiCad 10). Repo: /home/claude/prompt-to-functional-pcba (read tools/floorplan/README.md and tools/copper/README.md first).
Logan (the owner, reviewer only) set these priorities: 1) hard thresholds where a violation means a part will not work (power paths joined, hot loops under limits, DRC clean); 2) then less ringing; 3) then lower losses and better thermal spreading. Loop area and power paths matter more than wire length, but the board must also be routable.

## Where we are
- Logan reviewed a block floorplan (one box per section and side) and picked option r2-d with 4 boxes moved. Its box file: /home/claude/work/bfp7/floorplan_2.json (render floorplan_2.png next to it).
- Skeleton-first method (tools/floorplan/skeleton.py, driver /home/claude/work/hp/skel.sh): place the 38 power parts plus every hot-loop capacitor alone in their boxes, plan their copper, freeze that copper as no-footprint keep-outs, then fill the remaining parts with place_pack.py (REG_MARGIN=FILL_MARGIN), then plan all power copper (trial.sh -> run.sh, plan_copper.py, write_copper.py, DRC, dc_score.py, thermal.py).
  Usage: `cd /home/claude/work/hp; FILL_MARGIN=3 ROOM=0.15 ./skel.sh <tag> /home/claude/work/bfp7/floorplan_2.json <seed>` (about 10-15 min). Result line `RESULT <tag>: ...` lists open power nets, total loss and DRC error count; files land in /home/claude/work/hp/<tag>_*.
- Best so far: tag q7s2 (seed 2). Power: every power path joined (3V3 under 1 A and the J301/J302 test GND are left to the router, as on the hand board), 0 DRC errors, 1.20 W loss (hand 1.10 W), 7 of 7 hot loops pass, tier-2 sum 5.48 nH. Renders: /home/claude/work/hp/q7s2_F.png, q7s2_B.png.
- The problem: trial routing. q7s2 routed 299 of 442 signal edges (143 failed) and the router thrashed for 2 h 20 min. The hand placement with the same generated copper (tag m3, /home/claude/work/hp/m3_cu.kicad_pcb) routed 391 of 448 (57 failed) in 18 min. Failures on q7s2: 84 in USB port nets, 9 cell taps, 10 GND, 5 PACK_P, 5 P1_LDO_3V3. Signal half-perimeter (place_pack's printed signal_half_perimeter_mm): q7s2 about 4100 mm, hand board 2064 mm. Full logs: /home/claude/work/rt/route_in.log (q7s2) and route_ref.log (hand); look at the FAILED and FAILKEY lines.
- 8 other skeleton seeds left 1-2 power opens at the PD chips (U401/U501).

## Tools you will use
- Trial route: `/home/claude/work/team/route_trial.sh <tag> [minutes]` routes /home/claude/work/hp/<tag>_cu.kicad_pcb (needs <tag>_cu.kicad_pro/.kicad_dru beside it; trial.sh makes them). Prints `ROUTE <tag>: routed N edges, M failed ...`. Log in /home/claude/work/team/r_<tag>/route.log.
  FAST SCREEN: a 2-minute run reaches step 120. Failing count at step 120: hand m3 = 12, q7s2 = 34. Use `route_trial.sh <tag> 2` to screen candidates, and a full run (45 min cap) only on your best one or two.
- Hot loops (5-10 min per board, run from /home/claude/work): `cd /home/claude/work && bash hp/hot_each.sh <tag>` prints the tier-1 gate and tier-2 sum. Must stay 7 of 7 pass.
- Renders: `cd /home/claude/work/hp; for L in F.Cu B.Cu; do python3 /home/claude/prompt-to-functional-pcba/tools/copper/render.py <tag>_cu.kicad_pcb <tag>_cu.json <tag>_${L%%.*}.png $L; done`. Look at your renders with the Read tool; Logan rejected a board before because power parts sprawled.
- place_pack.py env knobs: BLOCK_FLOORPLAN, REG_MARGIN, PLACE_START (start from a placement), IC_POWER_ROOM, POWER_ROOM, CONSTRAINTS. fastcore.py holds the cost (signal half-perimeter, crossings, intent, region).
- Placement JSON: {ref: [x, y, angle, side?...]}; apply_placement.py in /home/claude/work/hp writes it into m3_bare.kicad_pcb (see skel.sh for the exact docker commands).

## Machine limits and shared-space rules
- 4 CPU cores and 15 GB RAM shared by 4 workers. Run at most one router and one placer at a time each. No parallel seed sweeps wider than 2.
- Docker must be running (`docker images`). If it is not: `rm -f /var/run/docker.pid /var/run/docker.sock; (dockerd > /tmp/dockerd.log 2>&1 &)`, wait 15 s.
- Do NOT edit files under /home/claude/prompt-to-functional-pcba or the existing scripts in /home/claude/work/hp in place: other workers use them. Copy what you change into your own folder /home/claude/work/team/w<k>/ and run the copies. Prefix every tag you create with w<k>_ so files never collide.
- Do not commit or push git. Never order PCBs or call any JLCPCB API.
- Wall-clock budget: aim to finish within about 3 hours.
