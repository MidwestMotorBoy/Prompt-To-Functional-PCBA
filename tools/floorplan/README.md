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

## Run it

```
python3 floorplan.py extract <board dump.json> intent.json [<netlist.json>]
python3 floorplan.py score intent.json <board dump.json> [<netlist.json>]
python3 place_sa.py intent.json <board dump.json> <netlist.json> <constraints.json> out.json [moves] [seed]
```
