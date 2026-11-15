# Worker "rebuild" (team A, round 1): notes

All numbers are from `tools/score/score_board.sh` (blocked-edge screen = `--route=0 --no-hot`, best variant also with hot loops).
Blocked edges are split by `tools/blocked.py` into stage (charger power stage: Q4xx/Q5xx/TH GND, gate drive, FSW,
ACOV, R429 PACK_P), p1 / p2 (port top blocks: PD chip, port protector, EEPROM, pull-ups, connector) and other.

## Part 1: one-command rebuild

`rebuild.sh <workdir> [--exact] [--gu=DIR] [--score[=ARGS]] [--no-keepv]`

1. dumps `tools/score/template/board.kicad_pcb` with `gu/dump.py` in the KiCad container to `<workdir>/base.json`
   (the committed `groundup/base.json` is not used; the fresh dump has the same 289 footprints with identical
   position, rotation, pad nets and courtyard boxes; only the zone list differs: 16 zones in the template
   against 1252 in the committed dump of the routed board, and the placer does not read zones);
2. runs the groundup placer (`run.py place_keep.py,place_p1top.py,place_centre.py,place_p1stage.py,place_p2top.py,place_bot.py`,
   two passes, `GAP=0.25 RING=0.4 GAPB=0.1 RINGB=0.3`) on copies of the scripts in `gu/`: 1 min 45 s;
3. converts to the scorecard format with `gu/gu_to_score.py` (`new_rot = template_rot - ang`);
4. optionally runs the scorecard.

Reproduction of `tools/battery-bank/groundup/placement.json` (`gu/cmp_place.py`), placelib.check(): 0 courtyard /
edge / peg errors, 289 of 289 placed.

| Run | Parts that differ from the committed placement.json | Why |
|---|---|---|
| plain rebuild (`runs/base_build`) | C301, C549 | C301 is a fixed part: the template has it at y 116.078, the committed json at 115.958 (the routed board moved it 0.12 mm). C549: the placer puts it at (84.6, 75.2); the committed json has (80.2, 86.0), a later hand edit that lies outside the placer's own lip limit (courtyard x 79.25 < 79.4). |
| `--exact` (`runs/exact_build`) | C301 only | `gu/post_edits.json` applies the C549 hand edit after the placer. C301 stays at the template position (fixed part). |

The C430/C438/C530/C538 edits of the first fix pass are already in the committed place scripts (no difference).

Scores of the rebuilt base:

| Run | Blocked edges | stage / p1 / p2 / other | DRC | power_open | Loss |
|---|---|---|---|---|---|
| lead baseline (committed json, incl. C301 -0.12) | 65 of 441 | 19 / 24 / 20 / 2 | 0 | GND@Q401,Q501 + allowed | 1.064 W |
| `--exact` rebuild (`runs/exact_score`) | 65 of 441 (same 65 edges) | 19 / 24 / 20 / 2 | 0 | GND@Q401,Q501 + allowed | 1.065 W |
| plain rebuild (`runs/base_score`, C549 at the placer's spot) | 70 of 443 | 19 / 25 / 24 / 2 | 0 | GND@Q401,Q501 + allowed | 1.065 W |
| hand placement (`runs/hand_score`, reference) | 56 of 452 | 18 / 18 / 14 / 6 | 0 | PP5V@U401 + allowed | 1.36 W |

**keep_vias.json** (56 via spots of the hand copper that the greedy placer must not cover) is a hand-copper artefact.
Without it (`--no-keepv`) the placer **fails**: `RuntimeError: Q103: no free spot near (98.6, 125.6)` in
place_bot.py. The parts placed before it take other spots and the gauge corner runs out of room. So it is a de facto
placement input; keep it until the bottom block is re-planned.

**TPs**: groundup's place_bot.py moves TP412, TP512, TP106, TP109, TP113, TP301 away from the template. I left those
moves as they are (they are in the stage-free bottom/centre and the baseline has DRC 0); not tested at template spots.

## Part 2: support-part placement round the PD chips and ports

The charger stage (place.py, place_p1stage.py) is untouched in every variant; only place_p1top.py and place_p2top.py
changed. The changed parts in the best variant v5 (48 of 289, all port-top-block support parts):
C401-C408, C439, C441-C443, C449-C452, D401, R402-R404, R424-R426, R432, R433, R441, R455, U401, U402 (port 1);
C503-C508, C549-C551, R502-R504, R524-R526, R541, R555, U501, U502 (port 2).

### Variant table (all DRC 0)

| Variant | What moved | Blocked | stage / p1 / p2 / other | power_open | Loss | PC route |
|---|---|---|---|---|---|---|
| exact base | groundup as committed | 65 of 441 | 19 / 24 / 20 / 2 | GND@Q401,Q501 (stage) + allowed | 1.065 W | rebuild-base: 378 of 441 routed, 63 failed, **timed out at 60 min** |
| v1 | U401 rot -90 -> 0 at (105.1, 81.0); caps in front of its pins | 66 of 439 | 19 / 24 / 21 / 2 | **+PP5V@U401 (new open)** | 1.090 W | |
| v2 | v1 + D401 to J401's east VBUS pins, CC caps beside U405, C407 at pin 34, R424 east of pad 20, C449 between them | 62 of 440 | 18 / 21 / 21 / 2 | stage + allowed | 1.103 W | |
| v3 | v2 + C407 0.4 mm east (pins 36/37 free), C403 NW, kelvin filters at R424's two ends, C408 under pins 12-14 (port 2 C549 at the placer's spot, not --exact) | 61 of 449 | 19 / 16 / 24 / 2 | stage + allowed | 1.045 W | |
| v4 | v3 + C405 GND pad 1.4 mm from pin 7, EEPROM U402 rot 90 under pins 13-17, pull-ups beside it (--exact for port 2) | 58 of 443 | 18 / 17 / 21 / 2 | stage + allowed | 1.080 W | rebuild-v4: 368 of 443 routed, 66 failed, **timed out at 60 min** |
| **v5 (best)** | v4 + port 2 the same way: U501 rot 0 at (84.1, 81.0), C550/C549 at pads 23/20, R524 below pad 20, C506 on the VBUS path below D501, C507 at pin 34, LDO caps NW / W, EEPROM and pull-ups under the south row | **55 of 436** | 18 / 16 / 19 / 2 | stage + allowed | **1.071 W** | rebuild-v5: 373 of 436 routed, 61 failed, **timed out at 60 min** |
| v6 | v5 + port 2 R524 1.2 mm lower, EEPROM / pull-ups 2 mm further from the pins | 57 of 438 | 19 / 16 / 20 / 2 | stage + allowed | 1.053 W | |

Non-stage blocked edges: 46 (base) -> 37 (v5). Target was under 30: **not reached**.

v5 with hot loops on (`runs/v5_hot`, `--route=0`): 55 of 436 blocked, DRC 0, loss 1.071 W, **5 of 7 hot loops pass
tier 1, 5.47 nH** (HL_3V3 1.54, P1 HL_5V 0.66, P1 HL_OUT 1.08, P2 HL_5V 0.89, P2 HL_OUT 1.30 nH). Port 1 and port 2
HL_IN fail "no closed loop through the first capacitor C430 / C530": the charger-stage GND open at Q401/Q501 that
worker 'stage' owns (expected, not touched here). Both 5 V buck loops pass (port 2 HL_5V parts did not move).

Renders checked (`runs/v5_hot/F.png`, `B.png`): both PD chips sit 9-10 mm below their USB-C connector, with
the port protector between; decoupling, EEPROM and pull-ups within 6 mm of their pins; nothing sprawled. D401 (port 1 VBUS
TVS) sits at the connector's east VBUS pins, top right (114.55, 67.05), 5.6 mm from VBUS A4. Copper side effects
visible: the port 2 PPHV planner track runs down the west board edge to C509 (also in the baseline), and the PP5V
of both ports now crosses the VBUS stem on B.Cu (planner detour).

### Full routes on Logan's PC

