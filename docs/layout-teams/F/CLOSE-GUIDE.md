# Team F closing guide: finish the connections the router left open in your region

The board is placed, power copper is generated, the lead laid power straps and Kelvin taps, the router routed 365 of
380 connections. What is left is what the router could not do: pins walled in by other routes or by pours, pads that
need a via in the pad, pour pieces that do not touch. You close every item in your list inside your region, by
looking at pictures, removing what is in the way and re-laying it, and checking with the real KiCad DRC.

Board: 43 x 74 mm, x right, y DOWN, mm. F.Cu (parts, power pours), In1/In4 solid GND (a via just passes through),
In2.Cu (signals + PACK_P pour), In3.Cu (signals + 3V3 pour), B.Cu (some power pours and capacitors).
Rules: track 0.2 (0.15 for necks at fine-pitch pins), clearance 0.15, HighCurrent nets (power, CELL_*) 0.25 from small
signals, via 0.45/0.3 through all layers, via centres 0.5 apart (same net) / 0.6 (other net), copper to board edge 0.25.

## Tools (`docs/layout-teams/F/tools`); your work dir `/home/claude/runs/c_<name>` holds board `g1`
Write `docs/layout-teams/F/routes/<name>.py`:
```python
import sys; sys.path.insert(0, '/home/claude/prompt-to-functional-pcba/docs/layout-teams/F/tools')
from ml import ML
h = ML('/home/claude/runs/c_<name>', 'g1')
h.pad('U501', 17)                       # (x, y, polygon, net, layer)
h.near(x, y, 0.5)                       # copper within 0.5 mm of a point, per layer
h.route(net, a, b, w=0.2, layers=('F.Cu','In2.Cu','In3.Cu','B.Cu'), margin=4.0)   # multi-layer path search with the real
                                        #   rules, adds vias itself; a, b must lie ON copper of the net (pad centre,
                                        #   via centre, track end). Returns the path or None. layers=(..) restricts it.
h.try_route(net, a, b)                  # same with fall-backs (0.15 mm, wider window)
h.via_near(net, x, y, r=1.0, n=3)       # legal via spots near a point: [(dist, x, y)]
h.via(net, x, y)                        # add a via (check the spot with h.via_free(net, x, y) first)
h.force(net, 'F.Cu', [(x, y), (x, y)], w=0.15)   # exact track, NOT checked: for stubs out of fine-pitch pins and nudges
h.plane(net, (x, y))                    # GND / 3V3 / PACK_P pad: short track to a new via that lands on the net's plane
h.drop(net, layer_or_None, [x0, y0, x1, y1])   # remove existing tracks of a net (both ends in the box) and its vias in
                                        #   the box; the object forgets them, so you can route through and then re-lay it
h.save('/home/claude/prompt-to-functional-pcba/docs/layout-teams/F/routes/<name>.json')
```
Pictures first: `python3 tools/crop.py /home/claude/runs/c_<name> g1 x0 y0 x1 y1 /home/claude/runs/c_<name>/a.png`
(four layers side by side with net names; add `F.Cu,In2.Cu 80` for chosen layers and zoom). Read the picture.

Apply + real DRC (1 to 2 minutes, run in the foreground with a 10 minute limit, from `docs/layout-teams/F`):
`python3 tools/hr2.py /home/claude/runs/c_<name> g1 <name>_1 routes/<name>.json`
It prints the DRC errors, the open connections of the nets you touched and the totals. Always build from `g1` with your
whole script (one script, re-run from the top), so the result can be merged with the other regions.
To see your result: crop with board name `<name>_1`.

## How to close each kind of item
- **Pin walled in by other routes** (router said "no way even with every other route gone" means pours or pads wall
  it; "blocked by routes" means tracks). Look at the crop. Usual fixes: a 0.15 mm `force` stub straight out of the
  pin to free space then `route` from the stub end; a via just outside the pin row; `drop` the neighbour's track or
  via inside a 1 to 2 mm box, lay yours, then re-lay the neighbour with `route` (it must come back: check the open
  list). Never leave a net you dropped open.
- **Pad inside a pour of another net** (gate pads HG1 at Q401.1 / Q501.1, thermistor pads TH401.1 / TH501.1): a via
  IN the pad (`h.via_near(net, x, y, 0.4, inside=h.pad(..)[2])`), then an inner layer. If no spot in the pad is
  legal, say exactly what blocks it (layer, net, distance).
- **Zone to zone items** (two pieces of the same pour): the positions printed are zone corners, not the gap. Crop the
  layer, find the piece that holds no via or pad connected to the rest, and join it with a track between HARD copper
  of the net (pad to pad, via to pad, via to via) on any layer; a track that only touches pour is cut by the refill.
  A tiny island with no pad on it can be left: say so.
- **GND / 3V3 / PACK_P pads or track ends**: `h.plane(net, point)`; if it fails, a via near the pad plus an inner
  track to the nearest via of the net.
- Pours of GND, PACK_P and 3V3 refill round new copper and are never obstacles, but do not wall off a pour neck that
  feeds a load. Other pours (VBUS, PPHV, PP5V, SW, AC_SNS_N, BAT_SNS_P, CELL_P...) are hard copper: go under them.
- Never drop or cut: PACK_P tracks (wide straps on In2 / B.Cu), Kelvin tap tracks (nets AC_SNS_N, BAT_SNS_P, PPHV and
  PACK_P from the shunts R424/R427/R524/R527/RS101), pours, parts. Do not move parts.
- Leave copper outside your region alone unless your list says a net crosses regions; then keep that track on an
  inner layer and report its path.

## Rules
Edit only `routes/<name>.py/.json` and files in your work dir. No git. Do not change tools (report tool problems).
Never order PCBs. Never pipe a run into `head`. Foreground commands stop at 10 minutes. At most 12 hr2 runs.
Done = your list is closed with 0 DRC errors in your region and nothing you touched left open.
Report (under 300 words): closed / left with the exact reason for each left item, anything dropped and re-laid,
cross-region tracks, tool problems, hr2 runs used.
