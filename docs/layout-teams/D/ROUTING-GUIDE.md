# Team D routing guide: hand-routing the connections the router left open

The board is placed, its power copper is generated, the lead has laid the key routes (Kelvin sense pairs, gate
escapes) and the router has routed the rest in tiers. You finish a region by hand: every open connection and DRC
error in your list. You decide where each track and via goes, a tool checks clearance before anything is written,
and the real KiCad DRC confirms.

Board: 43 x 74 mm, x right, y DOWN, mm. Layers: F.Cu (parts, power pours), In1 and In4 are solid GND planes (never
routed, a via just passes through), In2.Cu (signals, router ran them mostly vertical, plus a PACK_P pour that refills
round new copper), In3.Cu (signals, mostly horizontal, plus a 3V3 pour that refills), B.Cu (bottom, some power pours
and capacitors). Tracks 0.2 mm (0.15 allowed for a short neck at a fine-pitch pin), vias 0.45 / 0.3 through all layers.

## Tools (in `docs/layout-teams/D/tools`, work dir `/home/claude/runs/r2_route`)
Write a script `docs/layout-teams/D/routes/<your name>.py`:

```python
import sys; sys.path.insert(0, '/home/claude/prompt-to-functional-pcba/docs/layout-teams/D/tools')
from obst import HR
h = HR('/home/claude/runs/r2_route', 'p2')            # the routed board you build on; loads every obstacle
h.near(x, y, 0.5)                                     # what copper is within 0.5 mm of a point, per layer
h.free_vias(net, x, y, 1.5)                           # nearest spots where a via of this net is legal: [(dist, x, y), ...]
h.via(net, x, y)                                      # add a via (prints PROBLEM if not legal)
h.seg(net, 'F.Cu', [(x, y), (x, y), ...])             # a track you draw yourself, checked
h.auto(net, 'In3.Cu', (x, y), (x, y))                 # a track found for you on ONE layer round everything in the way;
                                                      #   returns the points, or None and prints NO PATH (margin=6 widens the search)
h.link(net, (x, y), (x, y), 'In3.Cu', r=1.0)          # pad to pad: a via near each end, inner-layer track, short F stubs
h.drop(net, 'In3.Cu', [x0, y0, x1, y1])               # remove an existing route (tracks whose both ends are in the box, vias in
                                                      #   the box; layer None = all layers) so you can re-lay it; hr2 applies it,
                                                      #   your HR object does NOT see the removal, so make a first file with only
                                                      #   the drops, apply it to a new board name, and build on that board
h.save('<your name>.json')
```
Everything you add becomes an obstacle for what you add next. A pad point is the pad centre (from the open list, or
`python3 tools/pinmap.py --p ../best_placement.json U401` run in tools, or `h.near`). A track must end ON copper of
its net: pad centre, via centre, or an existing track end.

Apply and check with the real DRC (about 1 minute):
`python3 tools/hr2.py /home/claude/runs/r2_route p2 <out name> routes/<your name>.json`
It prints every DRC error on the board, the connections of your nets that are still open, and the totals. Use your
own out name (start it with your name). Pictures: `python3 /home/claude/prompt-to-functional-pcba/tools/copper/render.py
<board>.kicad_pcb <board>.json /tmp/x.png F.Cu x0,y0,x1,y1 60` (also In2.Cu, In3.Cu, B.Cu); look before you guess.

## How to route a connection
1. `h.near` both ends. Short and on the same side of a chip: try `h.auto(net, 'F.Cu', a, b)`.
2. Otherwise `h.link` on In3 (east-west) or In2 (north-south); for a dog-leg use a via in the middle and two autos.
3. No free via at a pad: look a bit further (`r=2`) and bring an F track to it with `h.auto(net, 'F.Cu', pad, via)`;
   a via in the pad itself is allowed as a last resort on pads at least 0.45 mm wide.
4. A pour of GND, PACK_P or 3V3 refills round your copper, so it is never an obstacle. Other pours are hard: go round
   or change layer. Do not cut power pours.
5. GND, 3V3 and PACK_P pads connect with ONE via next to the pad plus a short F track (the planes are on In1/In4 for
   GND, In3 for 3V3, In2 for PACK_P); if the pour does not reach the via on that layer, add an inner track to the
   nearest existing via or track of the net.
6. If a route of another signal is in the way, you may `drop` it and re-lay both, but only signal routes, never
   pours, never the Kelvin pairs (nets AC_SNS_N, BAT_SNS_P, PPHV and PACK_P tracks on In3 from the shunts).
7. A DRC error between two router tracks: drop the shorter of the two routes and re-lay it.

## Rules
Edit only `routes/<your name>.py` and `.json`. No git commits. Do not change tools; report tool problems. Never
order PCBs. Do not move parts. Stop when your list is done or after about 40 tool calls on the hard ones; report what
is left and why.

## Notes from the first pass (read these)
- The checker is stricter than DRC (0.2 mm to copper, 0.3 to hard pours). `h.auto(..., clr=0.15)` finds corridors the
  default misses; HighCurrent nets (CELL_1N, power nets) need 0.25 mm from small signals, so keep the default near them.
- `auto` cannot start inside a 0.4 mm-pitch pin row: draw the first 0.3 to 0.5 mm straight out of the pin yourself
  with `h.seg` (w=0.15), then `auto` from the end of that stub.
- The wide PACK_P tracks on In2 and B.Cu from (100.8, 116.3) to (119.0, 106.8) are the pack power path. Never drop
  or cut them; cross them on In3 or F.Cu.
- Tracks are allowed inside the J301/J302 no-via areas even though the checker flags them; confirm with hr2.
- F.Cu power pours (VBUS, PPHV, PP5V, AC_SNS_N, BAT_SNS_P, SW, CELL_P) are hard: a track through one cuts the power
  path. Go under them on an inner layer.
- A second PACK_P power track (1 mm, In2) runs down the left edge from (79.85, 65.6) to (79.45, 84.0). Same rule:
  never drop or cut it, cross it on In3, B.Cu or F.Cu.
- `h.drop(net, layer, box)` removes the net's VIAS in the box on every layer, whatever layer you give: re-add a via
  you still need. `h.near` does not list pours at radius 0; use 0.3.
- When a pad sits on a cut-off scrap of the 3V3 pour (In3) or has no legal via, a second hop helps: via A near the
  pad, `auto` on one layer to a stepping-stone via B (any legal spot, `h.free_vias(net, x, y, 3)`), then another
  layer from B to the net's copper.
