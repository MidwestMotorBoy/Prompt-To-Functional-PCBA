# Worker "ports" (team A, round 2): notes

All scores come from `docs/layout-teams/A/tools/score_board_split.sh`, the split-zone scorecard. Quick screens come
from `tools/quick.sh`, a copy of the pdfix quick.sh with `split_spec.py` added between plan_copper and write_copper.
Every number here is **split**. Earlier numbers (pdfix a3 33/436, stagefix s3 37/430) are pre-split and cannot be
compared with these.

Base: `lead_merge/merged3_gu.json` (stage B4 + rebuild v5 port parts + stagefix s3 + pdfix a3).

## 1. Merged board m3 (`runs/m3`, `--route=0 --no-hot`)
- loss 1.053 W, DRC 0.
- power_open: 3V3@L201 and GND@J301/J302 only (the allowed opens).
- blocked 31 of 400: stage 5 / p1 13 / p2 11 / other 2.
- Queued at 22:55 UTC as `ports-m3` (`A/ports-m3-d71e5d03.json`). PC result: see section 4.

## 2. Variants (each one is a list of moves in `variants/mk.py`; build one with `python3 variants/mk.py <name>`)

| Variant | Moves (on top of base) | Blocked | stage / p1 / p2 / other | power_open | Loss | Verdict |
|---|---|---|---|---|---|---|
| m3 (base) | none | 31 of 400 | 5 / 13 / 11 / 2 | allowed only | 1.053 W | reference |
| **b1** (pdfix a4) | U502 84.4, C508 82.3, R541 86.6, R504 86.5 (lane west of R541 under port-2 pin 18 0.2 mm wider); R502 back to 82.2, R503 to 81.3 | **29 of 400** | 5 / 13 / **9** / 2 | allowed only | 1.053 W | **keep**: port 2 CHG_INT (R504->U501.18) and I2CC_SDA (R502->U503) freed |
| b2 | b1 + C507 1.5 mm north (83.5, 75.45), to move port 2's B.Cu PP5V detour away from U501 pins 26-31 | 29 of 401 | 5 / 13 / 9 / 2 | **PP5V@U501 OPEN** | 1.042 W | reject (hard limit). U501.36 GND freed, but pin 34 lost its PP5V copper |
| b3 | b1 + C507 0.5 mm north (83.5, 76.45) | 29 of 401 | 5 / 13 / 9 / 2 | **PP5V@U501 OPEN** | 1.043 W | reject. C507's PP5V pad must stay at y 77.725: the PP5V planner path to U501.34 is "left to router" and only the cap's pour reaches pin 34 |
| b4 | b1 + U505 0.2 mm south with C501/C502/C552 | not run | | | | placelib: U505/C541 overlap 0.36 x 0.19 (C541 cannot move: L502 / C506 are around it) |
| b5 | b1 + U505 0.4 mm west | not run | | | | placelib: peg H102 |
| b1 + planner experiment (`runs/b1_joinfix`, NOT the scorecard) | b1, with `tools/plan_copper_joinfix.py`: return_join uses `tight=False` (keeps the signal escape room) | 24 of 400 | 5 / **8** / 9 / 2 | allowed only | 1.053 W | evidence for a planner fix: all 5 port-1 SDA/SCL/IRQ edges route |

The best placement is **b1**: `best_gu.json`, `best_score.json`, and `best_overrides_gu.json` (the 6 refs that
differ from merged3).

b1 with hot loops on (`runs/b1_hot`, `score_board_split.sh --route=0`):
- loss 1.054 W, DRC 0.
- power_open: 3V3@L201 and GND@J301/J302 only.
- **7 of 7 hot loops pass tier 1, 6.16 nH**: HL_3V3 1.53, P1 HL_5V 0.66, P1 HL_IN 0.76, P1 HL_OUT 0.78, P2 HL_5V 0.89, P2 HL_IN 0.78, P2 HL_OUT 0.76.
- blocked 29 of 400.
- Queued at 23:30 UTC as `ports-b1` (`A/ports-b1-3d793d8a.json`).

## 3. Renders (`runs/b1_hot/F.png`, `B.png`)
- **F.Cu:** Each PD chip (U401, U501) sits 9-10 mm below its USB-C connector, with the protector (U405/U505) between
  them. The VBUS stem runs from the connector to pad 23. PPHV comes off pad 20 east to the sense resistor (R424/R524).
- The 5 V bucks sit by their chips: port 1 U404/L402 to the east, port 2 U504/L502 to the east of U501. PP5V caps
  C541-C543 are in line with L502.
- LDO caps, EEPROM (U402/U502) and pull-ups are within about 5 mm of their pins. Nothing is sprawled; the only part that
  moved is in port 2's south-row cluster, by 0.1-0.6 mm.
- **B.Cu:** Mostly free. Per port: one PP5V detour blob crossing the VBUS stem just north of the PD chip, a short PPHV
  stub, and a VBUS track from the connector. These are the same as in m3.

