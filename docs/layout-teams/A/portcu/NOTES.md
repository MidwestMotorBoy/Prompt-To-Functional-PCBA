# Worker `portcu` (team A, round 3): planner rules for the port-top copper walls

All numbers are split-zone copper: quick screens from `tools/quick.sh` (ports quick.sh + split_spec, planner =
`tools/plan_copper_p.py`), candidates from `tools/score_board_split_p.sh` (stagepwr's score_board_split_a.sh copy,
PLANNER defaults to plan_copper_p.py). "allowed only" = power_open is 3V3@L201 and GND@J301/J302 only.

Base placement (not moved): `stagepwr/best_gu.json` + the 6 ports b1 overrides (`ports/best_overrides_gu.json`:
U502 C508 R541 R504 R502 R503) = `portcu/base_gu.json` / `base_score.json` (pf.check: no errors). No portcu
placement overrides were needed: every gain below is copper only.

## Result

Best board = **G5**: base placement + planner options (`best_plan_opts.txt`)

    --sealed=1 --taps=1 --joinfix=1 --epstrip=1 --directjoin=1 --nogrow_dead=1 --gndesc=1 --connesc=1
    --pinesc=1 --pinesc_refs=U501 --pinesc_near=1 --gndpair=1

| board | blocked (stage/p1/p2/other) | power_open | DRC | hot loops | loss | outdir |
|---|---|---|---|---|---|---|
| base, planner A (`--sealed=1 --taps=1`), screen | 24 of 396 (0/13/9/2) | allowed only | 0 | | 1.035 W | runs/q_A |
| base, A + joinfix, screen | 19 of 398 (0/8/9/2) | allowed only | 0 | | 1.035 W | runs/q_AJ |
| candidate E (A + joinfix + epstrip + directjoin + nogrow_dead + gndesc), scorecard | 9 of 371 (0/2/5/2) | allowed only | 0 | 7 of 7 tier 1, 6.23 nH | 1.034 W | runs/sc_E |
| **candidate G5 (E + connesc + pinesc U501 near + gndpair), scorecard** | **5 of 369 (0/1/2/2)** | allowed only | 0 | **7 of 7 tier 1, 6.23 nH** | 1.035 W | **runs/sc_G5** |
| candidate G5S (G5 + stagepwr PACK_P In2 straps), scorecard | 5 of 372 (0/1/1/3) | allowed only | 0 | 7 of 7 tier 1, 6.23 nH | 1.035 W | runs/sc_G5S |

Port blocks (p1 + p2) went from 22 (planner A) / 17 (A + joinfix) to **3** on G5; of those 3, two are stage-side
parts (R402 I2CC_SDA -> U403.2, R535 CHG_INH -> J302) and one is U501.37 DRV9_OFF -> Q509 (20 mm route to the
centre; see "Left").

PC full routes (split copper): **G5 353 routed / 16 failed of 369** (104.2 min, done), against 363/37 of 400 for
stagepwr v1 stock and 364/36 of 400 for ports b1 on the same placement: 20 fewer failures.

## Renders (runs/sc_G5/F.png, B.png, read)
- F: the same compact port tops as b1: USB-C, protector U405/U505 under it, PD chip U401/U501 ~10 mm below with the
  VBUS stem to pad 23, PPHV east to the sense resistor, buck U404/U504 + inductor beside the chip, PP5V caps in line.
  New copper is tiny: 0.15-0.2 mm GND strips from PD-chip pins into pad 39, pin-pair GND links, a 0.3 mm PP5V track
  from pin 34 to C407/C507. The connector's A9/B4 VBUS pad pair is no longer grown into a blob over the protector.
  No pour cut into islands, no new long detours; charger stages unchanged.
- B: port 1 unchanged; port 2's thin B.Cu VBUS copy along the stem is gone and its PP5V detour blob sits further
  north (the via sites at U501.28-30 pushed it), still a short blob between C507 and C541. PACK_P / AC_SNS_N /
  BAT_SNS_P stitching under the stages as before. G5S differs only on In2 (straps); F/B renders are the same.

Placement files: `best_gu.json` / `best_score.json` (= base, no portcu overrides), options in `best_plan_opts.txt`.

## Rules (all in `tools/plan_copper_p.py`, each behind its own option, 0 = stock behaviour)

The planner subclasses stagepwr's `plan_copper_a.PlannerA` (gate escapes, `--sealed`, `--taps`), which imports the
stock `tools/copper/plan_copper.py` unchanged. Every number is a quick screen on the base placement, each rule
added on top of the accepted stack before it.

