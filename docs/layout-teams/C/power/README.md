# Package power: power stages inside the placer (cplace/cpower.py)

Every power stage (both ports' four-switch stages, the two 5 V bucks, the 3.3 V buck) is built by rule from
`constraints.json` (`hot_loops`, `pin_pads`, `draw`) in the `pre_place` hook, before any signal part, and locked
(`ctx.LOCK`). No board coordinates are typed anywhere. The method is in the docstring of `cplace/cpower.py`.

## How to run

```
cd docs/layout-teams/C/power
./check.sh v3_s3 3          # place (HOOKS=cpower, SEED=3), legality vs base, HOOKS-empty cmp, quick plot (about 45 s)
../cplace/cscore.sh /home/claude/work/C/power/v3_s3 /home/claude/work/C/power/v3_s3.json --route=0   # screen + hot loops, about 15 min
```

`plot_stage.py <dump> <placement> <out.png> [x0,y0,x1,y1]` draws courtyards and pads coloured by net (quick look
only; the scorecard's F.png/B.png are what count).

## Measured (scorecard `cscore.sh --route=0`, hot loops on, no full route)

| Run (outdir under /home/claude/work/C/power/) | Code | Seed | Blocked edges | Loss W | power_open beyond allowed | DRC err | Hot loops |
|---|---|---|---|---|---|---|---|
| hand (lead, `/home/claude/work/C/hand_screen`, --no-hot) | | | 56 of 452 | 1.359 | P1 PP5V at U401 | 0 | hand_hot.json: 7 of 7, 8.15 nH |
| base cplace, no hooks (lead) | | 2 | 98 of 465 | 2.001 | P1 PP5V+VBUS U401, P2 PP5V U501, GND U504 | 0 | not run |
| v1_s2 | v1 (no separation rule) | 2 | 42 of 449 | 1.341 | CELL_P F102, P1 PP5V+PPHV U401, P2 PPHV U501 | 2 (GND x VBUS track crossings at the PD chips) | **6 of 7**, 5.95 nH (P1 HL_OUT: C438 not closed) |
| v2_s2 | v2 (separation + bulk caps in the pose choice) | 2 | 62 of 440 | 2.505 | P1 PP5V+PPHV U401, P2 PPHV U501 | 0 | 7 of 7, 5.42 nH |
| v2_s4 | v2 | 4 | 67 of 437 | 2.634 | P1 PP5V+PPHV U401, P2 PPHV U501 | 0 | 7 of 7, 5.42 nH |
| **v3_s3** (best) | v3 (+ section-box term) | 3 | 61 of 453 | 1.082 (CELL_P/CELL_P_RAW open, so low) | CELL_P F102, CELL_P_RAW J112, P1+P2 PP5V and PPHV at U401/U501 | 0 | 7 of 7, 5.48 nH |
| v3c_s3 | v3 + ccorr (HOOKS=cpower,ccorr, ccorr as of 16:14) | 3 | 69 of 441 | 1.297 | P1 PP5V+PPHV U401, P2 PPHV U501 | 0 | 7 of 7, 5.48 nH |
| v3_s2 | v3 | 2 | 65 of 454 | 2.903 | P1+P2 PP5V and PPHV at U401/U501 | 0 | 7 of 7, 5.49 nH |

Hot-loop totals (hot_gate.log "Loop total", board loop with all capacitors and ESL + 0.2 nH package), v3_s3 against
the hand board: HL_3V3 1.04 (1.95), P1 HL_5V 0.84 (1.08), P1 HL_IN 0.68 (1.02, limit 1.3), P1 HL_OUT 0.72 (1.03, limit
2.17), P2 HL_5V 0.83 (1.08), P2 HL_IN 0.68 (0.99, limit 1.3), P2 HL_OUT 0.69 (1.00). First capacitor alone: 0.34-0.41 nH
against 0.76-1.25 nH on the hand board. The stage is identical across seeds (5.42-5.49 nH on every run of v2/v3).

Gate-drive nets blocked (HG/LG between FET and gate resistor, ghost.log): hand 4, base 4, v1_s2 2, v2_s2 3, v3_s3 1
(P1 HG1), v3_s2 2 (P1 HG1, P2 LG2): not worse than the hand board.

## What did not work / traps

- **Shared bodies keep the hot-loop capacitor 0.5 mm off a power FET.** `pp_bodies.py` adds 0.5 mm escape room round
  every part with 12+ pads; the PowerPAIR FETs have 21 pads counting the paste windows. With it the first capacitor
  sat 1.29/1.60 mm (supply/return gap) from the pins; on the courtyard 0.79/1.15 mm (hand: 0.79/1.14). The module
  builds on the courtyard and gives the escape room back on free sides (restore_body).
- **The rule copper decides closure, not the distance.** plan_copper.py draws hulls over all supply pads and all
  return pads of a loop. One bulk capacitor turned across the loop cut the first capacitor's supply pour into three
  pieces: 6 of 7 (v1). Hard rule now: every capacitor's supply pad on the supply side of the switch mid line, return
  pad on the return side.
- **A switch pose must be judged with its bulk capacitors.** Q402 at the board edge had no room left for C431/C434
  under the separation rule (cost 1e5). The pose search now places every loop capacitor for each candidate.
- **Stage spill takes the charger's room.** Without the section-box term the bulk columns filled the charger box,
  U503 landed 15 mm away and 16 edges at U503 were blocked (v2). The box term brings both ports to the same shape.
- **Sense resistors are filed under the charger section** in the floorplan; with the box term R427 went to the
  charger box (10 A pad 10 mm from the stage). They are placed without the box term.
- **The base placer exits when a large part finds no spot.** With the stages placed first, Q101 (8.5 x 6.7 mm) had
  no legal spot on seeds 2, 4, 7. One tagged line in cplace.py (`# [power]`) now places it as a small part (evicts
  small unlocked parts) instead of `raise SystemExit`. It is still the cause of the large FET_MID/CELL_P_RAW loss on
  those seeds (2.5-2.9 W): the cell-path FETs land apart. That is the power-chain/corridor package's job.
- **PD-chip power opens are not the stages'.** PP5V and PPHV open at U401/U501 on every run ("no path on F.Cu" at the
  PD chip): the chip's power pins are walled in by its own support parts. The stage side of PPHV (R424/R524) joins.
- Gate escape term: two gate pins of a FET read about 9 mm of escape path on every pose, so it hardly ranks poses.
- Foreground waits: the scorecard with hot loops takes 13-15 min here; a `timeout 590` wait loop ends before it, so
  wait for the DONE line, not for hot_gate.log.