## 4. Full routes on Logan's PC (split copper)
Both routes ran on copper from score_board_split.sh outdirs (split). Both finished ("done"); neither hit a cap.

| Name | Board | Routed | Failed | Edges | Minutes | Status |
|---|---|---|---|---|---|---|
| ports-m3 (`A/ports-m3-d71e5d03.json`, queued 22:55 UTC, arrived about 00:15, 80 min after queueing) | merged3 | 361 | 39 | 400 | 83.1 | done |
| **ports-b1** (`A/ports-b1-3d793d8a.json`, queued 23:30 UTC, arrived about 01:12, past the 75 min mark) | b1 | **364** | **36** | 400 | 100.6 | done |

- b1 fails 3 fewer edges than m3. Port 2 CHG_INT, one Port 1 I2CC_SCL and CELL1 now route.
- Both are below the hand reference (391 of 448 routed, 57 failed, in 18 min). That reference is pre-split and has a
  different edge total, so compare counts.
- b1 FAILKEYs (36):
  - port 1 I2C: SCL x3, SDA x2, IRQ_N
  - C_CC1 x2 per port, C_CC2 x1 per port, P1 VBIAS, P1 CC1 x2, P2 CC1
  - GND pins U401/U501 .31/.36, J401.A1
  - P1 CHG_INT x2, P1_LDO_3V3 x2, P1 I2CC_SDA, P1 I2CC_SCL
  - **P1 PP5V x1**: the router edge for U401.34, which the planner left to the router
  - stage: REGN, HG1 x2, SW1 x2, P2 BTST1 x2, CELL3
- **Not checked:** power_open on the routed board. The routed .kicad_pcb stays on the PC, so dc_score was not run on
  it. The P1 PP5V failure means U401.34 depends on the pour alone: the pre-route board has it joined
  (power_open clean).
- No local 45-min route was run.

## 5. Still-blocked port edges in b1 and what walls each in
Port 1 (13):
- **U401.8/9/10 SDA/SCL/IRQ (5 edges: 3 to U501, plus SCL->R304 and SDA->R305).**
  - Cause, traced with `tools/joindbg.py` / `viadbg.py`: GND pin 7 gets no via. Its 0.3 mm link fails at the corner
    next to SDA pin 8 (0.4 mm pitch, planner raster room 0.21 < 0.25). So `return_join` runs from pin 7 to the
    nearest via-holding GND zone piece. That piece is port 2's HL_5V return pour round C544.2 at x ~99.7, 3.0 mm away.
  - Pin 14 has the same link failure (next to PD_DRAIN pin 15). It then joins pin 7's new piece: 2.8 mm straight
    west, under pins 13..8, with a `tight=True` path that keeps only clearance. U402.7 joins pin 14.
  - The result is a GND corridor 0.3 mm under pins 8-10, with pad 39 (GND) above: SDA/SCL/IRQ are sealed.
  - With pin 7's join refused (simulated), pin 14 goes to the C544 pour at 5.9 mm (limit 6.0), under all the pins.
    No placement within my parts fixes this: the C544 pour cannot move 3 mm, and walls would also block the escapes.
  - **Fix needed in the planner:** run return_join with the signal escape room (`tight=False`). This gave 24 of 400
    (p1 13->8) in the experiment, with no power opens. Another option is to skip joins whose corridor passes within
    the escape room of a signal pin.
- **U405 C_CC1 x2, C_CC2, VBIAS (4).**
  - J401's west VBUS pins A9/B4 (x 104.1) get a planner via stub down to y ~70.8. Their pour sits directly over
    U405's north pins 3-5 (x 103.5-104.3); the router F grid is walled there, and B5's own escape is under the blob.
  - U405 cannot move: H104's peg is to the east and C407 is to the south (the U405/C407/U401 stack is courtyard-tight,
    checked from 73.8 to 74.0). Moving it west needs C401/C402/C451/C403 moved too, and the C_CC tracks would still
    cross the stub.
- **U401.36 / U401.31 GND (2).**
  - The router's GND target includes pad 39 (exposed pad), but the cells between the pin row and pad 39 are inside
    the pins' clearance.
  - The PP5V pour of pin 34 is a terminal with no escape room within 1 mm, and GND pins get no escape ring at all
    (only signal nets do). So grow walls pin 36 north. Pin 31 is between PD_DRAIN 30 and the VBUS 32 piece.
  - The planner cannot place a via at either pin (0.4 mm pitch, link raster as above). This needs the planner or the
    router (pin-to-EP stub).
- **R402.2 I2CC_SDA -> U403.2 (1).** R402's end is free (dbg: F/B/via free round it). The walls are in the charger
  stage / at U403 (y 113), which is stagepwr's area.
- **J401.A1 GND (1).** The connector GND pad is next to the east VBUS stem (A4). The connector is fixed.

