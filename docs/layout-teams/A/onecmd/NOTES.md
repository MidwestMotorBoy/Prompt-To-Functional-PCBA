# Worker `onecmd` (team A, round 2): one command from the bare template, rules instead of typed coordinates

All scores are from `docs/layout-teams/A/tools/score_board_split.sh` (split-zone copper). No full route was run or
queued (see 2). Reference split screen of merged3: `ports/runs/m3` = 31 of 400 blocked, 1.053 W, allowed opens only.

## 1. build.sh: bare template -> merged3, exactly

```
docs/layout-teams/A/onecmd/build.sh <workdir> [--score[="ARGS"]] [--overrides=DIR] [--ref=GU.json]
```
Example: `docs/layout-teams/A/onecmd/build.sh docs/layout-teams/A/onecmd/runs/m3`. It takes **116 s** (1 s KiCad dump,
about 105 s groundup placer, about 8 s stage template; the screen is extra).

Steps:
1. `gu/dump.py` dumps `tools/score/template/board.kicad_pcb` in the kicad/kicad:10.0 container and writes `base.json`.
2. The groundup placer (`gu/run.py`, two passes, GAP=0.25 RING=0.4 GAPB=0.1 RINGB=0.3) runs with the rebuild v5
   port scripts (`gu/place_p1top.py`, `gu/place_p2top.py`) and writes `v5_gu.json`. This is identical to
   `rebuild/best_placement_gu.json` (0 parts differ).
3. `stage/apply_stage.py` (a copy; `STAGE_WD` selects the build dir) applies `stage/stage_template.json` (B4) to
   both ports and writes `stage_gu.json`. It evicts and re-places 8 parts: D404, D410, D504, D510, C410, C510,
   R416, R516.
4. Every `overrides/*.json` is applied in name order and gives `placement_gu.json`. The two files now are
   `10_stagefix_s3.json` (R432, R433, C420) and `20_pdfix_a3.json` (11 port parts).
5. `gu_to_score.py` writes the scorecard format to `placement.json`.
6. `check.py` runs the placelib check (exits 1 on any error), then the build is compared with `--ref` (default
   `lead_merge/merged3_gu.json`).

**Diff against lead_merge/merged3_gu.json: 0 of 289 parts differ.** C301 matches too (both keep the template pose).
The scorecard format matches `lead_merge/merged3_score.json` exactly (245 entries). The placelib check is clean.

Trap found: apply_stage must run **with GAP/RING unset**. The stage worker re-placed the evicted parts with gap 0. With
the placer's GAP=0.25 RING=0.4 still exported, D410 finds no spot and the stage step leaves an overlap. build.sh runs
it under `env -u GAP -u RING -u GAPB -u RINGB`.

Adding a worker's result needs no code change: drop its `{ref: [x, y, abs rot]}` file into `overrides/` with a name
that sorts last. I tested this with `runs/ov_test` (merged3 files + `30_ports_best.json` + `40_stagepwr_best.json`
-> `runs/b_ovtest`): the check is clean, and the build differs from `stagepwr/best_gu.json` in exactly the 6 ports
parts.

## 2. Rule-based generic flow (no typed support-part coordinates)

```
docs/layout-teams/A/onecmd/generic/run_rules.sh <workdir> [--score[="ARGS"]] [place_rules.py options]
```
It takes 66 s including the dump and is deterministic: `runs/rbest` reproduces `runs/r8` with 0 parts differing. The
best result is copied to `onecmd/generic_best_gu.json` and `onecmd/generic_best_score.json`.

`generic/place_rules.py` is a copy of `generic/place_generic.py` with rules from `generic/rules.py`. No rule names a
reference designator; each reads only footprint geometry, pad nets, constraints.json and already placed parts.

- **Stage template on the fixed inductors** (`--stage`, `stage/stage_template_u403.json`): Q401/Q402, the HF and
  bulk caps, the gate resistors and the BAT sense resistor with its kelvin filters hang from L401, and the same
  template sits on L501. The template is B4 plus U403 (controller under the bridge) and R444 (HG1 gate resistor),
  both relative to Q401. There is no absolute coordinate; 19 relative poses.
- **PD chip rotation** (`rules.pd_rotation`): the big power pads (>= 3x median pad area, on constraints power nets)
  face the mean of the connector VBUS pins and the inductor that the PPHV sense resistor feeds. The connector and
  inductor are found from the netlist and constraints draw. Result: rot 0 for both U401 and U501, the same as v5.
- **Sense resistor beside the PPHV pad** (`rules.sense_targets`): one shunt-cap length + 0.5 mm out from pad 20,
  then along the chip side toward the consumer, so the shunt cap fits between. It also gets an **exit band**:
  1.5 mm boxes from its consumer-side pad to the nearest placed pad of that net (C427), kept clear of other nets.
- **TVS at the connector** (`rules.tvs_targets`): its VBUS pads target the connector VBUS pin nearest the chip's
  *largest* VBUS pad. D401 lands at (114.3, 67.3, 270); merged3 has (114.55, 67.05, 270).
