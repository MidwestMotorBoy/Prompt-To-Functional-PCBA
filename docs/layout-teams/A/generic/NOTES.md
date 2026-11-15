# Worker 'generic' (team A, round 1): a placer with no typed coordinates for support parts

All numbers below come from `tools/score/score_board.sh` (scorecard), unless marked "placer report".

## What is in this folder
| file | what |
|---|---|
| `place_generic.py` | the placer. Inputs: board dump, kicad_pro/dru, constraints.json, anchors.json, fixed_parts.json, optional enclosure.json. Output: `placement_gu.json` (absolute poses), `report.json`, `place.log` |
| `glib.py` | library copied from groundup `fpdb.py` + `placelib.py` and generalised: `DB`, `Limits` (mechanical limits from the board), `escape_ring()` (derived clear band round fine-pitch ICs), `Placer` (greedy per-pad-target search of `placelib._auto`, with twin translation, power corridors, exact `check()`) |
| `gdump.py` | groundup `dump.py` + the Edge.Cuts outline with its holes (runs in the kicad/kicad:10.0 container) |
| `anchors.json` | poses of the 32 big parts (28 typed, 4 derived by translation) |
| `anchors_p2t.json` | generality test: every port-2 anchor derived from its port-1 twin (20 typed, 12 derived) |
| `anchors_v5.json` | variant with the rebuild worker's v5 PD-chip poses (g8, not finished) |
| `fixed_parts.json` | the fixed rule + the explicit cup-fixed list, one reason per entry |
| `enclosure.json` | the only typed mechanical numbers left: the two F.Cu lips of the cup (the board file does not hold them) |
| `run.sh` | one command: template -> dump -> placement -> scorecard format (-> scorecard with `--score`) |
| `showp.py`, `servesdist.py`, `render.py` | placement picture without copper; distance of every `serves` cap to its pin |
| `best_placement.json`, `best_placement_gu.json` | best candidate (g19) in scorecard format and in absolute groundup format |
| `runs/<name>/` | each variant: `place.log`, `report.json`, `placement*.json`, `score/` (scorecard outdir) |

Run: `docs/layout-teams/A/generic/run.sh <workdir> [--score] [place_generic options]`. The best run is
`run.sh runs/g19 --corr-path=0 --corr-floor=1.4 --corr-maxlen=8 --corr-pin=2.0 --serves-noring=2`
(`ANCHORS=<file>` selects another anchors file).

## Rules (all derived, none per part)
1. **Mechanical limits from the board** (`glib.Limits`): Edge.Cuts outline with notches and connector cut-outs
   (`GetBoardPolygonOutlines`), every rule area with "no footprints" per side (the KO_* zones: top stops, rails, tails, wire
   holes, gap fillers), pad-to-edge distance from the project/dru (`edge_clearance` 0.25 mm). Rasterised at 0.05 mm with a
   summed-area table, so a courtyard test is O(1). Holes/pegs are footprints (H101..H104) and are fixed parts, so their
   courtyards are obstacles. Only the cup lips are typed (enclosure.json, 2 boxes).
   placelib's typed EDGE, LIP_Y, LIP_X, PEGS, PEG_R and the notch numbers (about 20 numbers) are gone.
2. **Fixed set**: locked, or on B.Cu, or ref class J/H/TP/SW (rule) + 19 explicit cup-fixed refs with reasons (fixed_parts.json). 50 parts.
   TP parts stay where the template has them; groundup moved four test points, so L402, L201, U403 and U502 hit TP109,
   TP301, TP113 and TP512 at their groundup poses and are legalised (nearest legal pose, same rotation; L402 moves 4.8 mm up).
3. **Anchors** are chosen by rule (ICs, inductors, fuses, sense/kelvin resistors and current shunts, FETs/diodes with >= 8 pads): 32 parts.
   A pose is typed (from groundup placement.json) or `translate` = the port-1 twin's pose shifted by the offset between two
   fixed parts (L401 -> L501). Twins are found from the netlist: sheets whose names differ only in a number, same footprint,
   value and nets once the sheet prefix is swapped (64 pairs).
