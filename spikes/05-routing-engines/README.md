# Spike 4: which engine should route the plain signals?

Question: once power copper, sense pairs and gate drives are generated, which engine should bulk-route the rest?
Tested on the hand-routed Monolith (Battery-Bank commit 8dd9eb6), where a clean answer is known to exist.

## Test board

`strip_signals.py` keeps power copper (nets with at least 50 mm2 of pour, and GND), Kelvin sense pairs, gate drives,
switch nodes and bootstrap nets, and deletes every track, via and teardrop of the other 161 nets: 1412 segments,
176 vias, 1960 mm. KiCad counts 275 open connections on the result. Placement and power copper are the human's.

## Result

Same KiCad 10 DRC (board's own rules and `.kicad_dru`), same `score.py`, library and silkscreen messages excluded.

| board | open connections | DRC violations | track, mm | vias | on a ground plane, mm | wall time |
|---|---|---|---|---|---|---|
| hand-routed (reference) | 0 | 0 | 1960 | 176 | 19 | |
| existing Battery-Bank router (`tools/battery-bank/groundup/router.py --softnets=GND,PACK_P,3V3`) | 33 of 275 | 5 | 1945 | 200 | 0 | 22 min |
| Freerouting 2.5.0 (after the input fixes below) | 48 of 275 | 156 | 1623 | 99 | 0 | 22 min |
| KiCadRoutingTools | not run | | | | | |

Neither engine finishes the board. The existing router gets closer and stays almost legal; Freerouting leaves more
open and breaks rules it was never told about.

- Existing router: 3 of its 5 violations are the custom "HighCurrent copper to small signals" 0.25 mm rule on
  CELL_1N, 1 dangling track end, 1 pour neck. Of its 23 failed connections, 20 report "no way even with every other
  route gone": the pads are walled in by power pours that the human routed through (PPHV, CELL_N, the I2C and CC
  nets around the PD controllers). That is the spike 3 finding again: lanes must be reserved in the power copper
  before bulk routing, not found afterwards.
- Freerouting: 91 violations are that same HighCurrent spacing rule, 17 the 0.25 mm edge margin, 16 track width
  and 14 via annular ring. The Specctra DSN file has one clearance number per class and cannot carry KiCad custom
  rules, so the engine cannot see them. It stops improving after about 11 passes (46 to 63 open, oscillating).

## What it took to make Freerouting usable (and what DSN loses)

Out of the box Freerouting did not converge at all on this board (651 of 780 "unrouted", 3163 violations after 18
passes). Four things had to be fixed in the DSN, all in `dsn_only_nets.py`:

1. It does not treat a pad inside an outer-layer pour as connected, so every poured power net arrives as open
   connections. Fix: empty the pin list of every net that is not to be routed.
2. Existing copper of those nets then counts as fragments to join. Fix: give every kept track, via and pour its own
   one-item net and mark it protected.
3. Pours are hard obstacles; the hand board carries 321 mm of signal through pours that KiCad refills around.
   Fix: drop the soft pours (GND, PACK_P, 3V3 on signal layers) and leftover teardrops from the DSN.
4. KiCad 10 exported 0.2 mm clearance and a 0.6 mm via although the board's rules are 0.15 mm and 0.45 mm. With the
   exported values it stalled at 168 of 283; with the real ones it reached 237.

Also lost in DSN: all net classes (everything arrives in one class), custom rules, per-layer preferences. Fan-out
had to be switched off (14 minutes of fan-out passes with nothing routed). KiCad's session import deletes every
track already on the board, so `import_ses.py` imports into a scratch copy and moves only the new tracks across.

## Existing router notes

First run treated the hand board's unnamed pours as hard obstacles and left 122 of 218 open; `--softnets` (added to
`router.py`) names nets whose pours may be crossed. Second run was confused by teardrops left from stripped tracks
(68 open); the test board now removes them.

## Not run

KiCadRoutingTools needs a Rust build of outside code, which this cloud session does not allow. FastHenry is in the
same position (spike 04).

## Conclusion

- Keep the existing router as the bulk engine. It reads KiCad rules and classes directly, respects them, and its
  failures are explainable connection by connection.
- Freerouting is not worth carrying as the main engine: equal time, fewer connections, and a lossy file format
  that needs four workarounds and still hides the custom rules. It stays useful as a second opinion on whether a
  net is routable at all.
- The 20 walled-in connections are a floorplan and power-copper problem, not a router problem. Next step for the
  flow: generate power copper with declared lanes, then judge the floorplan by a trial route with this router.

## Reproduce

```
python3 strip_signals.py hand.json hand.kicad_pcb strip.kicad_pcb
kicad-cli pcb drc --severity-all --format json -o drc_strip.json strip.kicad_pcb
python3 router.py strip.kicad_pcb drc_strip.json bb.kicad_pcb --softnets=GND,PACK_P,3V3      # KiCad python
kicad-cli pcb export specctra ... strip.dsn
python3 dsn_only_nets.py strip.dsn strip.kicad_pcb.nets.txt strip_sig.dsn GND,PACK_P,3V3 150,450
java -jar freerouting-2.5.0.jar -de strip_sig.dsn -do fr.ses -mt 4 -da --gui.enabled=false \
     --router.fanout.enabled=false --router.autorouter.max_passes=14
python3 import_ses.py strip.kicad_pcb fr.ses fr.kicad_pcb                                     # KiCad python
python3 score.py strip.kicad_pcb.nets.txt "hand-routed=hand.json,drc_hand.json" "existing router=bb.json,drc_bb.json" "Freerouting=fr.json,drc_fr.json"
```
