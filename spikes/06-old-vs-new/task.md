# Task (same words for both ways)

The pack is changing to cells that must be charged more gently. On BOTH USB ports of Monolith:

1. Battery regulation voltage: 16.4 V, within 1 % (was 16.8 V nominal).
2. Charge current limit: 3.0 A, within 5 % (was 4.2 A).
3. Input current limit: 3.25 A, within 5 % (was 5.5 A).

Rules:
- Use the charger datasheet (`datasheets/bq25756.pdf`) for the formulas. Do not change the sense resistors.
- Use standard resistor values that can be bought (E96, or E192 for 0.1 % parts). Keep package and tolerance.
- When a value changes, the part number fields (MPN, LCSC) must not be left pointing at the old part: put the new
  part number if you can find it, otherwise set them to `TBD`.
- Change nothing else. Every other set point of the port must still hold and no wiring may change.
- Finish by stating each new resistor value, the computed set point, and the commands you ran to check the result.
