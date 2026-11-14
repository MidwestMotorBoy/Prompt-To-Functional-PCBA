# Round 3 team report: making the skeleton-first placement routable

## Result

The winner is **w1_c** (worker 1). It keeps the q7s2 power skeleton unchanged and replaces only the step that places the remaining signal parts.

| Measure | w1_c | q7s2 (before) | Hand board m3 |
|---|---|---|---|
| Signal connections routed | 346 of 442 | 299 of 442 | 391 of 448 |
| Connections failed | 96 | 143 | 57 |
| Router run time | about 37 min, finished | 2 h 20 min, finished | 18 min, finished |
| Signal wiring estimate (half-perimeter, mm) | 2591 | 4100 | 2064 |
| Power paths | all joined | all joined | all joined |
| DRC errors | 0 | 0 | not re-checked this round |
| Hot loops | 7 of 7 pass, 5.49 nH | 7 of 7 pass, 5.48 nH | not re-checked this round |
| Copper loss (W) | 1.255 | 1.20 | 1.10 |

"All joined" leaves the same three items to the router as before: 3V3 at L201 (under 1 A) and the GND test pads J301 and J302.

w1_c closes about half of the routing gap between q7s2 and the hand board (47 of 92 connections). It is not yet as routable as the hand board, and it loses 0.05 W more than q7s2.

Renders: `winner_top.png` and `winner_bottom.png` in this folder. I looked at both. The power parts and pours are in the same compact groups round their chips as on q7s2; nothing sprawls.

## What I checked

For each worker's best board I confirmed the board files exist, re-read the route log and the copper trial log, counted DRC errors in the DRC report, and counted hot-loop passes in the hot-loop report. All reported numbers matched the logs. I looked at the top and bottom renders of the top two boards (w1_c and w3_U6_s11) and compared them with q7s2.

Only w1_c's router run finished. The other three stopped at the 45-minute cap, so their routed counts are the last progress line, not a final result. Worker 1's and worker 4's reports both said "full route done"; for worker 4 that is not correct (the log ends mid-run at step 1240).

## All four workers

All four boards meet the hard limits: power joined, 0 DRC errors, 7 of 7 hot loops.

| Rank | Worker and board | Approach | Routed / failed / total | Run finished? | Loss (W) | Hot loops (nH) | Wiring estimate (mm) |
|---|---|---|---|---|---|---|---|
| 1 | W1, w1_c | New placer for the signal parts: every part is put down at a legal spot next to the pins it serves | 346 / 96 / 442 | Yes, 37 min | 1.255 | 5.49 | 2591 |
| 2 | W3, w3_U6_s11 | Existing placer with a changed cost and move set | 341 / 102 / 446 | No, cut at 45 min | 1.203 | 5.45 | 3466 |
| 3 | W2, w2_a10pd | Smaller keep-outs round the frozen power copper | 323 / 120 / 450 | No, cut at 45 min | 1.466 | 5.48 | 3737 |
| 4 | W4, w4_l | Moved 39 small parts on q7s2 by hand-style repair | 304 / 133 / 441 | No, cut at 45 min | 1.200 | 5.46 | not measured the same way |
| - | q7s2 (start) | | 299 / 143 / 442 | Yes, 2 h 20 min | 1.20 | 5.48 | 4100 |
| - | Hand board m3 | | 391 / 57 / 448 | Yes, 18 min | 1.10 | | 2064 |

W1 and W3 are close on routed count (346 against 341), and W3 has the lower loss (1.20 W against 1.255 W). W1 ranks first because its count is a finished result and its router run settled in 37 minutes, while W3's run was still ripping up and retrying when it was cut (its count moved between 330 and 347 in the last steps). For reference, q7s2's own run showed 303 routed at the same step where W3 was cut.

## What worked

- **Placing each part legally from the start, next to the pins it serves (W1).** This was the largest single gain. The first version cut the wiring estimate from 4100 to 2992 mm in a 2-second run. Placing each chip's own resistors and capacitors straight after the chip, then a few passes of lifting and re-placing each part, brought it to about 2550 mm. The parts round the two charger chips now match the hand board (U403: 29 parts within 2.5 mm against 26 on the hand board; U503: 24 against 23).
- **A 1 mm keep-free zone round the frozen PP5V and VBUS pads at the PD chips (W1).** Without it, one run put signal parts against U401's PP5V pin and that power path opened.
- **In the existing placer (W3):** moving groups of parts as rigid blocks during the fill, settling the large chips first, and a long final fine-tuning pass. Together these took the wiring estimate from 4100 to about 3470 mm.
- **Freezing less power copper is safe if the PD-chip paths stay frozen (W2).** Keeping out only the nets of 10 A and above plus VBUS, PPHV and PP5V (247 mm2 instead of 885 mm2) left every power path joined.

