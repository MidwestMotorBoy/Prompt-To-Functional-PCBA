# Stage 6: floorplan (work in progress)

`floorplan.py` holds the intent file (board box, fixed parts, one region per block or block section and side,
lanes) and its demand score. `place_sa.py` is a first generic placer driven by the intent file.

## What the first measurements say (2026-11-11, Monolith hand board against the scripted board)

Signal demand is the half-perimeter of every net with fewer than 12 pads, at pad level.

| | Hand board | Scripted board |
|---|---|---|
| Detailed placement, half-perimeter | 2064 mm | 2508 mm (+21 %) |
| Floorplan only, 5 sheet regions (every part at its region centre) | 1007 mm | 1027 mm (+2 %) |
| Floorplan only, 29 section regions | 1719 mm | 1786 mm (+4 %) |
| Nets inside one section | 69 nets, 282 mm | 69 nets, 475 mm (+68 %) |
| Nets between sections | 92 nets, 1782 mm | 92 nets, 2033 mm (+14 %) |
| Section region area, summed | 8025 mm2 | 9009 mm2 (+12 %) |

1. The two boards have almost the same floorplan. Only 9 parts of the scripted board sit outside the hand
   board's sheet regions. Where the blocks go does not explain the scripted board's extra wiring.
2. The difference is inside the blocks: how tightly each section is packed, and which way its pins face. Nets
   that stay inside one section are 68 % longer on the scripted board.
3. So a block-level floorplan cannot be accepted on its own score. The score has to be taken on the placed
   parts, and the intent has to reach down to sections and to pins ("this capacitor at that pin").

## First generic placer: flat annealing is not enough

`place_sa.py` anneals every part inside the hand board's own section regions, from a random start, with a
spring from each decoupling capacitor to the pin it serves. Two runs of 2 million moves (about 9 minutes each):
2677 and 3104 mm, with 1 to 7 mm2 of overlap left and capacitors on average 10 mm from the pin they serve.
That is worse than the scripted board (2508 mm) and far from the hand board (2064 mm), and the two runs differ
by 16 %. Moving one part at a time cannot build a tight section.

This agrees with the floorplanning research (`/mnt/project-files/floorplan-research/`): pack blocks with a
solver, place each power stage from a template scored by the loop solver, place support parts greedily at
pin targets, and accept on a trial route. Next step: place section by section (the part with most pins first,
then its served parts at their pins), then pack the sections, and measure against the same two boards.

## Section placer: clusters at pin targets, then packing (same day)

`place_sections.py` builds each of the 29 sections as a tight cluster on its own: main part first, then always
the part most connected to what is placed, at the spot and rotation with the least wiring to placed pads, with
a strong pull from a decoupling capacitor to the pin it serves. 7 seconds for the board. `place_pack.py` then
moves the clusters as rigid pieces (annealing over about 30 pieces) and finishes with small single-part moves.
Connectors, holes and test points stay where the hand board has them. Nothing else is taken from the hand board.

| | Signal half-perimeter | Overlap |
|---|---|---|
| Hand board | 2064 mm | |
| Scripted board (the Battery-Bank flow) | 2508 mm | |
| Flat annealing, two runs | 2677, 3104 mm | 1 to 7 mm2 |
| Section placer, clusters packed, three runs | 1949 to 2185 mm | under 1 mm2 |
| Section placer after refinement, three runs | 1714, 1817, 1907 mm | 0 |

Inside sections: 170 mm of wiring against 242 mm on the hand board; served capacitors 228 mm from their pins in
total against 440 mm. About 15 minutes per run on one core.

Read this with care:

- It is wirelength only. The placer does not know hot loops, gate loops, Kelvin pairs, heat, which nets are
  noisy, or the enclosure keep-outs (pegs, lips), and bodies are pad boxes plus 0.1 mm, not courtyards. A real
  board needs more room than this, so the true gap to the hand board is smaller than the table shows.
- What it does show: placing section by section at pin targets and then packing gets a generic placer, with no
  board-specific coordinates, to the hand board's wiring demand. The flat approach could not.
- Next: the intent statements from the floorplanning research (near, order, keep-apart, lanes) with a compiler
  that checks them against the netlist; courtyards and keep-outs; crossing and hot-loop terms in the score;
  power-stage templates scored by the loop solver; then the trial route as the acceptance gate.

## Intent statements, and a placer that obeys them (same day)

`intent.py` holds the statements from the floorplanning research: `near`, `keepapart`, `order`, `kelvin`, `fixed`,
`lanes`. `derive` writes the ones that follow by rule from the circuit code (for Monolith: 106 near from the
served pins and hot loops, 6 keep-apart from switching and sensitive nets, 4 Kelvin pairs). `validate` rejects any
statement that names a part, pad or net the netlist does not have. `check` measures them on a placed board.
`place_sections.py` and `place_pack.py` take the file and use the statements as pulls and cost terms.

| Placement | Statements that hold (of 112) | Signal half-perimeter | Overlap left |
|---|---|---|---|
| Hand board | 72 | 2064 mm | 0 |
| Scripted board | 74 | 2508 mm | 0 |
| Section placer, wirelength only (run 2) | 48 | 1714 mm | 0 |
| Section placer with the statements, three runs | 103, 103, 101 | 1983, 2292, 1863 mm | 1 to 2 mm2 |

- Wirelength alone made a placement that looked best and broke more than half the statements. With the
  statements in the cost it keeps about 92 % of them at roughly the hand board's wiring demand.
- The limits are first guesses (2 mm for the first hot-loop capacitor, 2.5 mm for a served pin, 5 mm for bulk,
  centre to centre). The hand board fails 40 of them, mostly large capacitors that cannot physically sit 2.5 mm
  from a pin, so the limits need to scale with part size before the count means much as a pass mark.
- 1 to 2 mm2 of overlap remains after 300 000 refinement moves; a legalising pass is still needed.
- Still wirelength plus statements only: pad boxes for bodies, no enclosure keep-outs, no crossing count, no loop
  solver in the loop.

Update: `near` is now measured from the target pad's centre to the nearest pad edge of the part, so a large
capacitor is not penalised for its own size, with limits 1.5 mm (first hot-loop capacitor), 2 mm (served pin) and
4 mm (bulk). On that measure: hand board 69 of 112, scripted 69, placer with statements 92 to 93, wirelength-only
placer 48. The hand board's misses are of two kinds: near misses of a few tenths of a millimetre, and bulk
capacitors that the circuit code declares as serving a FET pin but that sit 6 to 8 mm away by design. The code's
`serves` does not yet say "bulk" or "at the pin", so the limit classes need the owner's judgement or a rule from
capacitor value before the count can be a pass mark.

## Run it

```
python3 floorplan.py extract <board dump.json> intent.json [<netlist.json>]
python3 floorplan.py score intent.json <board dump.json> [<netlist.json>]
python3 place_sa.py intent.json <board dump.json> <netlist.json> <constraints.json> out.json [moves] [seed]
python3 intent.py derive <build dir> <design dir> intent.json ; python3 intent.py validate intent.json <build dir>
python3 intent.py check intent.json <board dump.json> [placement.json]
python3 place_sections.py <board dump.json> <netlist.json> <constraints.json> clusters.json [J,H,TP,SW] [intent.json]
python3 place_pack.py clusters.json <board dump.json> placement.json [cluster moves] [seed] [refine moves] [intent.json]
```
