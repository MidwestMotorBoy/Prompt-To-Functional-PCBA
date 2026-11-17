# r6_caps (team A, round 6): keep power pads joined on the ROUTED board

Board: stack S (`best_placement.json`), planner M + `$BEST_PLAN_R5` (r5_merge), split-zone scorecard. New copper step
`tools/capfix.py` runs after split_spec/BUS4/BUS4B and before write_copper (env `CAPFIX` in `tools/score_board_r6.sh`).
Recipes: `source tools/env_r6.sh` (`CAPFIX_E` = the delivered one); `tools/run.sh <name> CAPFIX_E --route=0` scores it.
Local full route + routed checks: `tools/route_local_r6.sh runs/<name> 150`.

## Result: candidate **ce** (`CAPFIX_E`)

| | base (stack S, re-run here) | **ce** |
|---|---|---|
| power_open | allowed | allowed |
| DRC errors | 0 | **0** |
| hot loops | 7/7, 6.27 nH | **7/7, 6.27 nH** |
| blocked edges | 4 of 364 | **4 of 361** (same 4: SCL J302.6, CHG_INH R535, GAUGE_FUSE U101.25, P2 DRV9_OFF) |
| loss (pre-route) | 0.801 W | 0.809 W |
| PC full route | 356 / 8 failed of 364 (lead5-S, twice) | **353 / 8 failed of 361** (r6caps-ce, 79.5 min, done) |
| local full route | 357 / 7 of 364 | 355 / 6 of 361 (about 40 min, not timed out) |
| routed DRC errors | 0 | 0 |
| routed loss | 1.070 W | 1.087 W |
| routed_pad_unjoined | 3V3 C207.1, C403.1, C503.1; PACK_P C213.1; PPHV C409.1, C509.1 | **PPHV C409.1, C509.1 only** |
| every pad off main (allpad_check, routed) | 3V3: C207.1 C403.1 C503.1 R305.1 R314.1 R417.2 R517.2 TP301.1 U204.10 U401.38 U501.38; PACK_P C213.1 R518.1; PPHV south groups; P2 PP5V R533.1 | 3V3 R314.1, R417.2; PPHV south groups (C409.1 R409.1 U403.32/33, C509.1 R509.1 U503.32/33); P2 PP5V R533.1 |

PC failed list of ce (8): P1 I2CC_SCL U402.6->U401.17 and R403->U403.1, P1 CHG_INT R404->U401.18 and U403.3->R404,
P1_LDO_3V3 R404->R441, SMBC U101.19->R115, SCL J302.6->U301.9, CELL_P C110->R118: the same port-1 PD-cluster /
charger-run / gauge set as stack S (lead5-S: I2CC_SDA x3, I2CC_SCL, P1_LDO_3V3 x2, SMBC, SCL). No new region.

## Why each pad was cut (routed board of stack S, runs/base, re-routed here: 357/7, same as lead5)
router.py runs with `--softnets=GND,PACK_P,3V3`: EVERY zone of these nets, on every layer, is soft (signals may cut it;
KiCad refill carves round them). Tracks are hard. The router routes F, In2, In3, B only (In1/In4 never).
- 3V3 had ONE copper body: the In3 pour (horizontal routing layer) + six vias (L201 tree, U301 cluster x3, C403, C503,
  both via-in-pad) + small soft F.Cu stub zones. Routing cut the In3 pour into 8 pieces with pads: the MCU cluster
  (main), **L201/C207/TP301/U204.10 (the regulator output itself)**, the PD-chip group C403/C503/U401.38/U501.38, and
  single pads R314, R305, R417.2, R517.2. dc_score did not see it (it solves J301 -> L201, already the allowed open).
- PACK_P C213.1: B.Cu pad on a 6.8 mm2 soft B.Cu stub zone shared with C212 and two vias; the router cut the stub
  between the pads (C212 kept the vias). R518.1 the same on F.Cu.
- PPHV C409.1/C509.1 (and R409, U403.32/33): **router bug, not copper.** KiCad reports "Zone 'pc_..._PPHV' | Pad 32 of
  U403"; router.py turns a non-plane "Zone" end into B = A's position, and searches the zone goal mask only in the window
  round the pad, finds none, and "routes" a zero-length track at the pad. So VAC of both chargers is unconnected on
  every routed board of rounds 4-5 (routed tracks of PPHV stop at y 110; nothing goes north).

## What capfix does (all options in tools/capfix.py docstring)
1. `--band=3V3`: a 3V3 copy on **In4** (the router never routes In4; refill only clears signal vias): Steiner tree of
   2.0 mm bands (0.8 mm necks allowed, cost x3) on a 0.1 mm grid round the In4 PACK_P copy, other-net vias and PTH,
   over all 3V3 via groups, + spurs to 3V3 pads within 12 mm. In4 is split in two by the PACK_P copy (west band at
   y 123-126 and the diagonal), so `--cross` joins the two In4 pieces through a **hard F.Cu track** (0.4 mm, 6.4 mm,
   mostly inside the existing L201/C207 3V3 stub zone) from the L201 via to a NEW via at (87.90, 122.82) north of the
   band (site = shortest path + escape-room penalty near other-net small pads + avoid-map penalty). 254 mm2, 2 pieces.
