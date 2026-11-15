# Worker `strapfix` (team A, round 3): keeping power joined on routed boards

All numbers here use split-zone copper (score_board_split chain). Base = stagepwr v1 placement
(`stagepwr/best_score.json`), planner A (`--sealed=1 --taps=1`).

## Result

**Don't strap PACK_P on In2. Put a second PACK_P copy on In4, and pour soft GND on B.Cu.**
`router.py` routes only F, In2, In3 and B. In1 and In4 are GND planes it never routes on. So PACK_P copper on In4 can
be pierced by signal vias, but no signal track can cut it. It also blocks nothing for the router: there are no
strap tracks on In2. The In4 GND plane loses that area, which costs GND loss. A soft GND fill on B.Cu (2 oz, priority
0, under every hard zone) wins that back and more. GND is a soft net for the router, so the fill also costs no
routing. The router cuts it like any other plane and KiCad refills around the tracks.

Best board: `runs/sc_i4b` (options in `best_opts.txt`; the placement is the v1 placement, unchanged).

| variant | blocked | DRC | power_open before route | hot loops | loss before | local route (riptime 600) | routed power_open | routed DRC | loss after route |
|---|---|---|---|---|---|---|---|---|---|
| v1A3, no straps (stagepwr full_v1A3) | 25 of 396 | 0 | allowed | 7/7, 6.21 nH | 1.034 W | 355 / 41 failed of 396 | **PACK_P open at D103, U204** | 0 | 1.744 W |
| v1A3S2, In2 straps 41 tracks/120 mm (stagepwr) | 26 of 399 | 0 | allowed | 7/7, 6.21 nH | 1.034 W | 352 / 47 failed of 399 | 3V3@L201 | 0 | 1.364 W |
| **sc_i4b: In4 PACK_P (MST 3 mm + pour copy in x96-122,y100-140) + B.Cu soft GND fill, no In2 straps** | **25 of 396** | **0** | allowed (3V3@L201, GND@J301/J302) | **7/7 tier 1, 6.22 nH** | **0.835 W** | **360 / 36 failed of 396** | **3V3@L201 only** | **0** | **1.092 W** |

On the routed sc_i4b board, PACK_P loss rises from 0.131 to 0.282 W and GND from 0.225 to 0.330 W. The J113 path
goes from 0.83 to 1.83 mΩ, because the router still cuts the In2 pour (885 of 1271 mm² left), but In4 holds it
together. The routed loss is 1.092 W, under the 1.2 W target.

