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

### Why port 1 routed worse than port 2 (summary)
1. **The PD cluster was never fixed on port 1.** pdfix a3 / ports b1 moved port 2's EEPROM, pull-ups and LDO cap
   (U502, R502-R504, R541, C508) into the "pull-up in front of a walled pin" arrangement; port 1 kept the old one: R441
   4 mm behind R404, R404 1.3 mm off pin 18, so the SBU_FLT and P1_LDO_3V3 tracks wrapped R404.2 and pin 18
   (CHG_INT) had no exit (seen 57-117 cells); R441 -> R404 and both CHG_INT edges failed with it.
2. **pinesc ran on U501 only.** Port 2's PD pins 17/18/19/28 had reserved via sites; port 1's did not, so the
   crossing I2CC_SCL pair (U402.6 <-> U401.17, an unavoidable crossing between two CCW-numbered chips facing
   each other) and CC1 U401.28 -> U405.12 had no via room. On the old port-1 cluster pinesc looked worse on the ghost
   screen; on the port-2 cluster it helps, once q4 ties the GND pair U401.26/27 it would strand.
3. **Port 1's 5 V buck layout differs** (groundup p1top vs p2top + stagefix s3): R433 (FB divider top) sat behind
   R425 and C449, 2-3 mm from its PP5V pour, with both pads boxed by 0402s and GND vias: PP5V stub and FB edge failed
   alternately on every route.
4. **Port 1's column carries the MCU traffic.** U301 sits south of U403, so SDA/SCL U401 -> R304/R305 (36-37 mm),
   EN_5V1 (37 mm), EN_5V2 (crossing) and CELL3 (52 mm diagonal) all run down port 1's column next to its own three
   27-28 mm charger runs (I2CC_SDA, I2CC_SCL, CHG_INT, whose pins U403.1-3 face south toward the MCU). Port 2 has its
   three charger runs plus IRQ_N. This is why the stage pins on U403's north row (BTST1, LODRV1/2, REGN, HIDRV1) lose
   via sites on port 1 more often than on port 2; it is congestion (router 'pulled' / 'no way after baked routes'),
   not sealed pads, and not fixable inside port 1 without moving the MCU block.
5. **HG1 Q401.1 -> R444**: the gate-escape via site was free but the ACP_F Kelvin pair (routed first) ran In2 over it;
   drawing the gate via as copper (q3) fixes it on both ports.
Copper otherwise is the same per port (1b): hard copper areas match within 10-15 %.

## Step 2: sub-route screen (`tools/route_sub.sh`)
`tools/router_sub.py` = tools/score/router.py + one option `--box=x0,y0,x1,y1[;...]` (keeps only the edges with an end
in the box or whose straight line crosses it; nothing else changed, same --softnets, env ROUTER_OPTS passed through).
`tools/route_sub.sh <scorecard outdir> <workdir> [box] [MIN]` routes the port-1 column (default box 99,66,121.6,116:
PD chip, cluster, stage, the I2CC/CHG_INT runs to the charger and the MCU-bound runs crossing it): 130 of 369 edges.

Validation on lead_final/sc_Z (runs/sub_Z): **119 routed / 11 failed of 130 in 16 min** (one core).
Full local route of the same board failed 13 port-1 edges; the sub-route reproduces 8 of them (CC1 x2, BTST1 D404 ->
U403.26, I2CC_SDA R402 -> U403.2, CHG_INT U403.3 -> R404, PP5V R433 stub, P1_LDO_3V3 R441 -> R404, HG1 Q401 -> R444),
the other 3 are the same family of congestion fails (LODRV2 U403.21, BTST1 U403.26 -> C412, SBU_FLT R441 -> U401.19;
the first two failed on the PC route of the best board). It misses the I2CC_SCL pair and REGN x2 (those failed only on
the local route). Rip-up order and RIPTIME make any single run noisy by about +-2 edges, so the screen is used for
differences of 3 or more. It takes 16-35 min (load dependent) instead of 90-120 min.
Afterwards, against the PC routes: port-1 failures on the PC were 10 (v1, sub 7), 6 (v5q, sub 4), 4 (v5p, sub 4),
9 (v6p, sub 3). It ranks the big steps right (base 11 -> 4) but not differences of 1-2 edges; the full route has its
own spread of several edges (v6p: PC 19 vs local 10 on one board).