- **Power-pin cap at its pin, one pitch off-centre** (`pincap`, `caprot`): the cap is aimed one pin pitch toward
  the row side with fewer signal pins, with its axis along the row normal and a courtyard gap of 0. C407 lands at
  (104.5, 77.0, 90) and C507 at (83.5, 77.0, 90); merged3 has (104.5, 76.95, 90) and (83.5, 76.95, 90).
- **Big-pad decoupling** (`bigpad`): a cap whose served pin's net has a much larger pad on the same chip goes to that
  pad (C450/C550: VBUS pin 32 -> pad 23).
- **Pull-up in front of a walled pin** (`pullup`): this applies to a signal pin whose pad edge is < 0.75 mm from a
  power pad of the same IC. Its 2-pad resistor goes straight out from the pin, axis along the row normal, signal pad
  0.9 mm from the pin, most-walled pin first. R541 lands at (86.5, 84.4) (merged3 86.5, 84.25) and R455 at
  (103.1, 77.8) (merged3 103.0, 77.75).
- **Support-part fixes** found while screening:
  - Stage bulk caps (constraints draw cin/cout) count as power-corridor ends. This keeps the AC column free.
  - Kelvin and RC-filter resistors sit at the sense resistor or filtered IC pin: their other pad pulls with weight 0.3.
  - A pad whose net leaves the part's own sheet pulls with weight 0.3 (`--foreign-w`).
  - The search centre is the mean of the full-weight targets.
  - Corridor end boxes go only on an IC's largest pad of a net, so the PD chip's small VBUS pin 32 no longer bars
    the PP5V cap from pin 34.
- Inputs are unchanged: `fixed_parts.json` (TPs fixed at template poses per the charter) and `enclosure.json`.

### Variants (6 split screens, `--route=0 --no-hot`; each outdir is `onecmd/runs/<name>/score`)

| run | change | blocked (stage/p1/p2/other) | power_open beyond allowed | DRC | loss |
|---|---|---|---|---|---|
| r4 | stage template, PD rule, sense, TVS, pincap, pull-up, U403/R444 relative | 54 of 411 | PP5V@U401, PP5V@U501, AC_SNS_N@R424 | 0 | 1.144 W |
| r6 | + gap 0 at pins, corridor ends only on largest pad, caprot, bigpad | 58 of 412 | AC_SNS_N@R424 | 0 | 1.104 W |
| r7 | + exit band from R424 to the nearest AC_SNS_N pad | 53 of 411 | AC_SNS_N@R424 (C424/C427 path winds) | 0 | 1.105 W |
| **r8 (best)** | + bulk caps as corridor ends, kelvin weight, RC-filter rule, full-weight search centre | **47 of 406** (9/21/16/1) | **none** | **0** | 1.210 W |
| r9 | r8 + aprons at big pads + big-pad caps keep the escape band | 55 of 404 (9/23/22/1) | none | 0 | 1.184 W |
| r10 | r8 + big-pad caps along the pad normal, 1.5 mm outward | 50 of 401 (9/19/21/1) | none | 0 | 1.213 W |

Best generic board, **r8**: `onecmd/runs/r8/score` (also `runs/rbest`):
- blocked edges 47 of 406
- power_open only 3V3@L201 and GND@J301/J302
- DRC 0
- loss 1.210 W
- glib exact limits check: 0 errors (placer report)
- hot loops not run

For comparison, merged3 is 31 of 400 at 1.053 W, and the round-1 generic best was 59 of 415 split (1.33 W). r8 is
**16 edges worse than merged3, not within 5**, so by the brief **no hot-loop scorecard run and no PC route were
queued**.

The groundup placelib check (typed peg circle R 2.2, typed edge numbers) flags 14 items on r8. Round-1 generic best
flags 16. They are peg-circle approximations and the TPs fixed at their template poses. Board-derived limits and
KiCad DRC are clean.

Renders read (`runs/r8/score/F.png`, `B.png`):
- **F.Cu.** Each PD chip sits beside its USB-C connector: U401 under J401, U501 west of J501, as in merged3. The
  stages are compact under the inductors. AC caps | Q401 | Q402 | BAT caps; port 2 is the same template on L501. SW1
  goes straight up. Nothing of the stage is stranded. The gauge RC filters R101-R104 and Q103 sit by the gauge
  again (in r2 they were in the middle of the board).
- **Weak spots.** Port 2's VBUS (pink) runs in a long loop around the port-2 PD chip. The port-1 5 V buck inductor
  L402 was legalised 4.8 mm up, because TP109 is fixed at its template pose inside L402's merged3 spot. merged3 moved
  that test point (a groundup move the charter does not allow), and the port-1 buck output caps crowd the east side
  of U401.
- **B.Cu.** The AC_SNS_N corridors to the far input caps (C421/C456) loop around each stage (planner detours). Port
  2 has a VBUS B.Cu track from J501. B.Cu is otherwise mostly free.

