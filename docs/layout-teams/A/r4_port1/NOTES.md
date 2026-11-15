# Worker r4_port1 (team A, round 4): why port 1 routes worse than port 2, and fixes

All copper is split-zone (team scorecard `tools/score_board_best.sh` with the best recipe of `tools/best_env.sh`,
called through `tools/score_r4.sh`, planner `tools/plan_copper_q.py` = portcu planner P + r4 options).
Base = team best `best_placement.json` / `lead_final/sc_Z` (power_open allowed only, DRC 0, 7/7 6.24 nH,
blocked 5 of 369, PC route 352 / 17 failed of 369, local 351 / 18 failed).

## Step 1: diagnosis (no part moved)

### 1a. Placement diff, port 1 vs port 2 (`tools/portdiff.py bare.json`)
Pose of every 4xx part relative to its nearest anchor (U401, J401, L401, U403) against the 5xx twin.
The stage (Q4xx/C4xx round L401) is an exact copy. The PD cluster is NOT:

| part | port 1 (rel. U401) | port 2 (rel. U501) | note |
|---|---|---|---|
| U402 EEPROM | +1.1, +5.6 | +0.3, +5.5 | port 2 moved by pdfix a3 / ports b1 |
| R441 SBU_FLT pull-up | +3.3, +6.1 (behind R404, 4 mm from pin 19) | +2.5, +3.25 (straight in front of pin 19, 1 mm) | ports b1 "pull-up in front of a walled pin" applied to port 2 only |
| R404 CHG_INT pull-up | +3.3, +4.4 (1.3 mm east of pin 18) | +2.4, +4.9 (0.4 mm east of pin 18) | |
| R402/R403 I2CC pull-ups | SDA -1.9, SCL -1.0 | SCL -2.8, SDA -1.9 | |
| C408 LDO cap | -1.1, +3.7 | -1.8, +3.7 | |
| U404 buck, R432/R433/R434, C439/C446 | buck rot 90 north-east of the chip | rot 180, south-east | different groundup scripts (p1top / p2top), stagefix s3 moved R432/R433 |
| U405 protector, C401/C402/C452 | J401 -2.2 | J501 +2.25 | connectors are fixed and not a translation of the PD chips: U401-J401 dx 1.4, U501-J501 dx 9.4 |
| PD chip to charger | U403 - U401 = 5.74 mm east | U503 - U501 = 3.71 mm east | port 1's I2CC/CHG_INT runs to the charger jog 2 mm more |

The override files show it directly: `final/overrides/20_pdfix_a3.json` and `30_ports_b1.json` move C508, U502,
R502, R503, R504, R541 (port 2) and nothing of port 1's cluster. Port 2 got the round-2 cluster fix, port 1 never did.

### 1b. Copper diff (`tools/cudiff.py spec.json`, port-1 boxes vs the same boxes shifted 21 mm)
Hard copper (what the router cannot cross) is nearly the same per port: PD south box AC_SNS_N F 22.6 / B 11.4 mm2
(port 2 19.8 / 10.1), PPHV 5.6 / 6.6, SW1 12.7 / 13.5. Differences are in soft copper only (PACK_P In2 95 vs 0.4 mm2,
In4 bus 33 vs 0, 3V3 In3 56 vs 104), and soft zones (GND, PACK_P, 3V3) are passable for router.py. `--pinesc` is on
U501 only; on U401 it was rejected (5 -> 7 blocked, two GND pin-pair tracks left floating). The In4 bus is not a
routing layer. So copper does not explain 13 vs 3.

### 1c. Nets crossing the port columns (`tools/edges.py drc.json box`)
Box x 99-121.6, y 70-116 (port 1 column) against x 78.4-99 (port 2): port 1 holds 93 edges inside plus these long
foreign runs; port 2 88 inside.

| port 1 column carries | port 2 column carries |
|---|---|
| SDA U401.8 -> R305 (36.9 mm), SCL U401.9 -> R304 (35.8 mm): the MCU I2C pull-ups sit beside U301 / U403 | IRQ_N U501 -> Q103 (37 mm) |
| EN_5V1 R432 -> U301 (37 mm) | |
| EN_5V2 U301 -> U504 (40 mm, crosses) | EN_5V2 (ends at U504) |
| CELL3 J111 -> R103 (52 mm, crosses diagonally, HighCurrent class, +0.1 mm clearance) | CELL1 J109 -> R101 (52 mm) |
| SDA/SCL/IRQ_N U401 -> U501 (21 mm west) | (same edges, other end) |

The MCU U301 sits at x 111-117, y 119-127, directly south of port 1's charger U403. Every MCU-bound net from the
PD chips and the 5 V buck enable (SDA, SCL, EN_5V1, EN_5V2) runs down port 1's column, through the same gaps
as port 1's own I2CC_SDA / I2CC_SCL / CHG_INT runs to U403 (27-28 mm each). Port 2 has its three charger runs and
one MCU net.