2. `--stubs=1`: hard tracks from cap pads of 3V3/PACK_P that sit in a small (< 40 mm2) soft stub zone to the zone's
   via/track (C302, C207, C301, C107, C303, C209, C213), path inside the zone; sealed Kelvin pads skipped.
3. `--links` (F.Cu, pad clearance 0.16 mm, other copper 0.3 mm) R509.1->C509.1 (port 2 lacked port 1's planned track),
   and `--link3d` (multi-layer grid path F/B with vias legal on all six layers, no via in small own-net pads,
   escape-room via penalty, optional `--avoid=<routed board>` cost map) C409.1->U403.33, C509.1->U503.33: VAC cap,
   divider and VAC pins are one planned piece (4.6 / 5.2 mm, 2 vias each).

## Tried and rejected (numbers)
| run | what | screen | full route |
|---|---|---|---|
| ca | band + stubs + F.Cu C409->U403.33 link (along pins 34-36) + N-S PPHV link3d on In2 | blocked 11 (ACOV/ACUV walled), loss 0.841 (In2 PACK_P slit +34 mW) | - |
| cb | band + stubs only (old cross site 87.50,122.82) | 4 of 363, 0.807 W | PC 352 / **11** of 363 (104 min); new: CE_N x2, VC1, U503-ICHG (R513 beside the cross via), CHG_INT. cb-rep (same board) 352 / 11 again, 103 min: the PC route is repeatable per board, so the +3 was real; ce (cross via moved by the escape-room penalty, plus the south PPHV links) routes with 8, so the via site is the likely cause (not isolated) |
| cd | ce-like + **planned PPHV north-south link** (B.Cu, 28-32 mm, 2 vias each) | 5 of 359, 0.812 W, hot 7/7, all pads joined pre-route | PC 343 / **16** (136 min); local 347 / 12, but routed_pad_unjoined EMPTY and routed_power_open EMPTY |
| cf | cd with the links steered by the base-route avoid map | 6 blocked (ACN_F, LODRV2 at U403) | - |
| cg | ce + `--anchor` (via just outside the PD PPHV tree so the ratsnest says Via, not Zone) | 4 of 361; port 2 anchored, **port 1 no legal spot** | queued r6caps-cg, pending at write time |
| cj / ck | ce + R314.1 link3d / R417.2 F.Cu link | blocked 5 (SWDIO J301.2), cj also 2 DRC (NPTH hole; fixed in tool) | - |

So: the 3V3/PACK_P fix is free for routing (ce 8 failed); a planned 30 mm PPHV north-south link costs 5-8 failed edges
(it takes the port-1 column the long CHG_INT/I2C runs need). Goal "C409.1/C509.1 joined by planned copper" is met
only to the VAC pins (local piece); the north-south join is still open, now traced to the router bug.

## Open items for the lead
- **PPHV VAC open on every routed board** (router bug above). Options: fix router.py (for a non-plane net, a "Zone" end
  should use the zone mask over the whole net, or the nearest zone point as B), or `--anchor` (works on port 2, port 1
  needs a legal spot: relax its clearance to pad spacing), or accept cd's planned link (+8 failed).
- 3V3 R314.1 and R417.2 single pads: the router lands their via on an In3 island off the band (R417.2 sits inside the
  In4 PACK_P copy). Their planned links cost SWDIO. Needs a per-pad planned via onto the band before routing.
- P2 PP5V R533.1 off main on routed boards (base and ce).
- Routed loss +17 mW (GND 0.298 -> ~0.33 on cd: the band splits In4 GND and router vias perforate it); a 1.2 mm band
  would cost less.

## Files
- tools: `capfix.py`, `allpad_check.py` (every pad of every power net on the main piece), `score_board_r6.sh`,
  `route_local_r6.sh` (both: + CAPFIX, allpad.json / allpad_routed.json, routed_allpad_off, routed_unconnected_power),
  `env_r6.sh`, `run.sh`, `zoomplot.py`.
- runs: base (stack S re-route, routed.kicad_pcb kept: input of `--avoid`), ca, cb, cd (local route), ce (delivered:
  score.json, F/B.png, routed board + routed_*.png incl. In3/In4), cf, cg, cj, ck. img/: In4 views.
- PC queue names: r6caps-cb (352/11), r6caps-cb-rep (352/11), r6caps-cd (343/16), r6caps-ce (353/8), r6caps-cg (pending at write time; poll with ../route_result.sh r6caps-cg).
