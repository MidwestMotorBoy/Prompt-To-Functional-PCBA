# Team D worker guide: hand-placing one room of the Monolith board

You place the parts of ONE room by hand: you decide where every part goes and write the coordinates yourself, look
at the picture, and correct. The lead designed the floorplan (which room holds what, where power enters and leaves).
Your job is the detail inside your room. Your brief is `rooms/<room>.brief.md`. Read it after this guide.

Everything is under `docs/layout-teams/D/` in the repo at `/home/claude/prompt-to-functional-pcba`.

## The board in two lines
43 x 74 mm, 6 copper layers (F, In1 GND, In2 signals + PACK_P pour, In3 signals + 3V3, In4 GND, B). Parts go on the
top side only. x grows to the right, y grows DOWN (north = smaller y). Units are mm. Fixed parts (connectors J,
holes H, test pads TP, thermistors TH, the big inductors L401/L501, the radio module U301, bottom-side capacitors)
never move.

## Tools (run from `docs/layout-teams/D/tools`)
- `python3 pinmap.py U401 C403 ...` prints each part's size and which pad is on which side, with nets
  (add `--p ../rooms/<room>.json` to see it as you placed it). Do this for every chip before placing anything.
- `rooms/hand_<room>.png` shows how the earlier hand layout placed your parts. It is a reference, not the answer:
  the lead changed the floorplan and the hand layout has known faults (listed in your brief).
- Write your placement as a script `rooms/<room>.py`:

```python
import sys; sys.path.insert(0, '../tools')      # run it from the rooms folder: cd rooms && python3 <room>.py
from room import Room
rm = Room('<room>')
rm.put('U401', 105.1, 79.9, 0)            # origin x, y, rotation (0/90/180/270, relative to the template orientation)
rm.put_court('L402', rot=90, left=95.0, top=105.0)   # or place by courtyard edges
rm.beside('C403', 'U401.38', 'N')         # C403's pad on the same net lines up with U401 pad 38, on its north side,
                                          #   0.15 mm between the two courtyards (gap=...), rotation chosen for you (rot=...)
rm.beside('R402', 'C403', 'E', gap=0.1)   # beside another part, centred on it (shift=... slides it along)
rm.row(['R403', 'R404'], 'R402', 'E')     # a row continuing east
rm.done()                                 # prints overlaps / out-of-room / lane violations, longest nets, decoupling
                                          #   distances; saves rooms/<room>.json and rooms/<room>.png
```
  `rm.pad('U401.38')` gives a pad position, `rm.court('U401')` a courtyard box, `rm.size('C403', rot=90)` width and height.
  Look at `rooms/<room>.png` after every run (Read it). Blue lines are the unrouted connections of your parts, the
  black boxes are your room, your parts have red outlines, green pads are GND. Every part of the room must be placed
  by your script; `done()` lists the ones you forgot.
- Whole-board score: `bash tools/qs.sh <run-name> --no-hot` (use a new name each time, start it with your room
  name). It assembles every room's latest placement, generates the power copper, runs DRC, the DC loss solve and the
  blocked-connection screen. It takes 6 to 15 minutes (only two run at a time; yours may wait). Then:
  - `python3 tools/blocked.py /home/claude/runs/<run-name> <room>` lists the power paths the copper planner could not
    draw and the signal connections that have NO path at all, limited to your room's parts.
  - `bash tools/cu.sh <run-name> x0,y0,x1,y1 F.Cu` draws the generated copper in a window (also `B.Cu`). Look at it.
  - `/home/claude/runs/<run-name>/dc.log` has resistance and loss of every power path; `hot_gate.log` (only without
    `--no-hot`) has the switching-loop inductances.
  Other rooms are being re-placed at the same time, so parts outside your room may look odd or move. Judge only your
  own parts. Run it at most 4 times: think first, look at the picture first.

## What a good room looks like (in priority order)
1. **Legal.** No courtyard overlaps, everything inside the room boxes, nothing in a reserved lane.
2. **Power paths work.** The copper planner draws each power net as a tree on the top layer between its current
   terminals, as wide as the current needs (about 0.5 mm per amp, so 2.5 mm for 5 A, 5 mm for 10 A, 0.8 mm for
   1.5 A), and refuses a path that winds (longer than 1.5 x straight + 3 mm). So: put the terminals of one power net
   facing each other with a straight, clear strip of top copper between them, and keep small parts out of that strip.
   A power path that is left open is a failure of the whole board.
3. **Hot loops are tight.** For each switching loop in your brief: the first (high-frequency) capacitor sits with
   its supply pad at the switch's supply pin and its return pad at the switch's return pin, a millimetre or less
   away, on the top layer, with free space beside the return pads for vias. The bulk capacitors follow directly
   behind it, same orientation.
4. **Every pin can escape.** The usual reason a connection has no path is that a pin is walled in by neighbours'
   pads and by power copper. So:
   - keep 0.4 to 0.5 mm of free space between a chip with fine-pitch pins and the parts around it, except for the
     one part whose pad faces that pin;
   - turn each resistor and capacitor so that the pad that connects to the chip faces the pin it connects to;
   - a net that leaves your room, or runs more than about 3 mm, needs room for a via (0.6 mm round, so a free spot of
     about 1 x 1 mm) next to its pad: do not close the ring of parts round a chip, leave gaps on every side;
   - leave 1 mm free round the pads where 5 A copper has to land on a chip (VBUS, PPHV, PP5V pins);
   - a Kelvin tap (sense line of a shunt) leaves from the inner edge of the shunt pad as a thin track, so keep that
     edge reachable.
5. **Decoupling.** Each capacitor that serves a pin (`done()` lists them with distances) within about 1.5 mm of it.
6. **It looks designed.** Parts of one function together, same-size parts in aligned rows, nothing scattered. The
   reviewer looks at the picture first and rejects boards whose power parts sprawl. Do not chase wire length:
   loop area, power paths and escape room matter more.

## Rules
- Only edit files `rooms/<your room>.py` (plus scratch files in `/tmp`). Do not edit the tools, the specs, other
  rooms' files or the scorecard. If a tool is wrong or missing something, say so in your report.
- Do not move parts of other rooms and do not move fixed parts. If your room is too small or the hand-off point in
  your brief does not work, place the best you can inside the room and say exactly what you need changed.
- No git commits. Never order PCBs or call any ordering service. No secrets anywhere.
- You may start sub-agents for a sub-block if it helps, but one careful pass by you is usually faster.
- `/mnt/project-files` is a network mount: never search it; you do not need it.

## What to send back
A short report: (1) the final placement file and picture paths; (2) the last scorecard run name and, for your room,
the blocked connections and open power paths that remain, with the reason for each; (3) the numbers your brief asks
for; (4) what you tried that did not work; (5) what you need from the lead or from a neighbouring room (be specific:
which part, which coordinate, which lane); (6) anything in this guide or the tools that slowed you down.