Queued (commit + push via queue_route.sh): rebuild-base (from runs/exact_score) at 14:51 UTC,
rebuild-v5 (runs/v5_score) and rebuild-v4 (runs/v4_score) at 16:12 UTC.
- rebuild-base (`A/rebuild-base-46ae854a.json`, arrived 16:26 UTC, 95 min after queueing): **378 routed, 63 failed of
  441 edges, status "timed out at 60 min"** (the PC's cap is 60 min, one thread). For comparison: hand placement
  391 of 448 in 18 min (charter).
- At 16:21 UTC (90 min after the first queue, before that result came) nothing had come back, so the fallback local
  `--route=45` for v5 was tried; the session's permission check **refused** it, so it did not run.
- rebuild-v5 (`A/rebuild-v5-be91c270.json`, arrived ~17:10 UTC): **373 routed, 61 failed of 436, timed out at 60.1 min**.
- rebuild-v4 (`A/rebuild-v4-09827553.json`): **368 routed, 66 failed of 443, timed out at 60.1 min**.
- Reading: all three routes hit the 60 min cap, so none is a finished route. v5 leaves 2 fewer edges failed than the
  base (61 vs 63) with 10 fewer blocked edges in the screen (55 vs 65), but it also routed 5 fewer edges (the edge
  total is 5 lower). That is no clear full-route gain, and all three are below the hand placement (391 of 448 in
  18 min). The blocked-edge screen improved more than the timed-out route shows.

### Remaining blocked edges in v5 (non-stage) and what walls each in

Port 1 (16):
- U405.4->U405.7 (C_CC1), U405.5->J401.B5 (C_CC2), J401.A5->U405.4 (C_CC1), C451.1->U405.3 (VBIAS): J401's west
  VBUS pins (A9/B4 at x 104.1) get a planner via stub straight down to y ~70.6; its clearance covers U405's north
  pins 3-5 (x 103.5-104.3, router `dbg` dump: F.Cu cell (103.9, 70.8) = VBUS). A5 is also sealed by the east VBUS
  stem, which is within NEAR_TERM_MM (1 mm) of its own terminal pad A4 and so keeps only clearance from A5. The H104 peg
  (R 2.2 mm) stops U405 from moving east of the stub. Same in the hand placement.
- U401.37 DRV9_OFF (2 edges): the PP5V pour round pin 34 (terminal, so no escape room within 1 mm) and the 3V3 pour
  round C403 close the north exit of pins 36-38.
- U401.36, U401.31 GND: pin 36 as above; pin 31 between PD_DRAIN (30) and the small VBUS pin 32, which gets its own
  little VBUS pour piece; no via site.
- SDA/SCL/IRQ at U401.8/9/10 (6 edges): the planner's `return_join` for GND pins 7 and 14 (no via fits at a
  0.4 mm pin) runs a track to the nearest **GND zone piece that holds a via** (here port 2's HL_5V return pour at
  x ~99), up to 6 mm, straight under pins 8-10. A part's GND pad with a via does not count: only zone pieces do.
- R402.2 I2CC_SDA -> U403.2 (charger), R441.1/R404.1 P1_LDO_3V3: the EEPROM block under the south row; the long
  edges to the charger cross the stage.
- J401.A1 GND: connector GND pad next to the east VBUS stem.

