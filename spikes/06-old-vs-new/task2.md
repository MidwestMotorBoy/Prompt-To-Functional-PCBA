# Task 2 (same words for both ways)

Customers want to charge Monolith from a 24 V DC adapter wired to a USB-C plug, on either port. The adapter can sit
at 25.2 V (24 V + 5 %) continuously. On BOTH USB ports:

1. Input overvoltage cut-off: 26.5 V, within 4 % (was 22.5 V).
2. Input undervoltage cut-off stays at 4.1 V, within 5 %.
3. Everything that can see the input voltage must be rated for 26.5 V: capacitors, protection parts and IC pins,
   including what a CC pin sees if it is shorted to VBUS in the plug.

Rules:
- Datasheets are in the datasheet folder. Use standard resistor values (E96). Keep package and tolerance.
- When a part or value changes, the part number fields (MPN, LCSC) must not be left pointing at the old part: put the
  new part number if you can confirm it from what you have, otherwise set them to `TBD`.
- If a part cannot meet the new voltage and you cannot confirm a replacement from the datasheets given, do not
  hide it and do not guess: leave it and list it as an open problem with the limit and where the datasheet says so.
- Change nothing that the task does not need. No other set point may move.
- Finish with: what you changed (values and computed set points), every open problem, and the commands you ran.