PC route (Logan's PC): `strapfix-i4b` (`A/strapfix-i4b-c11849ff.json`, queued 05:37 UTC): **358 routed / 38 failed of 396, 53.5 min, done**. That is the same as the no-strap v1A3 board (358/38) and 5 fewer failures than the In2 straps (355/43 of 398), with power still joined after routing (shown on the local route).

Split baselines (PC): hand 363 / 59 failed of 422; b1 364 / 36 of 400; v1 stock 363 / 37 of 400; v1A3 (no straps)
358 / 38 of 396; v1A3S2 (In2 straps) 355 / 43 of 398.

## Part 1: why routing cuts PACK_P, and what it costs

Tool: `tools/cutmap.py <cu.kicad_pcb> <routed.kicad_pcb> <cu.json> <out> [net] [layer]`. It gives filled area and
piece count per net and layer, before and after routing, and lists the cutting tracks and vias. It also draws a
picture (`runs/cut_*_In2.png`).

- **No-strap routed board (full_v1A3):** In2 PACK_P goes from 1 piece / 1271 mm² to 3 pieces / 884 mm². The
  bottom-left piece (U204 and D103, 114 mm²) is cut off by a nearly horizontal line of gauge-block routes at about
  y 113-118: CELL3, CELL_1N, GAUGE_FUSE, TS1, CELL1, SMBD, PACK, BTP_INT. A small 17 mm² piece is cut off at U101.
  The 10 A Q102 -> J113 path is crossed by long vertical port-1 routes: ACP_F 26.5 mm and ACN_F 25.3 mm inside the
  pour, CHG_INT, U503-FB and REGN. The J113 path resistance goes from 1.48 to 6.5 mΩ.
- **Other power nets after routing:** VBUS, PP5V, PPHV, AC_SNS_N, BAT_SNS_P, CELL_P, CELL_P_RAW, FET_MID, SW1 and SW2
  (both ports) are hard F/B zones. Their area and piece count do not change, and their loss is the same after
  routing, so all stay joined. GND In1/In4 stay 1 piece each (2766 to about 2590 mm², via clearances only). GND F.Cu
  stays at 15 pieces. 3V3 In3 goes from 1 to 3 pieces (5 with straps); that is allowed, 3V3@L201 under 1 A. PACK_P
  F.Cu goes from 8 to 11 pieces (pieces of it are cut where F routes cross).
- **Straps (v1A3S2):** they keep In2 in one piece, but the pour between straps is cut up. PACK_P loss is 0.515 W
  routed, and the J113 path is 3.67 mΩ: a 1.5 mm 0.5 oz strap carries the 10 A. That is the 0.33 W gap: 1.364 vs
  1.034 W, and 0.29 W of it is PACK_P, J113 terminal 0.147 -> 0.367 W. Straps cost about 5 failed edges (43 vs 38 on
  the PC).
- **Cheaper strap forms on In2:** not run. The In4 copy fixes the cause and blocks nothing on the router's layers,
  so narrower or fewer In2 straps could only add cost. The no-strap route cut only the D103/U204 link plus the J113
  path, so a minimum strap set would be 2 links. But the J113 path needs about 0.2 W less resistance than a 1.5 mm
  inner strap can give, so In2 straps cannot reach 1.2 W routed without blocking a wide band of the vertical layer.
- **Keep-out corridor:** the router's `mark_ko` closes a "no tracks" rule area to vias too. So a keep-out costs the
  same router room as a hard strap; rejected for the same reason.

### Copper-only screens (tools/fastcu.sh)

fastcu.sh reuses sc_v1A3's bare board and split spec, adds the bus4 zones, writes the copper, and runs DRC and DC. It
also **injects the same zones into the already routed no-strap board** (stagepwr full_v1A3/routed.kicad_pcb, via
tools/inject_zones.py) and runs DRC and DC there. This is valid for the In4 zones, because the router never sees
In4. For the B.Cu soft fill it is an estimate, because the router would see that fill. Each screen takes about
1-2 min. All rows: DRC 0 before and after.

| bus4 variant (In4 PACK_P) + extra | loss before | routed (injected) loss | routed open |
|---|---|---|---|
| none (stagepwr full_v1A3) | 1.034 | 1.744 | PACK_P D103, U204 |
| copy of the whole In2 pour | 1.057 | 1.265 (GND 0.552) | none |
| strip w=4 (MST bands) | 1.034 | 1.421 | none |
| strip w=6 | 1.033 | 1.308 | none |
| strip w=10 | 1.048 | 1.282 | none |
| copy, box y>104 | 1.032 | 1.282 | none |
| strip w=3 + copy in box x96-122,y100-140 | 1.012 | 1.238 | none |
| strip w=3 + copy in 2 boxes (+ x78-96,y118-140) | 1.029 | 1.261 | none |
| B.Cu soft GND fill only (no In4) | 0.911 | 1.655 | PACK_P D103, U204 |
| copy + B.Cu GND fill | 0.849 | 1.146 | none |
| **strip w=3 + copy box + B.Cu GND fill (= sc_i4b)** | **0.835** | **1.138** (real route: 1.092) | none |

## Part 2: failures outside the ports

Local route of sc_i4b (360/36). The non-port failures left are CELL1 (J109 -> R101) and CELL3 (J111 -> R103), both
"no way" over 50 mm from the top cell connectors to the gauge; P1_LDO_3V3 x2 (U402/R404/R441, port-1 top area, not
mine); and SCL J302.6 -> U301.9. GAUGE_FUSE, DSG, TS1, SMBC/SMBD, VC2, CELL_P, BTST1 and REGN-gauge do **not**
fail any more. They failed only with the In2 straps, so taking the straps out fixed them.

Walls found with stagepwr/tools/dbg.sh on a copy of sc_v1A3 (runs/dbg_base):
- GAUGE_FUSE U101.25 -> R126.2 (blocked in the ghost screen, but routed in the full route). R126 sits in a pocket
  between J112's wire pad, F102 and the board notch. Every courtyard-legal spot near R125/Q104 overlaps U301 (cup
  module), Q104 or the notch (pf.py check). No move made.