Port 2 (9):
- **U505 C_CC1 x2, C_CC2 (3).** Same as port 1, with J501's A4/B9 VBUS stub at x 95.9 over U505's pins 3-4. U505
  cannot move 0.2 mm south (C541) or 0.4 mm west (H102 peg).
- **U505.12/11 CC1/CC2 -> U501.28/29 (2).**
  - On F, the VBUS pour grown from C506.1 (87.95, 77.1) covers everything north of pins 26-31. The pins are within
    NEAR_TERM of pad 23, so they get no escape ring.
  - On B, PP5V crosses the VBUS stem by a detour from C507.1 to C541.1 at y ~77.6, grown from y 75.8 to y 79.3. So
    there is no via site anywhere above the north row.
  - Moving C507 north (b2/b3) opens PP5V at pin 34. A real fix would move the VBUS stem east (C506 next to H102/C541),
    which means moving C541 and L502: a bigger port-2 rework.
- **U501.37 DRV9_OFF -> Q509 (1).** The same B PP5V blob and the F PP5V/3V3 pours round R555 leave no via site. A
  `--only` ghost of this net alone finds a path (its MST then starts at R555), so it is marginal.
- **U501.36 / U501.31 GND (2).** As port 1.
- **CHG_INH R535 -> J302 (1).** R535 is a stage part, not mine.

## 6. Skill notes (for a cheaper model)
1. Copy the helpers: `ports/tools/pf.py` (MERGED = merged3_gu.json; load / pads / bb / check / save) and
   `ports/tools/quick.sh` (pdfix quick.sh + split_spec). Never edit other workers' files.
2. Score the base once with `tools/score_board_split.sh <out> <score.json> --route=0 --no-hot`. Check power_open and
   DRC, then queue it with `queue_route.sh` straight away.
3. Split the blocked edges by area: `V=-v python3 rebuild/tools/blocked.py <out>`.
4. For each blocked pad, find what walls it:
   - `bash ports/tools/dbg.sh <out> '<net>' x0,y0,x1,y1 out.png 'x:y;...' '<net>'`. Colours: red = F free, green =
     B free, blue = via ok, white = all, magenta = end cells. The printed `dbg at` lines name the net that owns each
     cell.
   - Read the `_ov.png`.
   - If a GND pin of a QFN is involved, run `python3 ports/tools/joindbg.py <out>/bare.json x0,y0,x1,y1`. It lists
     each return_join with its length; a join that runs under signal pins is the wall.
   - Run `python3 ports/tools/viadbg.py <out>/bare.json x,y` for why a pad gets no via. The letters mean: f/b = no
     room on F/B, h = hole pitch, t = track, l = link fails.
5. Make a variant as moves in `variants/mk.py`, run `pf.check` (must be []), then `quick.sh runs/<v> variants/<v>_score.json`
   (about 5 min). Read `p1.png` / `p2.png`, check power_open in quick.json, and keep or revert. Log every variant,
   including the bad ones.
6. For a keeper, run `score_board_split.sh <out> <score.json> --route=0` (hot on, about 10 min here). Check 7/7 tier 1,
   Read F.png / B.png, then `queue_route.sh <out> ports-<name>`. Poll `route_result.sh` in a background until-loop.

Traps:
- **A cap that looks loosely placed may be what connects a power pin.** Port 2's C507 PP5V pad carries U501.34's
  only PP5V connection (the planner reports "U501 (no path on F.Cu)", left to router). Moving C507 0.5 mm opens
  PP5V. Check power_open after every move near a power pin, not only the blocked count.
- **`return_join` uses `tight=True`.** A GND pin of a 0.4 mm QFN whose neighbour is a signal can never get a via:
  the 0.3 mm link fails on the 0.1 mm raster. Its join, and the joins of later GND pins that chain onto it, run
  straight under the signal pins. Placement can only move the target pour, and only if it moves more than 6 mm away.
- GND pins get no escape ring, only signal nets do. So power pours (grow 1.5 mm) hug GND pins next to a power pin.
- The router's ghost result for one net (`--only`) can differ from the full ghost run, because the MST endpoints change.
- quick.sh and the scorecard can differ by a few edges in the total (400 vs 401), because the edge total depends on
  copper. Compare counts and state the total.
- The stagepwr worker runs heavy jobs at the same time; keep at most one heavy job of your own.

## Files
- `tools/pf.py`, `tools/quick.sh`, `tools/dbg.sh`: copies of pdfix's helpers, pointed at merged3 / split zones.
- `tools/joindbg.py`: lists the planner's return joins.
- `tools/viadbg.py`: shows why a pad gets no via.
- `tools/plan_copper_joinfix.py` + `tools/quick_joinfix.sh`: planner experiment only, not the scorecard.
- `variants/mk.py`, `variants/b*_{gu,score,ov}.json`.
- `runs/m3`, `runs/b1_hot`: the scorecard outdirs.
- `runs/b1..b3`, `runs/b1_joinfix`: quick screens.
- `img/`: zooms and dbg images.
