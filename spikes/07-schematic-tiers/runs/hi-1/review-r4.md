# Round 4 self-review (before this round's changes)

All six renders opened and cropped (page 1 is the root sheet with five sheet boxes, nothing to draw). make.sh: NETLIST OK;
lint 0 warnings except the MCU false positive.

| Sheet | Flow | Group | Wires vs labels | Clutter | Space | Recognisable | Annotation | Review | Mean |
|---|---|---|---|---|---|---|---|---|---|
| 3V3 Rail | 4 | 4 | 4 | 3 | 3 | 4 | 4 | 4 | 3.8 |
| Cells and Gauge | 4 | 4 | 3 | 4 | 3 | 4 | 4 | 4 | 3.8 |
| MCU | 4 | 4 | 3 | 4 | 3 | 4 | 4 | 4 | 3.8 |
| USB Port (1 and 2) | 4 | 4 | 3 | 4 | 3 | 4 | 4 | 3 | 3.6 |

Faults seen:
- 3V3: 18 mm of dead band between the buck and the bulk group, notes parked far right, the PACK_P rail symbol touches the
  note line above the bulk caps.
- Cells: the cell-input fan (BAT, VCC, PBI, VC4..VC1) is still a staircase of seven nested wires; the page has dead area at
  the right of the bottom row.
- MCU: pi network joined to RFIO/ANT_IN by labels only; lower third of the page empty.
- USB: A2 with 25 % margin; the BQ25756 feedback divider sits between the charger and the 9 V supply with no title, so it
  reads as part of the supply; charger FSW/ICHG/ILIM/TS ladder is long; PD, stage and charger tied by labels (by design).

## Five changes ranked by expected gain
1. USB on A3 / two-column power stage. Checked with areas: the three rows need about 100,000 mm2 against 86,000 mm2 usable
   on A3 at fixed symbol size, so a split gives no A3 sheet. Not done.
2. 3V3: close the dead band, notes beside the buck, move the bulk-cap heading clear of the rail symbol. Done.
3. USB: title the feedback divider so it is not mistaken for part of the supply. Done (note under the divider).
4. MCU: wire the pi network into RFIO/ANT_IN. Tried on paper: the loop needs the ANT_IN wire to run left past the NRST
   capacitor (5 mm below RSTN), so the reset network would have to move 60 mm left and the NRST wire would get long. Not done.
5. Cells cell-input fan to label stubs plus a wired filter group (as done for the lower pins in round 3). Not done: it would
   put four local filters on labels, for a modest gain.

## After round 4
| Sheet | Mean before | Mean after |
|---|---|---|
| 3V3 Rail | 3.8 | 4.0 |
| Cells and Gauge | 3.8 | 3.8 |
| MCU | 3.8 | 3.8 |
| USB Port (1 and 2) | 3.6 | 3.7 |