Port 2 (19): U505 C_CC1/C_CC2/VBIAS (4, same cause as port 1, with J501's east VBUS pins at x 95.9), U505.11/12 CC
-> U501.28/29 (2: the VBUS stem from J501 to pad 23 lies between U505 and U501's north row; no via site in the
2 mm strip), U505.9 SBU_FLT -> U501.19 (1), U501.16/17/18/19 I2CC / CHG_INT / SBU_FLT to U502 and the pull-ups (6) and
on to U503 (2): the port 2 **PPHV planner track to C509** (stage cap at U503) runs west straight under the south pin
row (y ~84.3) and down the board edge; U501.7, 31, 36 GND (3: as port 1), IRQ_N U501.10 -> Q103 (1),
CHG_INH R535 -> J302 (1, R535 is a stage part).

Other (2, unchanged from base): SCL J302.6 -> U301.9, GAUGE_FUSE U101.25 -> R126.2.

### What worked
- Turning both PD chips from rot -90 to rot 0 (the hand orientation) so the big VBUS (23) and PPHV (20) pads face
  east: the VBUS copper no longer runs from the connector down a whole pin column to a pad on the far side.
  Port 1 block 24 -> 16 blocked edges, port 2 20 -> 19, VBUS port 1 loss 83 -> 35 mW.
- Putting the PPHV sense resistor right beside pad 20 so PPHV leaves the chip away from the pin rows, and C549 /
  C449 between pad 20 and R424/R524 (not west of the sense resistor: in the baseline C549 west of R524 pulled the
  PPHV pour under pins 16-19 of U501).
- Moving the port 1 VBUS TVS D401 to the connector's east VBUS pins.

### What did not work
- More free room in front of a pin row (v6): the planner's `--grow 1.5` fills any free space within 1.5 mm of
  power copper and keeps only 0.4 mm escape room, so a bigger pocket next to a power track just becomes power copper.
  57 vs 55.
- Putting CC caps directly in front of the CC pins (v1): they sit between the PP5V and VBUS pours and get boxed.
- Without keep_vias.json the placer fails (above).

### Traps for the skill notes
- `rebuild.sh --exact` reproduces the committed placement; do not combine `--exact` with a variant that places
  C549 itself (the post edit moves it back).
- A pin within NEAR_TERM_MM (1.0 mm) of a pad of a power net's terminal gets no escape room from that net's pour:
  the neighbours of a fine-pitch power pin (PP5V pin 34, VBUS pins of USB-C) are walled unless they have a via
  site inside the clearance strip. Plan those neighbours' exits on the side away from the pour.
- Only pads that are at least 3x the IC's median pad area become terminals (TPS25751 pad 23 VBUS, not pin 32);
  `pin_pads` in constraints.json makes U401.34 a PP5V terminal.
- GND pins of a 0.4 mm QFN rarely get their own via (the 0.3 mm via link fails next to a signal pin); they join the
  nearest **GND zone piece with a via** by a track of up to 6 mm, and that track crosses the neighbouring pins'
  exits. Know where the nearest GND pour is before placing the I2C pins' side.
- The planner's PPHV (and other power) nets connect every shunt cap terminal, even a 0.1 uF cap at the charger IC
  25 mm away (C509): port 2's path ran along the board edge and under the PD chip's pin row.
- Router ghost: a "noway" edge is truly enclosed (the router also gives up after a 5000-node look from the far end
  only when the far end is boxed). `tools/router_dbg.py --ghostonly --only=<net regex> --dbgbox=x0,y0,x1,y1
  --dbgnet=<net> --dbgpts='x:y;...'` (run on a scorecard outdir, in the KiCad container, ~3 s) draws the free
  cells of one net per router layer and prints which net's copper fills given points: it found the VBUS via stub.
- The scorecard's edge count changes with the placement (436-452), so compare blocked counts, not ratios.
- Loss moves with C549 position at port 2 (1.045 vs 1.080 W in v3/v4): check loss after every port-2 change.

### Files
- `rebuild.sh`, `gu/` (copied groundup scripts + `gu_to_score.py`, `cmp_place.py`, `post_edits.json`),
  `variants/v1..v6/` (changed place scripts only; `rebuild.sh <dir> --gu=variants/v5` builds the best).
- `base_placement.json` (scorecard format) / `base_placement_gu.json` (groundup format): the `--exact` rebuild.
- `best_placement.json` / `best_placement_gu.json`: v5.
- `runs/<name>_score/`: scorecard outdirs (score.json, F.png, B.png, ghost.log, plan.log, dc.json);
  `runs/v5_hot/` v5 with hot loops; `runs/exact_score/` the rebuilt base; `runs/hand_score/` hand reference.
- `tools/blocked.py` (blocked edges by area), `tools/zoom.py` (copper window with pad numbers and blocked pads),
  `tools/showp.py` (placement picture from a build dir), `tools/router_dbg.py` (router copy with the ghost debug dump).