### 1d. Router limits behind "no way" (tools/score/router.py read, not edited)
- "no way even with every other route gone" is NOT the ghost screen's no-way: the rip-up ghost search runs on
  `FIX` = pads + pours + fan-out stubs + routes **baked** (pulled MAXRIP=4 times, then laid for good for the rest of
  the phase). Baked routes stay. So a pad that is free on the ghost screen (blocked 5 of 369) is "no way" once a
  baked neighbour route hugs it: `seen 64-290` in the fail line = the pad's free region is only a few hundred cells.
  These are congestion failures, which is why blocked_edges does not move with them.
- Search window: pad 6 mm round the two ends for edges < 10 mm, 12 mm for < 30 mm, 30 mm above. Node cap
  NODE_CAP = 2.4 M (x2 / x5 for >= 30 mm, max 12 M); the rip-up ghost halves the cap for edges < 30 mm (1.2 M).
  I2CC_SDA R402 -> U403.2 (27.8 mm) used 1.68 M nodes in the real search (exhausted: no path) and exceeds the
  1.2 M ghost cap, which is why it is also a GHOSTFAIL on the ghost screen. CELL3 (52 mm) hits the 12 M cap
  (seen -12000001): the search gives up, it is not proven walled.
- Layers F, In2 (vertical only), In3 (horizontal only), B; via = 0.45/0.3, 0.6/0.75 mm via-to-via; a via needs all
  four routing layers free. Between the PD chips and the chargers F and B are mostly power pours (AC_SNS_N, SW1,
  SW2, PPHV), so a long run is: F escape -> via -> In2 down -> via -> F at the far end. The via sites at both ends are
  the scarce resource (dbg of I2CC_SDA: F walled from y 89 to 108 on the whole column, B free only west of Q401).
- Each pad edge starts from the pad cells only: a pad that already has one route out (U401.8 SDA to U501) and
  neighbours on both sides has no start cell left for its second edge (SDA U401.8 -> R305: seen 99).
- RIPTIME = 1500 s of wall clock per phase: the result depends on machine load (PC 17 vs local 18 failures with
  different sets: LODRV1/2, BTST1 x2, SBU_FLT, CELL_1N, SMBC on the PC; HG1, REGN x2, HIDRV1, I2CC_SDA P2 locally).

### 1e. Named walls, failed port-1 edges vs their port-2 twins
| failed port-1 edge (local / PC) | port-2 twin | wall |
|---|---|---|
| CHG_INT R404 -> U401.18 (no way, seen 117/275) | R504 -> U501.18 routes | R441's SBU_FLT track from pin 19 runs down past pin 18 to R441 4 mm away (port 2's R541 sits in front of pin 19); pin 18 boxed by the pin-17 and pin-19 routes |
| P1_LDO_3V3 R441.1 -> R404.1 (seen 253) | R504 -> R541 routes | the two 0402s stacked 1.7 mm apart with R441.2 between; enclosed by the SBU_FLT and CHG_INT tracks |
| I2CC_SCL U402.6 -> U401.17, R403 -> U402.6 | routes | U402 1.1 mm east of the chip (port 2: 0.3); with SDA pad east of SCL the two cross and one needs a via in the cluster |
| CHG_INT U403.3 -> R404, I2CC_SDA R402 -> U403.2 (27-28 mm) | route | shared column with SDA/SCL/EN_5V1 to the MCU, via sites only at the cluster and south of U403 (1c, 1d) |
| PP5V R433.1 -> pour (3 mm, seen 221) | R533 routes (different buck layout) | pad 1 faces south into R426 / R434 / U404 pins, the pour is north / east; stagefix moved R433 there |
| CC1 U401.28 -> U405.12, U405.12 -> C401 | U501.28 routes since portcu pinesc | port 2 has the pinesc via-site reservation at pin 28 (U501 only); on U401 pinesc was rejected on the ghost screen |
| HG1 Q401.1 -> R444, BTST1 D404 -> U403.26, REGN | port 2 HG1/HIDRV1 fail as "pulled" | stage is an exact copy; the extra MCU-bound nets above take the via sites round U403's north pins |
| SCL J302.6 -> U301.9 (non-port) | | TC2030 pad 6 on the outer row: CELL_P pour wraps it at the 0.4 mm escape room, H103 peg and the NPTH peg close the rest; a track from a HighCurrent pour needs 0.25 mm + 0.1 mm (dbg_scl_j302_ov.png) |
| CELL3 J111 -> R103 (52 mm) | CELL1 J109 -> R101 routes | node cap 12 M exhausted, not a sealed pad |

(continued below as the work goes on)