## Step 3: variants (all split copper, scorecard via tools/score_r4.sh --route=0 --no-hot, then the sub-route)
Base copper = team best recipe (`tools/best_env.sh`). Planner options of `tools/plan_copper_q.py` used below:
q1 `--connesc_big=0.9` (strip + via site out of TC2030-size connector pads), q2 `--padjoin=4` (thin track from a
2-pad part's power pad to its own pour within 4 mm), q3 `--gatevia=1` (gate escape strip + via of a sealed FET drawn as
copper), q4 `--gndtie=1` (via for an IC GND pin left floating by --pinesc reservations, reservations relaxed but kept by
VIA_PITCH / clearance). `--pinesc_refs=U401,U501` = planner P's pin-escape reservations on port 1's PD chip as well.

| run | placement | planner extra | power_open | DRC | blocked | sub-route failed | loss W | notes |
|---|---|---|---|---|---|---|---|---|
| sub_Z | best (lead_final/sc_Z) | - | allowed only | 0 | 5 of 369 | 11 of 130 | 0.835 | reference |
| v1 | port-2 cluster copied to port 1 (variants/v1.json) | - | allowed only | 0 | 5 of 369 | 7 of 130 | 0.826 | PC full route 355 / 14 failed of 369, 102.9 min, done (r4_port1-v1) |
| v2 | v1 + R433 turned (PP5V pad north) | - | allowed only | 0 | 5 of 369 | 9 of 130 | 0.827 | worse, PP5V stub still no way |
| v1q | v1 | q1 q2 q3 | **CELL_P open at F102** | 0 | 4 of 366 | 8 of 128 | 0.702 | q1 rejected: the J302 north-row strips cut the only CELL_P strip from F102 (between J302 and H103/J118); HG1 routes now (q3) |
| v1p | v1 | q2 q3 + pinesc U401 | allowed only | 0 | 7 of 367 | 6 of 131 (2 = GND pair U401.26/27 floating) | 0.828 | CC1 and both I2CC_SCL edges route with pinesc on U401; the GND pair lost its via room to pin 28's via site -> rule q4 |
| v5q | v5 = v1 + R433/R425 swap (variants/v5.json) | q2 q3 | allowed only | 0 | 5 of 364 | **4 of 128** (BTST1 x2, I2CC_SCL U402.6->U401.17, CC1 U401.28) | 0.828 | R433 FB and PP5V, HG1, CHG_INT, I2CC_SDA long run all route; queued on PC as r4_port1-v5q |
| v5p | v5 | q2 q3 q4 + pinesc U401 | allowed only | 0 | 5 of 364 | **4 of 128** (LODRV1, CHG_INT x2, I2CC_SCL R403->U403.1) | 0.828 | gndtie keeps the GND pair tied (blocked back to 5); CC1 and the short SCL route; the long charger runs fail this time (order noise); queued on PC as r4_port1-v5p |
| v6p | v6 = v5 + R404 straight in front of U401.18, R441 staggered (variants/v6.json) | q2 q3 q4 + pinesc U401 | allowed only | 0 | 5 of 364 | **3 of 128** (HIDRV1 pulled, I2CC_SCL U402.6->U401.17 pulled, SDA U401.8->R305 node cap) | 0.829 | best screen; every CHG_INT / I2CC run to the charger routes; queued on PC as r4_port1-v6p |
| v3b | v1 cluster with R404 in front of pin 18 (variants/v3b.json) | - | - | - | - | - | - | scorecard stopped by the earlier pause, superseded by v6 |
| v6r | v6 | v6p + pinesc on U403/U503 | allowed only | 0 | **7 of 366** | 3 of 129 | 0.818 | rejected: the BTST1 pin-26 reservation cuts the SW1 tap of the bootstrap caps C412 / C512 from the SW1 pour (2 new blocked edges) |

### v6p with hot loops (runs/v6p/hot, `tools/score_r4.sh ... --route=0 -- $(cat tools/best_plan_opts.txt)`)
`{"loss_W": 0.829, "power_open": {"3V3": ["L201"], "GND": ["J302", "J301"]}, "drc_errors": 0, "hot_loops": "7 of 7 pass, 6.24 nH", "blocked_edges": "5 of 364"}`
Copper is identical to runs/v6p/sc (same spec.json vias/tracks/zones), so the PC route of r4_port1-v6p is this board.
Edge total 364 instead of 369: q2/q3 draw 5 short power/gate stubs as copper (R417 3V3, R518/C111/R113 PACK_P, R106
FET_MID pad joins; Q401/Q402/Q501/Q502 gate vias), so those edges are no longer router work.
F.png / B.png read: port-1 PD chip still directly below J401 with U405 between, the cluster is the port-2 arrangement
(EEPROM U402 south of pins 16/17, pull-ups west of it, R404 under pin 18, R441 beside it), R433 sits on the PP5V pour
edge next to U404, nothing stranded; port 2 unchanged (its cluster was already this arrangement), so the two ports
are now copies in the PD cluster.