4. **Support parts: targets per pad from the circuit data**, in this priority:
   hot_loops caps -> their pads on the switch pins' nets go to those pins (ignores escape bands);
   `serves` -> the pad on the served pin's net goes to that pin (pin_pads / pin function), the plane pad (GND) to the served
   part's GND pads with weight 0.5, other pads by netlist;
   kelvin / shunt filters -> the pad on the sense resistor's net goes to that resistor's pad;
   thermistors -> the hottest part (constraints heat) of their sheet on their side;
   otherwise netlist -> each non-plane pad (GND, PACK_P, 3V3 are planes: GND netclass or power nets with >= 20 pads)
   goes to the nearest placed pad of the same net, preferring partners on the part's own sheet.
   Search centre = mean of the nearest target points; search = placelib._auto (min Manhattan pad-to-target, 4 rotations,
   courtyard gap 0.25 mm round <= 3-pad parts), radii 4, 8, 14, 22 mm.
5. **Order**: hot-loop caps (constraints order), stage bulk caps (draw cin/cout order), small Q/U, serves caps (smallest value
   first), kelvin filters, bridges (every signal pad has its partner placed), the rest; inside a tier, parts with the
   largest share of targeted pads first. Re-evaluated after every placement (targets appear as parts get placed).
6. **Repeated blocks**: a part whose twin is unplaced and whose targets all sit on parts with one common twin offset is
   placed with its twin (both poses must be legal) - port 2 gets port 1's arrangement without a typed DX2.
7. **Escape ring** (replaces the typed RINGS table): for an IC with > 6 small pads at pitch p <= 1 mm,
   ring = ceil(via_pitch / p) * via_pitch * (distinct signal nets / small pins), via_pitch = via + clearance from the
   project's Default netclass. Values: U401/U501 0.6, U403/U503 0.9, U101 0.79, U102 1.2, U404/U504 0.75, U405/U505 0.42,
   U402/U502 0.45 (groundup typed U401 1.2, U102 0.9, U101 0.6, U404 0.5, U405 0.6).