| # | option | what it does | screen before -> after | verdict |
|---|---|---|---|---|
| 0 | `--joinfix=1` | ports' fix: `return_join` keeps the signal escape room (`tight=False`) | 24/396 -> 19/398 (p1 13 -> 8: U401 SDA/SCL/IRQ x5 freed) | keep |
| 1 | `--epstrip=1` | a GND pin of an IC (12+ pads, pin <= 0.45 mm wide, <= 0.8 mm from the EP) whose own exposed pad is GND gets a straight F.Cu track (0.2 mm, else 0.15 mm) into the EP, else an L (along the pin axis, then into the EP), else a 0.15 mm track to a served same-net neighbour pin; drawn before any power copper, other nets keep the clearance from it, and the pin is then skipped by the return step | 19/398 -> 15/374 (U401/U501 .31/.36 GND x4 freed; edge total drops because the GND pins are now joined) | keep |
| 5 | `--directjoin=1` | a power terminal left "no path" gets a straight track (0.5/0.3/0.2 mm) to its net's copper on that layer within 2 mm | 15/374 -> 15/373: U401.34 / U501.34 PP5V now joined to C407/C507 by a 0.3 mm track (the PP5V router edge is gone; it was a PC route failure); also P1 PPHV U403 by a 0.5 mm track | keep |
| 3 | `--nogrow_dead=1` | the grow step does not grow a dead pour piece (< 3 mm2, no via, no track, only connector pads): the USB-C connector's second VBUS pin pair A9/B4 is seeded as a pad-only piece; grown 1.5 mm it lay over the protector's CC pins | 15/373 -> 10/373 (U405 C_CC1 x2, C_CC2, VBIAS and U505 C_CC1 x2 freed) | keep |
| 4b | `--nogrow_detour=1` | do not grow a pour that is only a detour corridor (B.Cu PP5V / SW2 detours) | 15/373 -> 15/373, loss 1.034 -> 1.082 W; with nogrow_dead: 10 -> 10, 1.083 W | **reject** (no gain, +0.05 W) |
| 3b | `--mirror_minw=0.5` | drop mirror pieces thinner than 0.5 mm (2 x area / perimeter) with their stitching vias (the B.Cu copy of the VBUS stem, ~0.4 mm wide) | 10/373 -> 10/373, loss 1.034 -> 1.032 W | neutral, not in the stack (0.6 tried with pinesc: no change) |
| 1b | `--gndesc=1` | GND pins of connectors and of ICs with 8+ pads (pads <= 0.65 mm, not EP-strip-served) keep the signal escape room from foreign power copper | 10/373 -> 9/371 (J401.A1/B12 GND gets a via) | keep |
| 4 | `--pinesc=1 --pinesc_refs=U401,U501` | escape reservation at every signal pin of the PD chips: pin-width strip 0.9 mm out of the package + via site (via + 0.2 mm) at its end, kept on both outer layers (overrides the NEAR_TERM_MM exemption) | (on stack without gndesc) 10/373 -> 13/378: U501 CC1/CC2 freed, but U401/U501 GND .26/.27 lost their via sites | reject as is |
| 3c | `--connesc=1` | each connector signal pad (<= 0.35 mm wide) keeps a 0.4 mm wide strip 1.0 mm straight out of the connector (0.2 mm track + the 0.25 mm HighCurrent-to-signal rule), so a pour wrapped under the pad row cannot seal it | 9/371 -> 7/371 (J401.A5 C_CC1 and J501.B5 C_CC2 freed) | keep |
| 4' | `--pinesc=1 --pinesc_refs=U501 --pinesc_near=1` | as 4, only for signal pins within NEAR_TERM_MM of a foreign power pad of the same IC (U501 .1 .17-.19 .28-.30 .37) | 7/371 -> 7/373: CC1/CC2 freed, U501.26/27 GND lost (len 0.6/via 0.15, len 1.4, mirror_minw 0.6 all the same) | needs 1c |
| 1c | `--gndpair=1` | two neighbouring GND pins of one IC (<= 0.55 mm apart) are joined pin to pin by a pin-width track, so one via serves both (U501.27 had lost its via site to pin 28's reservation; .26 still had an in-pad via) | with 4': 7/373 -> **5/369** | keep |
| 4' on U401 too | `--pinesc_refs=U401,U501` | | 5/369 -> 7/371 (two GND pin-pair tracks at U401 left floating) | reject |
| 4c | `--grow_viaroom=1.0` | grown copper keeps 1 mm from fine-pitch IC signal pins on the other outer layer | 5/369 -> 5/369, same loss | reject (no gain; DRV9_OFF still blocked) |

The full try log (every screen, with options, blocked split, DRC, loss and opens) is `runs/log.txt`.

## What walled each port edge (traced with dbg.sh / zoom.py / roomdbg.py)
- **U401/U501 GND .31/.36** (rule 1): 0.4 mm pitch, no via fits and GND pins had no escape ring; but each sits
  0.3 mm from the chip's own GND EP (pad 39). Pin 31's straight strip ran into the EP's rounded corner next to the
  VBUS pad 32, so an L (down the pin axis, then into the EP, 0.15 mm) is needed there.
- **U401 SDA/SCL/IRQ** (rule 0): the tight return join of pins 7/14 under pins 8-13. With epstrip on, pins 7, 11-14
  get EP strips and no return_join is drawn at all.
- **U405/U505 C_CC / VBIAS** (rule 3): the planner seeds the J401 VBUS terminal with both VBUS pin pairs; the A9/B4
  pair is a separate pad-only piece (it carries nothing: it is not joined on the board) that the grow step turned
  into a 1.5 mm blob over U405 pins 3-5 and under B5. Not growing it freed 6 edges.
- **J401.A5 / J501.B5** (rule 3c): the VBUS tree pour from A4/B9 wraps round under the pad row; the 0.4 mm escape
  room keeps the pad free, but the track leaving it needs 0.25 mm from a HighCurrent zone, and the pour sat
  0.325 mm from the pad's exit.
- **U501 CC1/CC2 .28/.29** (rules 4' + 1c): pin 28 is 0.98 mm from VBUS pad 23 (inside NEAR_TERM_MM, no escape room);
  the VBUS stem (F) and the B.Cu PP5V detour left no via site above the pin row. The via-site reservation fixes it;
  the PP5V detour then moves and the VBUS mirror's stitching vias take pin 27's GND via site, which gndpair repairs.
- **J401.A1/B12 GND** (rule 1b): boxed in by the A4/B9 VBUS pad and the VBUS pour (GND pads had only the clearance).

## Left
- U501.37 DRV9_OFF -> Q509 (101.2, 97.3): a 20 mm edge; near pin 37 / R555.2 there is F-only room and no via site
  (yellow/salmon in dbg). Not fixed by nogrow_detour, grow_viaroom or pinesc. Port 1's copy routes.
- R402.2 I2CC_SDA -> U403.2 and R535 CHG_INH -> J302: stage-side parts (stagepwr's area), not touched.
- other: J302.6 SCL -> U301.9, U101.25 GAUGE_FUSE -> R126 (not port parts).
- Electrical note (not new, also on the stock planner): the connector's second VBUS pin pair (A9/B4 on J401,
  A4/B9 on J501) is not joined to VBUS on the board; the plug commons them, so all 5 A enters through one pin pair.
  dc_score does not flag it. A planner rule to stitch that pair to the tree (B.Cu strap) would cost B.Cu room
  next to the CC pins; left for the lead to decide.

## Full routes on Logan's PC
All three were queued from `score_board_split_p.sh` outdirs (split copper) with `queue_route.sh`; all finished
("done"), none hit a cap. Results from branch route-results (`A/<name>-<sha>.json` / `.log`).

| name | board | queued (UTC) | routed | failed | edges | minutes | status |
|---|---|---|---|---|---|---|---|
| portcu-E (`A/portcu-E-b6c9fbfc.json`) | runs/sc_E | 04:18 | 351 | 20 | 371 | 106.7 | done (arrived ~06:08, 110 min after queueing) |
| **portcu-G5** (`A/portcu-G5-155c0266.json`) | **runs/sc_G5** | 05:07 | **353** | **16** | 369 | 104.2 | done (arrived ~06:55) |
| portcu-G5S (`A/portcu-G5S-1a82e7bd.json`) | runs/sc_G5S (G5 + PACK_P straps) | 05:25 | 353 | 18 | 371 | 86.0 | done |

References on the same placement family (split): stagepwr-v1-stock 363/37 of 400, stagepwr-v1A3 358/38 of 396,
ports-b1 364/36 of 400, hand 363/59 of 422. Routed counts are lower than b1's because the edge total dropped
(GND pins and the PP5V pin now joined by planner copper); the failures dropped from 36-38 to 16.

FAILKEYs:
- E (20): P1 REGN x4 (stage), P2 HIDRV1, U401.27 GND (isolated: fixed by gndpair in G5), P1 C_CC1 J401.A5 (fixed
  by connesc in G5), P1 CC1 U401.28 (congestion), P2 CC1 U501.28 (fixed by pinesc in G5), P2 C_CC2, P1 PP5V
  (R433.1 -> PP5V pour, goals 0), P1/P2 I2CC_SDA, P1 I2CC_SCL, P1 CHG_INT, P1 SBU_FLT, P1_LDO_3V3, SCL, CELL1, CELL3.
- **G5 (16)**: port 1: CHG_INT x2, I2CC_SCL, SBU_FLT, CC1, PP5V (R433.1), P1_LDO_3V3; port 2: I2CC_SDA; SCL;
  stage: P1 BTST1 x2, P1 LODRV2, P1 HG1, P2 HIDRV1; gauge: TS1, CELL3. No GND, CC2/C_CC or U501 CC failures left.
- G5S (18): the straps move the stage/gauge failures around (U101 SMBD/SMBC/PACK/VC3, HIDRV1/2, PPHV, SS_5V ...);
  port failures about the same as G5. Straps cost 2 edges here (stagepwr saw 3-6).
- Not checked: power_open on the routed boards (the routed .kicad_pcb stays on the PC). stagepwr showed that In2
  signal routes can cut the soft PACK_P In2 pour without straps; G5S is the variant that keeps PACK_P joined.
  P1 PP5V's remaining failure is R433.1 (a 3 mm pull-up stub to the pour), not the U401.34 power pin (joined by
  --directjoin now). G5S also fails one P1 PPHV edge.
- No local full route was run.

## Tools
- `tools/plan_copper_p.py`: the planner (subclass of stagepwr PlannerA; options above).
- `tools/quick.sh`: quick screen (apply, plan, split, write, DRC, DC, ghost blocked count, zooms) with PLANNER =
  plan_copper_p.py by default. `tools/q.sh <name> <planner opts>`: quick screen of base_score.json (or $PL) into
  runs/q_<name>, one log line into runs/log.txt.
- `tools/score_board_split_p.sh`: scorecard copy (stagepwr's score_board_split_a.sh, PLANNER defaults to
  plan_copper_p.py; STRAPS env as stagepwr).
- `tools/roomdbg.py <bare.json> x,y <planner opts>`: room grid on F/B round a GND pad when the return step looks
  for its via, the via it took, and other nets' copper near (found the VBUS mirror vias that took U501.27's site).
