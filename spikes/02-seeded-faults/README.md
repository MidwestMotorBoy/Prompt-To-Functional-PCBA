# Spike 2: seeded faults (baseline so far)

Run 2026-11-11 in the cloud container. Part 1 of the spike only: the fault injector and the score of the
checks that exist today. The part knowledge base is not built yet (see "Blocked").

## What is here

- `mutate.py`: makes wrong copies of a known-good build (`netlist.json` from spike 1). Six fault classes with a
  fixed seed: swapped IC pins, a pin moved to another net, an opened pin, a resistor value off by ten, a
  capacitor rating dropped to 6.3 V, a deleted part. Hand-written faults can be added (`--extra`).
- `score.py`: runs each gate on the good build and on every mutant and counts only new findings.

## Baseline: 60 random faults plus Monolith's 5 historical bugs

| class | n | one-pin nets | declared constraints | KiCad ERC | twin-block compare | any, without twin | any |
|---|---|---|---|---|---|---|---|
| historical | 5 | 1 | 0 | 2 | 5 | 2 | 5 |
| miswire | 10 | 1 | 0 | 1 | 10 | 1 | 10 |
| open | 10 | 10 | 2 | 7 | 10 | 10 | 10 |
| pin_swap | 10 | 0 | 2 | 3 | 9 | 3 | 10 |
| rating | 10 | 0 | 0 | 0 | 9 | 0 | 9 |
| remove | 10 | 2 | 3 | 2 | 9 | 5 | 10 |
| value | 10 | 0 | 0 | 0 | 10 | 0 | 10 |
| all | 65 | 14 | 7 | 15 | 62 | 21 | 64 |

## Reading it

1. **Today's checks catch 21 of 65 (32 %)** once the twin compare is set aside: all the opened pins, and little
   else. Wrong values and wrong ratings: 0 of 20. Moved pins: 1 of 10. Swapped pins: 3 of 10. Of the five
   historical bugs, two (the swapped TPD6S300 pins, by luck of a power pin, and the deleted wire).
2. **The twin compare looks strong and is misleading.** It catches a fault put into one of two copies of a
   block. With blocks as code both copies come from one function, so a mistake in the block lands in both and
   the compare sees nothing. It stays useful only for hand-edited copies.
3. **So the knowledge base has to carry values, ratings and pin functions.** Those are the classes nothing
   catches: a rule needs to know that a pin is an enable with a 6 V limit, or that a net reaches 21 V.
4. **A scoring trap found on the way.** The first run showed ERC catching 65 of 65. KiCad reports a ground
   symbol without a power flag once, on an arbitrary sheet, so every mutant looked like a new finding. Any
   gate score must be built on findings tied to the fault, not on a changed count.
5. The exposed-pad bug is a footprint fault; here it is only a stand-in (a changed footprint name).

Cost: 65 mutants drawn and checked in under four minutes, no LLM tokens.

## Blocked

The cloud container cannot fetch datasheets: ti.com, st.com, lcsc.com, digikey.com, mouser.com and others are
refused by the network policy. The knowledge base needs either those hosts allowed for the cloud environment
or the PDFs fetched on Logan's PC.

## Run it

```
python3 mutate.py <good build dir> muts --n 10 --seed 1 [--extra historical.json]
SYMBOL_DIRS=... python3 score.py <good build dir> muts <spike 1 design dir> --twin "USB Port 1=USB Port 2:100"
```