- SCL J302.6 -> U301.9 (blocked, ghost and route). The TC2030 pad is closed off to the north by the H103 peg slot
  and by the CELL_P F.Cu pour from F102 to Q101 (y 128-131, x 101-116). A fix would need F102/CELL_P moved or a neck
  in the CELL_P pour. Both change a 10 A path, so this is left as a recommendation and was not screened.
- CELL1/CELL3: long tap nets from the fixed J109/J111 down to the RC filter at U101. Moving R101/R103 only moves the
  long run to the VCx net. No placement fix in my region.

No placement overrides were made, so there is no `overrides_gu.json`: the best board uses the v1 placement unchanged.

## PC routes (Logan's PC)

| name | board | routed | failed | total | minutes | status |
|---|---|---|---|---|---|---|
| strapfix-i4b | runs/sc_i4b | **358** | **38** | 396 | 53.5 | done |

## Rejected tries
- In2 strap variants: see Part 1. They cost router room on the vertical layer and cannot carry 10 A at 0.5 oz.
- In4 copy of the whole pour: loses too much In4 GND (GND 0.454 W before routing).
- Narrow In4 strips (w=4-6): PACK_P stays high after routing.
- B.Cu GND fill without In4 PACK_P: PACK_P still opens.
- A first batch run broke (`unexpected EOF`) because I edited fastcu.sh while it ran; that row was re-run.

## Skill notes (for a cheaper model)
1. After a full route, always run `stagepwr/tools/routed_dc.sh <outdir>`. A route count is only good if
   power_open on routed.kicad_pcb is the allowed set.
2. To see why a pour opened: `tools/cutmap.py cu.kicad_pcb routed.kicad_pcb cu.json out PACK_P In2.Cu`, then Read
   out_In2.png (red = cutting tracks, blue = cutting vias, numbered pieces).
3. The router (tools/score/router.py) routes only on F, In2 (vertical), In3 (horizontal) and B. Copper on In1/In4
   can be pierced by vias but never cut by tracks, and it costs the router nothing. Put a second copy of any bus that
   the router cuts on In4, with priority above the GND plane (`tools/bus4.py`).
4. Taking In4 area from GND costs GND loss. Win it back with a soft GND fill on B.Cu (`bus4.py --net=GND
   --layer=B.Cu --mode=fill --prio=0 --soft=1`): 2 oz outer copper, and the router may cut it (GND is a softnet).
5. Screen copper ideas in about 1 min with `tools/fastcu.sh <base outdir> <new> "<bus4 opts>" "" <routed outdir>`.
   It also injects the zones into an existing routed board, which is exact for In1/In4 zones.
6. Then run the full scorecard copy `tools/score_sf.sh` with env PLANNER / BUS4 / BUS4B (hot on, --route=0). Check
   blocked, DRC, 7/7. Queue on the PC, and run one local `router.py ... --riptime=600` (the scorecard's 45-min route
   is killed before it saves).
Traps: never edit a script while a loop that calls it is running. The router's `mark_ko` treats a "no tracks" rule
area as closed to vias too. Inner layers are 0.5 oz (17.5 µm) and outer 2 oz: a 1.5 mm inner strap is about
1 mΩ per 3 mm at 10 A. KiCad keeps only the first outline of a multi-outline zone, so bus4 writes one zone per
polygon.