8. **Power corridors** (new this round, the fix for the power opens): for every constraints net with kind power and
   current_a >= 1 A (not a plane), the parts on it that carry the current (same rule as tools/copper/roles.py kind_of:
   J, L, F, Q, D, SW; sense resistors; IC pads >= 3x the IC's median pad and >= 0.3 mm2) are joined by a minimum spanning
   tree; each link no longer than 8 mm reserves a straight band 1.4 mm wide (0.3 mm/A, floor 1.4, cap 1.5) that support
   parts not on that net may not cover, plus a 4 x 4 mm box at each IC power pin end. Longer links get none: their copper
   goes round or uses an inner layer, and a long band displaces too many parts.
9. **Decoupling of power pins sits at the pin**: caps whose served pin is on a power net (C406/C407/C417-C419/C449/C450 and
   the port-2 twins) ignore the escape bands (`--serves-noring=2`), like hot-loop caps. Without this the escape band of
   U401 pushed C407 (PP5V) 3 mm away and the 5 A VBUS copper took the room beside pin 34, so PP5V had no path.

## Checks after placing (placer report)
0 courtyard overlaps, 289/289 placed, 0 limit violations (exact courtyard + pad-to-edge test). Serves distances:
see table. `check()` on the hand-typed groundup placement with these limits finds 7 errors (J301 over the antenna
parts, J301/J113 over the edge - all fixed parts - and C549 1 mm into the cup lip).

## Variants (scorecard, --route=0 --no-hot unless noted)
Baseline (lead, hand-typed groundup placement): loss 1.064 W, DRC 0, blocked 65 of 441, power_open GND@Q401,Q501 + allowed.
Serves cap distance to its pin (placer, 85 caps): groundup max 17.81, median 2.45, 30 over 3 mm.

| run | change | blocked | DRC | power_open (beyond allowed 3V3@L201, GND@J301/J302) | loss W | serves median / >3 mm |
|---|---|---|---|---|---|---|
| g6 | first full generic run | 61 of 442 | 2 | PP5V@U501 | 1.25 | 3.27 / 46 |
| g7 | pad-edge margin fix | 62 of 436 | 0 | PP5V@U501 | 1.227 | 3.27 / 46 |
| g10 | + straight power corridors, 0.8 mm | **56 of 447** | 0 | VBUS@U401, VBUS@U501 | 1.096 | 3.48 / 48 |
| g11 | corridors follow a grid path round placed parts | 64 of 450 | 0 | PP5V@U401, PP5V@U501 | 1.204 | 3.48 / 49 |
| g12 | g11 + 1.4 mm floor | 61 of 451 | 0 | PP5V@U401, PP5V@U501 | 1.199 | 3.48 / 49 |
| g13 | path + straight | (killed) | | PP5V both left to router | | |
| g14 | path, shortest links first, avoiding other nets' bands | 60 of 447 | 0 | PP5V@U401, PP5V@U501 | 1.178 | |
| g15 | straight, 0.8, links <= 8 mm only | (killed) | | PP5V@U501 winds | | 3.27 / 46 |
| g16 | g15 with 1.4 mm | (killed) | | PP5V both left to router | | 3.27 / 46 |
| g17 | + 4x4 mm box at IC power pins | (killed) | | PP5V both left to router | | 3.27 / 46 |
| g18 | + all serves caps ignore escape bands | 73 of 456 | 0 | **none** | 1.325 | 2.39 / 32 |
| g19 | + only power-pin serves caps ignore bands (now the defaults) | 68 of 445 | 0 | **none** | 1.337 | 2.73 / 39 |
| g19 hot | same board, hot loops on | 67 of 443 | 0 | none | 1.336 | 7 of 7 pass, 7.80 nH |
| p2t | g19 rules, **port 2 anchors all derived from port 1** (anchors_p2t.json: 20 typed, 12 derived) | 64 of 447 | 0 | none | 1.321 | 2.92 / 41 |
| p2t hot | same board, hot loops on | 64 of 447 | 0 | none | 1.322 | 7 of 7 pass, 7.81 nH |
| p2t_r13 | p2t + escape rings x1.3 | 61 of 444 | 0 | none | 1.325 | 3.48 / 49 |
| **p2t_dropee** | p2t, EEPROMs U402/U502 not anchors (placed by the netlist): 19 typed, 11 derived, 2 automatic | **60 of 446** | 0 | none | 1.328 | 2.92 / 41 |
| p2t_dropee_r13 | + rings x1.3 | 67 of 448 | 0 | none | 1.299 | 3.48 / 49 |
| p2t_drop | p2t, also D401/D501/U406/U506 automatic | placer failed: U506 found no target spot (FAIL), D401 went 14 mm to the corner | | | | |

Loss is not comparable to the baseline: the baseline's open GND terminals at Q401/Q501 carry no current in the DC solve.

Best candidate: **p2t_dropee** (`best_placement.json` scorecard format, `best_placement_gu.json` absolute; scorecard outdir
`runs/p2t_dropee/score_hot`: score.json, F.png, B.png, hot_gate.log). With hot loops on: blocked 60 of 445, DRC 0,
power_open only the allowed 3V3@L201 and GND@J301/J302, 7 of 7 hot loops tier 1, tier-2 7.86 nH, loss 1.328 W.
Reproduce: `ANCHORS=$PWD/anchors_p2t.json ./run.sh runs/x --anchor-only=U402,U502 --score="--route=0"` (the placer is
deterministic; `runs/p2t_repro` reproduced `runs/p2t` byte for byte).
Against the hand-typed groundup baseline (65 of 441, GND@Q401/Q501 open): fewer blocked edges, no power opens beyond the
allowed ones, DRC 0 for both. The renders show compact blocks: each PD chip beside its USB-C connector, the decoupling at
its chip (85 serves caps: median 2.92 mm, groundup 2.45; max 12.3 mm = the charger AC bulk caps C427/C527 that the rule
copper reaches anyway, groundup max 17.8). One visible oddity: with port 2 translated from port 1, the port-2 gate-drive
LDO U506 sits at the left edge (x 81) instead of the centre strip, and U505/D501 sit in the top-left corner.

## Full routes (Logan's PC)
Same router as score_board.sh, one thread on the route server. Reference: hand placement 391 of 448; team A rebuild-base
(groundup placement) 378 of 441, rebuild-v5 375 of 436.

| name | board | routed | failed | edges | minutes | status |
|---|---|---|---|---|---|---|
| generic-g19 | g19 | 368 | 76 | 444 | 56.5 | done |
| generic-p2t | p2t | 374 | 74 | 448 | 72.5 | done |
| **generic-p2t-dropee** | p2t_dropee (best) | **379** | 66 | 445 | 63.8 | done |
| generic-g10 | g10 (VBUS open, for comparison) | no result 99 min after queueing; not re-run locally (the board fails the power hard limit anyway) | | | | |

g19's failures concentrate at the PD chips (I2C SCL, SBU_FLT, CC1/C_CC1, CHG_INT, PPHV, GND pins 26/27/31/36 of U401/U501)
and the P1_LDO_3V3 net - the same picture as the lead's blocked-edge analysis. No local --route=45 fallback was needed:
every candidate came back within 75 min of queueing.
The best generic board routes 379 of 445: above the groundup placement (378 of 441) but 12 short of the hand placement's
391 of 448, so the routing goal is NOT met yet.

## Typed coordinates: before and after
| | groundup (hand-typed) | generic flow (best run) |
|---|---|---|
| part poses typed with put()/sp() | about 116 parts (95 put/sp calls, the port-1 stage copied by a typed DX2) | 19 anchor poses (anchors_p2t.json minus U402) |
| auto() calls with a typed search centre at=(x,y) | 97 (plus 102 hand-written pin maps pins={...}) | 0 (centre and per-pad targets derived) |
| mechanical numbers | about 20 (EDGE 4, LIP_Y, LIP_X 2, PEGS 8, PEG_R, notch 3, TP limits 2) | 8 (two cup-lip boxes in enclosure.json); outline, notch, holes, rule areas, edge rule read from the board |
| other typed tables | RINGS (8 values), DX2, UY, per-file GAP/RING env | none (rings derived, port offset from the fixed L401->L501 pair) |
| fixed list | 19 refs in a code line | 19 refs with reasons in fixed_parts.json + the rule |

## What still needs a typed pose, and why (19 anchors)
- Port 1 power stage Q401, Q402, R427, U403 and the gate-drive LDO U406: their geometry sets the hot loops; a rule that puts
  the half-bridge FETs at the fixed inductor L401 from constraints `draw` (--derive fets) was not finished this round.
- PD/port block U401, U405, D401, U404, L402, R424: the floorplan_r2d boxes give only a block centre per section and side,
  not the pose of a 40-pin chip relative to the connector; deriving U401 from the box centre plus "pins facing J401" is the
  next step. D401/U406 placed by the netlist alone went 14 mm away (p2t_drop), so they stay anchors.
- Bottom block U101, U102, U204, L201, Q101, Q102, F102, RS101: one each, no twin to translate from; the floorplan boxes
  again only give a block centre.
- Derived: all 11 port-2 anchors (D501, L502, Q501, Q502, R524, R527, U501, U503, U504, U505, U506) by the L401->L501
  translation; U402/U502 placed by the netlist like support parts. L402/L502 had no common legal shift (TP109 is fixed
  inside L402's groundup spot), so each was legalised on its own.

## What a new board must supply for this to run
1. The board file (template) with the outline, fixed parts and rule areas -> `gdump.py` dump; kicad_pro/dru for clearance,
   via size and pad-to-edge rule.
2. constraints.json with `serves` (every decoupling cap -> pin), `pin_pads` where pin names are ambiguous, `hot_loops`
   (caps in order + switch pins), `draw` (stage cin/cout), `kelvin`, `heat`, and `nets` with kind/current_a for power nets
   (the corridors and the power-pin decoupling rule read them).
3. anchors.json: a pose for each big part chosen by the anchor rule, or `translate` from a twin + a pair of fixed parts.
4. fixed_parts.json: the enclosure-fixed refs with reasons; enclosure.json for any limit not in the board file.
Repeated blocks are found from sheet names that differ only in a number.

## Traps (for the skill notes)
- Clearing room next to an IC's power pin can invite the higher-current net's copper (planned first) into it: g17 kept every
  other-net part 2 mm off U401's PP5V pin and VBUS (5 A) took the space, so PP5V lost its path. The fix that worked was to put
  the power pin's own decoupling cap at the pin (ignoring the escape band), so that net owns the space.
- Escape bands round fine-pitch ICs must not apply to the caps that serve those ICs' power pins, but applying "no band" to all
  decoupling caps (g18) cost 5 blocked edges at the charger controllers: limit it to power-pin caps.
- Corridors that follow a grid path round placed parts (g11-g14) were worse than short straight bands: long bands displace too
  many parts; skip links longer than ~8 mm.
- Stray straight-line corridor over the PD chip (g10) pushed parts to the chip's other side and blocked VBUS: corridors should
  only join parts that carry the current (roles.kind_of rule: IC pads only if large).
- Translating an anchor can land it on a fixed part (TP, hole): legalise each anchor to the nearest legal pose at the same
  rotation, and if a twin pair has no common shift, legalise them separately and report it.
- The ghost blocked-edge count varies by 1-2 between two scorecard runs of the same placement (g19: 68 of 445, then 67 of 443).
- Loss is not comparable between boards with different power opens (an open terminal carries no current in the DC solve).
- Test points are fixed here (charter) but groundup moved four; anchors taken from groundup collide with them.

## Housekeeping
`runs/` is about 225 MB (scorecard intermediates: in/bare/cu boards, bare.json/cu.json, loss.npz). A cleanup of those
files was blocked by a safety check in this session; before committing, keep only score.json, F.png, B.png, *.log,
placement*.json, report.json and the cu.kicad_pcb of runs/p2t_dropee/score_hot.
