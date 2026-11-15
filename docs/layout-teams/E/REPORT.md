# Team E report: one agent, the hand board, a full route

Set by Logan: the same kind of experiment as team D, run by a single agent on high effort with no subagents, from
the same starting point (the Monolith hand template, `tools/score/template/board.kicad_pcb`), aiming for a fully
routed board. No cost cap. All numbers are from the shared scorecard run through `tools/sc.sh` in the cloud
container; a routed board is always scored with its own copper (`--keep-copper`), not with the plan's.

## Result

`routed/final.kicad_pcb` is fully routed. KiCad 10 reports 0 unconnected items and 0 DRC errors on it.

| | Hand board (start) | Final placement, before routing | **Final board, routed** |
|---|---|---|---|
| Connections open (KiCad) | 380 | 375 | **0** |
| DRC errors | 0 | 0 | **0** |
| Open power paths | AC_SNS_N at both input shunts, Port 1 PP5V | PP5V of both ports | none except 3V3 at L201 (allowed; see below) |
| Hot loops | 7 of 7, 6.75 nH | 7 of 7, 6.78 nH (run p3, three moves earlier) | **7 of 7, 6.77 nH** |
| Loss | 0.854 W (plan copper) | 0.923 W (plan copper) | **1.144 W (own copper)** |

