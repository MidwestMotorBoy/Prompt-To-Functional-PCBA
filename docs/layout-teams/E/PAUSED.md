# Team E: paused 2026-11-15 about 16:15 UTC (Logan: "pause when convenient")

Single agent, no subagents. Goal: a fully routed board from the hand template. Not reached yet.

## Where it stands

| | Hand board (start) | Team E now (run p5, before routing) |
|---|---|---|
| Open power paths | Port 1 PP5V at U401 | PP5V of both ports (closed by the router's power pass, see below) |
| Loss, generated copper | 1.359 W (0.854 W with team A's recipe) | 0.936 W |
| Hot loops | 7 of 7, 6.75 nH | 7 of 7, 6.78 nH (run p3; not rerun on p5) |
| DRC errors | 0 | **2** (see "First thing to do") |

Last full trial route (run p4, own router, signals only): 0 DRC errors, 26 signal connections open
(the hand board with the same router: 20). The p4 number is worse than it should be because the power pass took the
only way out of the PD chips' CC pins; the copper added for p5 is meant to fix exactly that and has not been routed yet.

## What exists

- `tools/` (README in each file's docstring): `sc.sh` scorecard wrapper, `go.sh` (moves -> copper -> score -> dump),
  `ep.sh` + `eplace.py` (placement as a move list, courtyard check), `ecopper.py` (hand copper list on top of the
  planner), `edump.py`, `er.py` (router core), `eroute.py` (driver: power pass, rip-up, swap), `eapply.sh`,
  `eview.py` (pictures, `--fill=B`, `--routes=`), `edbg.py`, `recipe.sh` (copper recipe env).
- `place/moves.txt`: 14 parts moved on the hand board, each with its reason.
- `place/copper.txt`: hand copper (input path lanes under both inductors, bottom-layer bars to the bulk capacitors,
  VBUS pin 32 via and track, VBUS pad pairs of both connectors).
- `place/constraints_plan.json`: planner-only terminal overrides (PPHV and PP5V); scoring uses the shared file.

## Findings so far

1. Of 43 pins the old trial router could never reach on the hand board, 40 were walled in by generated power pours,
   not by parts. In `er.py` a pour gives way to a track (KiCad refills round it) at a price that grows with depth
   into the pour, and a route that would split a pour or cut a pad off it is refused. Hand board: 50 -> 20 open.
2. Scoring a routed board with its own copper: 0.85 W before, 2.5 W after, when the router is left to join power
   paths with 0.2 mm tracks (AC_SNS_N alone 0.64 W) and to cut the In2 PACK_P pour. Power first, signals after.
3. The planner never joined the input shunt or the left bulk capacitors to the input FET's drain on either port; the
   scorecard does not flag it because capacitors are not scored terminals. Now real copper, 0.03 W per port.
4. The planner treats a capacitor at the charger's VAC pin as a 5 A PPHV terminal and pours a corridor 28 mm long
   to it, which walls off the input path. Fixed with a terminal override.

## First thing to do on resume

1. Run p5 has 2 DRC errors: the hand B.Cu track for Port 2's VBUS pin 32 (`place/copper.txt`, "track VBUS@2 B.Cu")
   runs over a GND via at (87.95, 77.475). Move the track's corner, then `bash tools/go.sh p6`.
2. `python3 tools/eroute.py /home/claude/runs/p6 cu r1 --power --skip='^(GND|PACK_P|3V3)$'` and look at the PD chip
   areas with `eview.py --drc=`.
3. Still to do after that: charger chip crowding (gate drive, bootstrap, REGN at U403), I2C bus lanes, the ground /
   pack / 3V3 pass after signals with a refill loop until KiCad shows 0 unconnected, score the routed board with its
   own copper, renders, REPORT.md, SKILL-NOTES.md.

Run folders are in the cloud container (`/home/claude/runs`) and do not survive it; everything needed to rebuild
them is in this folder (`bash tools/go.sh <name>` takes 2 minutes).