- `tools/poll.sh <name>...`: background poll of route_result.sh into runs/route_<name>.json.

## Skill notes (for a cheaper model)
1. Build the placement with `onecmd/apply_overrides.py` and check it with `ports/tools/pf.py` `check()` (must be []);
   convert with `rebuild/gu/gu_to_score.py <gu> <score> rebuild/runs/v5_build/base.json`.
2. Screen the base planner first (`tools/q.sh A --sealed=1 --taps=1`), then add ONE option per screen. Diff the
   GHOSTFAIL lists (`diff <(grep -o 'GHOSTFAIL.*' runs/q_X/ghost.log|sort) <(...q_Y...)`) rather than only counts:
   a rule often frees two edges and blocks two others.
3. For each blocked port pad: `bash ports/tools/dbg.sh <outdir> '<net>' x0,y0,x1,y1 out.png 'x:y;...' '<net>'`,
   Read `out_ov.png` (white = via possible, red/salmon = F only, green = B only, yellow = F+B but no via, magenta =
   end cells); the `dbg at` lines name the net that owns each router cell on F/In2/In3/B. Then look at the spec
   (`spec.json` zones/tracks/vias near the point) to see which planner step drew that copper (zone `kinds`).
4. Put a new rule in the planner subclass behind its own option; test the planner alone on an existing
   `bare.json` first (`python3 tools/plan_copper_p.py bare.json constraints.json /tmp/x.json <opts>`, 1 min) and
   diff its `left to router` / `left_to_router` / `hot loops` lines against the previous stack before screening.
