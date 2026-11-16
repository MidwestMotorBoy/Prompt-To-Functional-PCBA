# Layout team F: Fable lead, Fable workers on medium effort

Same task, starting point and scorecard as team D (Monolith board, parked hand placement, `tools/score/score_board.sh`).
Goal set by Logan: a fully routed board. All numbers are from the scorecard and KiCad 10 DRC.

## Result

| | Hand board | Team D (Opus workers) | Team F (Fable medium workers) |
|---|---|---|---|
| Placement: blocked connections | 56 of 452 | 28 of 427 | 17 of 437 |
| Placement: hot loops | 7 of 7, 6.75 nH | 7 of 7, 6.16 nH | 7 of 7, 5.79 nH |
| Placement: loss, generated copper | 1.359 W | 1.013 W | 1.009 W |
| Placement rounds | - | 2 (8 workers + 2 fixers) | 1 (7 workers) |
| **Fully routed: open connections / DRC errors** | - | 0 / 0 | **0 / 0** |
| Fully routed: open power paths | - | none | none |
| Fully routed: hot loops, own copper | - | 7 of 7, 6.30 nH | 7 of 7, 5.84 nH |
| Fully routed: loss, own copper | - | 1.845 W | **1.245 W** |

Files: `best_placement.json`, `score_placement.json`, `routed_F.kicad_pcb`, `routed_F.drc.json`, `routed_F.score.json`,
`routed_layers.png` (F, In2, In3, B side by side), `routed_top.png`, `routed_bottom.png`.

## What routing cost
Loss went from 1.009 W (placement, generated copper) to 1.245 W on the routed board:
PACK_P 0.248 to 0.381 W (signal tracks on In2 cut the pack pour; the hard straps kept it from opening),
Port 1 VBUS 0.029 to 0.078 W and Port 2 VBUS 0.047 to 0.063 W (pour pieces at the connectors are joined through single
vias and thin inner tracks, see below), GND 0.308 to 0.338 W. Hot loops did not change (5.79 to 5.84 nH).

## Things a reviewer should know
- VBUS at both USB connectors: the A9/B4 pin group is joined to the A4/B9 group by one 0.3 mm via in the connector pad
  and a 0.3 to 0.5 mm inner track. It is connected, but thin for half of the port current. A wider F.Cu or B.Cu bridge
  under the connector is the fix.
- Three 3V3 links are long thin tracks (0.15 to 0.2 mm): the Port 2 PD chip's 3V3 island reaches the main 3V3 pour by an
  In3 track of about 35 mm, and the Port 1 island by a 35 mm track through Port 2. The In3 3V3 pour is cut in three by the
  ground via row at y 101 and by the Kelvin pairs. Loads are small (PD chip logic), so it works, but a planned 3V3 trunk
  would be better.
- SCL runs 21 mm down In2 at x 100.1 through the PACK_P pour (part of the PACK_P loss rise).
- 22 dead-end stubs (DRC warnings, not errors) are left from the rip-ups; a prune pass exists (`RML.prune`) but removed
  one live CELL_P link in test, so it was not applied.
- The scorecard's trial route was not run on the final board; the board itself is the route.

## How it went
1. **Placement, one round.** 7 Fable medium workers, one per room (the two stages shared one worker design), with team
   D's guide plus a "lessons from the previous team" section. Result above. The 17 blocked connections were all copper
   plan issues (Kelvin taps, thermistor pads, pins under pours), so no second placement round was run.
2. **Lead copper before the router** (`routes/lead0.py`): PACK_P straps on B and In2, 10 Kelvin taps, ground necks at
   the PD chips, two pour cuts; then 18 path-search closes of pins the router is known to wall in (`lead1`, `lead2`).
3. **Router, one run over the whole board** with full rip-up (three variants tried, best 365 of 380, 37 open, 3 errors).
   A rehearsal on team D's placement showed that tiers with `--nopre` wall in chip pins, so tiers were not used.
4. **Four Fable medium workers by region** (`CLOSE-GUIDE.md`, `tools/ml.py`, `tools/crop.py`): closed 28 of the 32
   open items with 2 DRC runs each, 0 DRC errors in every region.
5. **Lead merge and last connections**: two workers' cross-region tracks collided (SCL against EN_5V1 and SDA); solved
   with a new local rip-up tool (`tools/rip.py`), which also closed SCL at U501 and the 3V3 islands.

## Cost
Token usage from the session logs (lead up to the final score; 17 worker agents: 13 placement runs over two sessions
because of the pause, 4 closing workers):

| | Output | Cache write | Cache read | Approx. cost |
|---|---|---|---|---|
| Lead (Fable) | 0.17 M | 1.1 M | 37.9 M | $26 to $32 |
| Workers (Fable, medium) | 2.40 M | 15.2 M | 109.9 M | $270 to $361 |
| **Total** | 2.57 M | 16.3 M | 147.8 M | **$296 to $393** |

Priced at $8 / $40 per million input / output tokens and $0.20 cache read; the range is cache writes at 1.25x
(5 minute cache) or 2x (1 hour cache) the input price, which the logs do not tell apart. About a third of the worker
cost is the six placement workers that were stopped at the pause and restarted.
Wall clock: placement about 3 h of worker time, routing and closing about 4 h.

## What I would do next
1. Plan a 3V3 trunk and the VBUS bridges at the connectors as lead copper before the router.
2. Reserve an I2C / IRQ lane across the stage band (y 100 to 112) on In3 before the router: every late connection that
   had to cross it needed rip-up.
3. Give workers `tools/rip.py`; the four hard connections took the lead longer than the other 28 took the workers.
4. Try to win back the PACK_P loss: move SCL and the other In2 columns off the pack pour.
