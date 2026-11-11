# Spike 3: can a corridor score see the missing lane?

Run 2026-11-11 in the cloud container. Two Monolith boards with the same 289 parts: the hand-routed one
(34 mm of signal track on a ground-plane layer) and the scripted one (258 mm in six nets, down the centre
column between the two power stages).

## Question

From placement and power copper alone, in about a second, does routing capacity against demand come out
comfortable on the hand board and short on the scripted board where the plane was cut? The research said: if
yes, build the floorplanner round that score; if no, corridor planning needs a trial route.

## Answer

**No. A static capacity score does not separate the two boards. The demand half of it does.**

| Measure | Hand board | Scripted board |
|---|---|---|
| Signal nets, half-perimeter length summed | 1888 mm | 2505 mm (+33 %) |
| Signal track actually drawn | 2126 mm | 3155 mm (+48 %) |
| Most nets that must cross one line across the board | 37 | 50 |
| Straight line: nets crossing / free width, worst line | 0.41 | 0.36 |
| Lanes (maximum flow through free space, 6 mm band): nets / lanes, worst band | 1.54 | 0.91 |
| Demand / capacity on a 6 mm window (RUDY), 90th percentile | 0.74 | 0.65 |
| Share of the plane cut inside the 20 % most loaded cells | | 47 % |

1. **Capacity cannot be read off the board before signals are routed.** Every capacity measure rates the
   hand board as tight or tighter than the scripted one, and the hand board routed clean. At its worst band the
   model finds 24 lanes and the board really carries 37 nets there. Two reasons: pads leave more room between
   them than a pitch-sized grid sees, and power pours yield to signals (321 mm of the hand board's signal track
   runs through a power pour). Treating generated power copper as fixed is what removes the lanes.
2. **Demand is exact and cheap.** The count of nets with pads on both sides of a line matched the nets really
   crossing it on the hand board at all three lines checked (21, 37, 21). The scripted placement needs a third
   more wiring across the middle of the board. That is the difference a placement score can see.
3. **Within one board the lane measure does point at the right place.** On the scripted board the tightest
   bands are at y = 101 to 103 (0.90) and 109 (0.91). The layout notes say the same: no legal via site between
   y = 101 and 107, which is why two nets stayed on the plane. So it is a usable diagnosis ("where is it
   tightest"), not a pass or fail.

## What this changes

- The floorplan score uses demand (nets across each cut, half-perimeter length), not capacity.
- Lanes are a declared constraint, not a measurement: the block-to-block nets get a reserved corridor with via
  sites at both ends, and the power-copper generator must leave it free. The scripted flow poured first and
  routed second; the hand flow did the reverse.
- Accepting a floorplan needs a trial route of the block-to-block nets, as the research said it might. The
  floorplan loop is then minutes per candidate.

## Limits

One board pair. Capacity models used a 0.35 mm pitch and pad bounding boxes; a finer model would raise both
boards' capacity and would still not explain why the tighter one routed. Nothing here is measured hardware.

## Run it

```
docker run --rm -u 0 -v $PWD:/w -w /w kicad/kicad:10.0 python3 dump_board.py board.kicad_pcb board.json
python3 corridor.py board.json      # demand and capacity per 2 mm cell
python3 cuts.py board.json          # 6 mm windows and straight cut lines
python3 lanes.py board.json         # maximum flow through free space per band (needs scipy)
```