5. A candidate (>= 4 edges better): `tools/score_board_split_p.sh runs/sc_X base_score.json --route=0
   --plan="<opts>"` (hot loops on, ~12 min), check 7/7 tier 1 and power_open, Read F.png/B.png, then
   `queue_route.sh runs/sc_X portcu-X`, and poll in the background (`tools/poll.sh`).

Traps:
- A pad-only piece of a pour is grown like any copper: the connector's unused VBUS pin pair became a blob over the
  protector. Check what the grow step grows (zone pieces with no via and no track).
- A reservation that frees signal pins moves the detours of other nets, which then take GND via sites a few pins
  away: always diff the full GHOSTFAIL list and check GND pins of the same IC.
- An EP strip from the pin centre to the nearest EP point can run diagonally into the neighbouring power pad when
  the EP has rounded corners: try the pin axis first (L shape).
- Connector pads need more than the planner's 0.4 mm escape room for a track to leave: the HighCurrent-to-signal
  rule is 0.25 mm (vs 0.15 mm clearance), so reserve a straight exit strip.
- Zero-length tracks: connector pads with two names at one spot (A1/B12) look like neighbour pins; skip pairs under
  0.05 mm apart.
- Edge totals change with every copper rule (396 -> 369): report failed and total, compare failed counts.
- Do not edit a planner file while a screen that imports it is starting (python reads it at start; edits between
  runs are fine).