### Rules tried and their effect
- q1 `--connesc_big` (TC2030 pad escape for SCL J302.6): rejected, opens CELL_P at F102. The CELL_P pour reaches F102
  only through the 1 mm strip between J302's north pad row and H103 / J118; any escape for J302.6 cuts it. J302.6 needs
  CELL_P re-planned (e.g. a B.Cu / In3 path from F102.2) or a moved F102; both are outside port 1 and left open.
- q2 `--padjoin=4`: draws 5 stubs (see above); R433.1 is not drawn by it on any placement (boxed by R425 / C449 / R432
  0402s); the R433/R425 swap is what fixed both R433 edges (PP5V pad now 1 mm from the pour, the router finds it).
- q3 `--gatevia=1`: HG1 Q401.1 -> R444 routes on every screen since (was "no way" on every full route of the base).
- `--pinesc_refs=U401,U501` (pinesc on port 1 too): with the port-2 cluster placement it now helps (CC1 U401.28 and
  the short I2CC_SCL route), unlike on the old cluster where it was rejected; needs q4 for the GND pair.
- q4 `--gndtie=1`: one via for U401.27 at 107.45, 78.67; blocked back from 7 to 5.
- pinesc on the charger chips U403/U503: rejected (cuts the bootstrap-cap SW1 taps, blocked 7).
- `--pinesc_via=0.0` (instead of q4) also frees U401.26's via, but shrinks every reserved via site (U501 too); not used.

## Step 4: full routes on Logan's PC (split copper; compare FAILED edges and the edge total)
| name | board | routed / failed of edges | minutes | status | failed edges |
|---|---|---|---|---|---|
| (ref) lead_final sc_Z | team best | 352 / 17 of 369 | 92 | done | 13 port 1, 3 port 2, 2 gauge/MCU (local list) |
| r4_port1-v1 | v1 (cluster copy only) | 355 / 14 of 369 | 102.9 | done | P1: LODRV1, BTST1 x2, FB U404.8->R433, CHG_INT R404->U401.18, CC1, I2CC_SDA long, I2CC_SCL long, HG1; P2: HIDRV1; other: SMBC, SCL J302.6, CELL_P C110->R118, CELL3 |
| r4_port1-v5q | v5q | 352 / 12 of 364 | 121.0 | done | P1: BTST1 x2, I2CC_SCL U402.6->U401.17, CC1, ACUV U403.34->R409, I2CC_SCL R403->U403.1; P2: LODRV1, CHG_INT R504->U501.18, BTST1 D504; other: SMBD, SMBC, SCL J302.6 |
| r4_port1-v5p | v5p | **355 / 9 of 364** | 112.5 | done | P1: LODRV2, HIDRV1, CHG_INT R404->U401.18, BTST1 D404->U403.26; P2: HIDRV1, I2CC_SDA U502.5->U501.16; other: VC2 U101.4->C102, SMBC U101.19->R115, SCL J302.6->U301.9 |
| r4_port1-v5p-rep | v5p again (identical board, same sha) | **354 / 10 of 364** | 88.2 | done | P1: BTST1 U403.26->C412, BTST1 D404->U403.26, I2CC_SCL U402.6->U401.17, REGN R454->C410; P2: REGN C510->U503.24, REGN R515->U503.24, HG1 Q501.1->R544; other: CELL_1N U101.33->U101.16, SMBC U101.19->R115, SCL J302.6->U301.9 |
| r4_port1-v6p | v6p (v5p + R404 in front of pin 18) | 345 / 19 of 364 | 106.4 | done | P1: LODRV2, I2CC_SCL x2, REGN x2, FB R419->U403.12, BTST1 D404, ACUV, I2CC_SDA long; P2: LODRV2, HIDRV1, I2CC_SDA U502.5; other: CELL_1N, U102-V3, BTP_INT x2, SMBC, SCL J302.6, 3V3 R302 |

v6p differs from v5p only by R404 / R441 (0.4-1.4 mm) yet fails 10 more edges, 7 of them in the gauge / MCU block that
neither variant touches: one full route has a spread of several edges from rip-up order alone (also seen as PC 17 vs
local 18 with different sets on the reference). So single PC numbers are compared with that in mind; v5p is the best
measured board and is the delivered variant. A repeat of the identical v5p board (r4_port1-v5p-rep) gave 10 failed, so v5p is 9-10 failed, not a lucky draw.