## What did not work

- **Running the existing placer's refine step after W1's placer** made it worse (2518 mm rose to 3556 mm). It lets parts overlap early and then shoves every chip aside to fix it.
- **Smaller keep-outs (W2) cost loss.** Signal parts then sit against the 10 A pours and the final copper is thinner: 1.47 W against 1.20 W. The real wiring gain, averaged over seeds, is about 7 %, not the 20 % one run suggested.
- **Reserving empty rooms round the controller chips (W2)** left power paths open or made the skeleton worse. Dropped.
- **Local repair of q7s2 (W4)** improved the 2-minute screen (34 failing down to 23) but not the full route (304 against 299). The free spots near the PD chips are already taken, so parts could only move to places still 5 to 20 mm from their pins.
- **The 2-minute screen is a weak predictor.** W4 and W2 both improved it a lot without a matching gain in the full route.
- **Run-to-run spread is large.** The same settings with a different random seed change the wiring estimate by several hundred mm in every method. One run proves little; pick the best of several.
- **U404 (Port 1 5 V buck) still lands about 18 mm outside its box** in every skeleton run. The cause is in the skeleton placer; nobody fixed it.

## What still limits the winner

- 93 of the 96 failed connections have no path even with every other signal route removed. They are blocked by pads and frozen power copper, not by other signals.
- They cluster at the PD chips and port chips: U503 (21), U501 (15), U401 (14), U505 (7), U405 (7). 67 are USB port nets.
- The top side is about 64 % full, while the bottom side has 1992 mm2 free for 271 mm2 of parts.
- The longest remaining nets go to frozen skeleton parts: gate resistors to FETs that sit behind power copper, the SWD lines from J301 to the MCU, and DRV9_OFF from Q409/Q509 to the PD chips.

## Tool changes to merge into the repo

1. **W1's placer as the fill step of the skeleton-first flow.**
   - `/home/claude/work/team/w1/greedy_fill.py` (the new placer)
   - `/home/claude/work/team/w1/pp_w1.py` (copy of place_pack.py that exports the exact part bodies and keep-outs the new placer uses, and adds an overlap report)
   - `/home/claude/work/team/w1/full.sh` (driver: q7s2 skeleton, new fill, apply, copper trial)
   - `/home/claude/work/team/w1/metrics.py`, `netdiff.py`, `intent_check.py` (measurement tools)
   - Settings for w1_c: BOXW=0, SEED=2, with the 1 mm keep-free zones at PP5V and VBUS.
2. **W3's placer changes, behind their switches, default off for now.** They are a real gain for place_pack.py but are superseded by W1's placer for this step.
   - `/home/claude/work/team/w3/place_pack.py`, `/home/claude/work/team/w3/fastcore.py`, settings in `/home/claude/work/team/w3/best.sh`
   - `/home/claude/work/team/w3/ghost.sh` and `ghost_router.py` (counts connections that have no path even on an empty board; a better screen than the 2-minute run)
3. **W2's keep-out drawing fix only.** Counting a 0.5 mm grid cell as blocked only when its centre is inside the pour cut the keep-out from 885 to 688 mm2 with nothing else changed. It is the W2_RASTER option in `/home/claude/work/team/w2/skeleton.py`. It has not had a full copper trial on its own, so run one before making it the default. Do not merge the other W2 freeze options as defaults; they cost loss.
4. **Nothing from W4** into the flow. `/home/claude/work/team/w4/repair.py` can stay as a hand tool.

## Next step

Give the PD chips and port chips room to get their signals out, since that is where nearly all remaining failures are and they are blocked by copper and pads, not by other signals.

1. Run W1's placer on a skeleton frozen with W2's keep-out drawing fix, and check loss stays near 1.25 W.
2. Let W1's placer put small signal sections on the bottom side, where 86 % of the area is free.
3. Fix the skeleton placer so U404 lands inside its box.
4. Run 4 to 6 seeds of the result, screen with the empty-board path count from W3, and full-route the best two.

Target for the next round: at least 370 routed with loss at or below 1.25 W and the hard limits unchanged.