What r8 still loses against merged3 (blocked list in `runs/r8/score/ghost.log`):
- U401/U501 GND pins 26/27/31/36 (8). C450/C550 sit in front of the north row east end.
- CC / C_CC at the protectors (10, as in merged3).
- I2C SDA/SCL/IRQ (6, the return_join cause in ports/NOTES).
- Port 2 charger support (DRV_SUP, REGN, HIDRV1: 7). U503's passives are placed by the greedy placer, not merged3's
  hand-tuned auto calls.

## 3. What is still typed

| | build.sh path (merged3) | generic path before (round 1, p2t_dropee) | generic path now (r8) |
|---|---|---|---|
| absolute part poses | 127 put()/sp() poses in gu/place*.py (34 of them later replaced by the stage template) + 14 override poses | 19 anchor poses + port 2 by translation | **16 anchor poses + 2 x,y-only (U401, U501 rotation derived)** |
| relative poses (no absolute coordinate) | stage template 17 parts x 2 ports | 0 (stage translated from typed Q401/Q402/R427) | stage template 19 parts x 2 ports (B4 + U403 + R444), hung from the fixed inductors |
| greedy calls with a typed search centre at=(x,y) | 91 of 94 auto() calls; 94 hand pin maps; 1 typed target point (D401) | 0 | 0 |
| mechanical numbers | about 20 in placelib (EDGE, LIP, PEGS, notch) + keep_vias.json 56 via spots | 8 (enclosure lips) | 8 (enclosure lips) |
| rule constants | RINGS table (8), DX2, UY, GAP/RING env | ring formula, corridor widths | + WALL_MM 0.75, PULL_MM 0.9, exit band 1.5 mm, kelvin / RC / foreign weight 0.3 |

Derived now that were typed in round 1: Q401, Q402, R427, U403 and their port-2 copies (stage template on
L401/L501); R424, R524 (sense rule); D401, D501 (TVS rule); U401/U501 rotation; U402/U502 (netlist). Also every
port fix of pdfix/v5 that the rules reproduce: C407/C507, R455, R541, R424, D401.

Still typed, and why:
- **Bottom block (8): U101, U102, U204, L201, Q101, Q102, F102, RS101.** These are one-off blocks with no twin. The
  floorplan_r2d boxes give only a block centre per section and side, and no rule says "protection FETs between the
  fuse and the pack wire holes" yet.
- **5 V bucks (4): U404/L402, U504/L502.** Port 2's buck sits between U501 and J501, port 1's east of U401, so
  neither is a translation of the other. A rule "buck output inductor at the PD chip's PP5V pin side, input caps
  toward PACK_P" is not written.
- **Port protectors (2): U405, U505.** They sit between the connector CC pins and the PD chip, squeezed by pegs
  H102/H104. Netlist placement of port-top anchors went 14 mm astray in round 1 (p2t_drop).
- **Gate-drive LDOs (2): U406, U506.** They sit in the centre strip over PACK_P. Netlist placement failed for U506
  in round 1. Not retried here (screen budget).
- **PD chip position (2 x,y): U401, U501.** Only the rotation is derived. The block centre would need a rule
  "under the connector, protector between, room for the VBUS stem".
- **Stage template numbers:** 19 relative offsets, each with its rule written in the template. Only C430/C438's
  offset (half courtyards) is a pure formula; the rest are geometry choices recorded relative to the FET.

## 4. Files

| Path | What it is |
|---|---|
| `onecmd/build.sh` | one command for merged3 |
| `onecmd/apply_overrides.py`, `onecmd/check.py` | override applier; placelib check |
| `onecmd/gu/` | copies of the groundup scripts + v5 port scripts + gu_to_score / cmp_place |
| `onecmd/stage/apply_stage.py` | copy, with `STAGE_WD` |
| `onecmd/stage/stage_template.json` | B4 |
| `onecmd/stage/stage_template_u403.json` | B4 + U403 + R444 |
| `onecmd/overrides/10_stagefix_s3.json`, `onecmd/overrides/20_pdfix_a3.json` | merged3 override files |
| `onecmd/generic/place_rules.py`, `onecmd/generic/rules.py`, `onecmd/generic/run_rules.sh`, `onecmd/generic/anchors_rules.json` | rule-based generic flow |
| `onecmd/generic/glib.py`, `onecmd/generic/gdump.py`, `onecmd/generic/fixed_parts.json`, `onecmd/generic/enclosure.json`, `onecmd/generic/showp.py`, `onecmd/generic/render.py` | copies from generic/ |
| `onecmd/generic_best_gu.json`, `onecmd/generic_best_score.json` | r8 placement |
| `onecmd/runs/` | m3 build, r1-r10 rule runs, score outdirs, about 70 MB |
| `onecmd/SKILL-NOTES-draft.md` | method for a cheaper model |

## 5. Skill notes
See `SKILL-NOTES-draft.md`.