### Local full route (fallback: r4_port1-v5q had no PC result 75 min after queueing, so ONE local route was run)
`../tools/route_local.sh runs/v6p/hot 150` (90 min, finished, not timed out):
`"route": "354 of 364 routed, 10 failed", "routed_loss_W": 1.165, "routed_power_open": {"3V3": ["L201"]}, "routed_drc_errors": 0`
(reference sc_Z local: 351 of 369, 18 failed, routed_loss_W 1.127, routed_power_open 3V3@L201 only).
Failed: P1 LODRV1, I2CC_SDA U402.5->U401.16, BTST1 D404->U403.26, I2CC_SDA R402->U403.2, I2CC_SCL R403->U403.1;
P2 HIDRV1, LODRV1, I2CC_SDA U502.5->U501.16; other SMBC U101.19->R115, SCL J302.6->U301.9.
The routed board keeps every power net closed (dc_score on routed.kicad_pcb), so the counts are not flattered by
pours the router ran through. Same board on the PC: 19 failed - the spread between two routes of one board is large.

### v5p with hot loops (runs/v5p/hot) = delivered board
`{"loss_W": 0.829, "power_open": {"3V3": ["L201"], "GND": ["J302", "J301"]}, "drc_errors": 0, "hot_loops": "7 of 7 pass, 6.24 nH", "blocked_edges": "5 of 365"}`
(copper identical to runs/v5p/sc, which is the PC-routed r4_port1-v5p; that screen said blocked 5 of 364).

### Router-side check (recommendation only, not part of the board result)
Sub-route of v5p with `ROUTER_OPTS="--maxrip=8 --capx=3"` (routes may be pulled 8 times, node caps x3): 6 of 128 failed
in 31 min vs 4 of 128 with the default options. No gain; not recommended. The limits named in 1d stand as findings.

## Result and deliverables
Delivered variant **v5p** = placement `overrides/50_r4_port1.json` (on top of final/overrides; build with
`tools/build_r4.sh <workdir> overrides/50_r4_port1.json`, checked: CHECK clean, identical to `placement.json`) +
planner `tools/plan_copper_q.py` with `tools/best_plan_opts.txt` appended to the team BEST_PLAN
(`tools/score_r4.sh <outdir> placement.json --route=0 -- $(cat tools/best_plan_opts.txt)`).
- Moves (7 parts, port 1 only): C408, U402, R403, R404, R441 to the port-2 cluster arrangement (+21.0 mm; R402
  already matched); R433 <-> R425 slot swap at the port-1 5 V buck.
- Hard limits: power_open 3V3@L201 + GND@J301/J302 only, DRC 0, hot loops 7 of 7 tier 1 at 6.24 nH (= reference),
  blocked 5 of 364/365, loss 0.829 W (ref 0.835).
- PC full route: **355 routed / 9 failed of 364, 112.5 min, done**; repeat of the identical board 354 / 10 failed
  of 364, 88.2 min, done (reference 352 / 17 of 369). Target 8 or fewer not quite met.
  Remaining failed edges: port 1 LODRV2 U403.21->R447, HIDRV1 U403.27->R444, CHG_INT R404->U401.18, BTST1
  D404->U403.26; port 2 HIDRV1 U503.27->R544, I2CC_SDA U502.5->U501.16; gauge/MCU VC2 U101.4->C102, SMBC
  U101.19->R115, SCL J302.6->U301.9.
- Port 1 went from 13 failed edges to 4 on both PC routes of v5p; none of the 27-28 mm charger runs (I2CC_SDA,
  I2CC_SCL, CHG_INT), CC1, PP5V/FB at R433 or HG1 failed on either (the repeat lost BTST1 x2, the short I2CC_SCL and
  REGN R454->C410 instead).
- Not delivered: v6 (R404 straight in front of pin 18) - best sub-route screen but PC 19 / local 10 failed, no better
  than v5p. The stage pins on U403's north row (HIDRV1, LODRV1/2, BTST1) still
  fail on both ports in turn: the stage is an exact copy, so that is a stage-placement matter (D404/D504 sit west
  of pins 27/28 whose escapes go north, so BTST1 must cross them; a bootstrap diode east of pin 26 / next to C412
  would remove the crossing) rather than a port-1 difference.
- Not fixed: SCL J302.6 (needs CELL_P re-planned, q1 shows the conflict), CELL3 / SDA long-edge node-cap failures
  appear on some routes only.