The hand board column uses team A's copper recipe (run `handP`). The plain router closed 394 of 452 connections on
the hand board (team D's report); team E's router closed all but 20 signal connections on it before any part moved.

What the final board is made of:
- The hand placement with 27 parts moved (`place/moves.txt`, 15 lines, each with its reason).
- The planner's power copper plus a hand list (`place/copper.txt`: 12 pours, 6 bars, 14 tracks, 34 vias) and
  8 Kelvin taps (`place/routes.txt`).
- 399 routes laid by `tools/eroute.py`: 2044 mm of track (top 532, In2 418, In3 556, bottom 539) and 218 vias, in
  three passes that took 9 minutes of machine time. The copper plan and its checks take 2 more.

Where the 1.144 W goes: ground 0.31, PACK_P 0.23, CELL_P 0.16, the four switch nodes 0.19, both PP5V 0.06, the
rest 0.19. Routing costs 0.22 W against the plan (0.923 W): ground +0.07 and PACK_P +0.06 from signal tracks
cutting the planes, PP5V +0.06 because those two paths are closed by routed 0.4 to 0.8 mm tracks.

Pictures: `routed/top.png`, `bottom.png`, `In2.png`, `In3.png`, `In4.png` (copper as KiCad draws it, bottom
mirrored) and `routed/F.png`, `B.png` (the scorecard's coloured views).

### What to know before trusting it

- **The last two connections were closed by hand, not by the router.** The Port 1 connector CC knot (three tracks
  and a moved VBUS track) and two CC vias at Port 2 are hand copper with exact coordinates. Everything else in the
  signal layers is the router's.
- **3V3 at L201 shows as open in the scorecard and is connected in KiCad.** With the pack sheet protected, more
  signal tracks run on In3 and cut the 3V3 sheet; the router rejoins the pieces with 15 short tracks, some 0.15 mm
  wide, and the loss solver's raster does not follow the thinnest one. It is the one opening the hard limit
  allows. The same board routed without the pack-sheet price (run p14) has no flagged path and loses 1.272 W.
- **The gauge shunt (RS101) sense lines are connected but not laid as Kelvin taps.** The eight charger shunt taps
  are true taps from the inner pad edge with pour voids at their vias; the gauge pair is ordinary routing.
- **Warnings left:** 67 "connection width" warnings (pour necks under the minimum width where tracks cut a pour)
  and 1 copper sliver. No dangling tracks or vias, no overlapping drills.
- Not done: tidying the router's bends for looks, a thermal run on the routed copper, any check against the
  schematic beyond the netlist the template carries.

### Rebuilding it

In a container with docker and the `kicad/kicad:10.0` image, from `docs/layout-teams/E`:
`bash tools/go.sh run1` (needs the hand board dump once: `BASE=<dump>`, see `tools/go.sh`), then
`bash tools/full.sh run1 4`, then
`source tools/recipe.sh; bash tools/sc.sh run1s /home/claude/runs/run1/rt.kicad_pcb --keep-copper --no-ghost --hot`.
The final board is run p17: the three text files in `place/` as committed, router defaults as in `full.sh`.

## What was tried

### Tools built (all in `tools/`, each with a docstring)

- `er.py`, `eroute.py`: a grid router (0.05 mm) written for this board. Pours of other nets give way to a track at a
  price that grows with depth, and a route that would split a pour or cut a pad off it is refused. Passes: Kelvin
  taps, power joins with wide tracks, signals with rip-up, swap and a local re-order step for knots, then every net
  again with the pours as KiCad really filled them.
- `go.sh` (moves, planner, hand copper, DRC, loss, dump) and `full.sh` (the passes, then stub trimming). `eplace.py`
  (placement as a move list with a courtyard check), `ecopper.py` (hand copper as a text list), `eapply.py` (routes
  onto the board, tap voids, refill), `etidy.py` (trims stubs), `eview.py` (pictures of any window with DRC marks),
  `sc.sh` (scorecard wrapper, hot loops side by side).

### What moved the count of open connections

| Step | Open after (KiCad, 0 DRC errors each) |
|---|---|
| Hand board, router with pours as walls | 50 signal |
| Pours give way to tracks | 20 signal |
| Power joined first with wide tracks, taps laid first (run p7) | 24 signal, 52 with pour pieces |
| Pin-access price, room under the PD chips, real fills between passes (p8) | 9 |
| REGN capacitor onto its own pins, VBUS pin track under the capacitor pads (p9) | 5 |
| Knot re-order step, pull-up rows moved 1.9 mm, wider via price (p12) | 2 |
| Hand copper for the Port 1 CC knot and the Port 2 CC2 via window (p14) | **0** |
| Overlapping vias removed, stubs trimmed, price on the pack sheet (p17, final) | **0** |

### What did not work or was dropped

- Leaving power paths to the signal router: 0.85 W became 2.5 W.
- A price of 2 per cell on the pack sheet: loss 1.13 W but SDA stays open in every pass. 1 per cell is the setting.
- Moving capacitor C552 to make room at the Port 2 protector: not needed, the missing via site was at the other
  end of the net.
- The knot step closed the Port 2 connector knot in a test and nothing in the final runs; the hand copper made
  it unnecessary there. It stays in the router, capped at 60 s per knot.
- A first version of the stub trimmer judged 350 good track ends dangling (the router ends tracks on a pad's edge)
  and a second one ran forever on rounding; the fixed one changes 16 tracks on the final board.

## Findings for the shared tools

1. Routed boards lose more than their plans say, mostly in planes the router is free to cut. Score after routing.
2. The planner does not join the input shunt or the left bulk capacitors to the input FET drain, and the scorecard
   does not flag it because capacitors are not scored terminals. Hand copper closes it here.
3. The planner pours to every pad of a net unless told which pads carry current (`place/constraints_plan.json`).
4. A pour that only touches a pad along its edge counts as joined in a raster model and as open in KiCad.
5. A hand via beside a planner via raises no DRC error and still overlaps its drill; read the warnings.

`SKILL-NOTES.md` has these and the routing lessons as 19 notes with the tool or evidence for each.

## Cost

One agent, no subagents. From the session transcript up to this report: 0.50 M output tokens, 1.52 M cache-write
tokens and 88 M cache-read tokens over 367 model turns, which is about $62 at list prices ($40 per million output,
$16 per million one-hour cache writes, $0.20 per million cache reads). The transcript may undercount. Wall time was
about four hours of work on either side of the pause.

## What I would do next

1. Give the 3V3 sheet two or three hard necks before signals, the way the pack path now has a protected sheet, so
   no 3V3 join is thinner than 0.3 mm.
2. Lay the gauge shunt's sense pair as taps (needs a tap rule for ground: only solid own copper blocks the via).
3. Make the pack-sheet price follow the current direction instead of a flat price, and try it on ground under the
   switch nodes, where routing added 0.07 W.
4. Run the same recipe on team D's round 2 placement, which starts with fewer blocked connections and less loss.
5. A cleanup pass for bends and widths before anyone looks at fabrication.
