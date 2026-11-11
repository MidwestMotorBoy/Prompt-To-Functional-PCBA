# Spike 2: seeded faults and a first knowledge-base pass

Run 2026-11-11 in the cloud container. Part 1 of the spike only: the fault injector and the score of the
checks that exist today. Part 2 is a first, pin-table-only pass at the knowledge base.

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

## Part 2: first knowledge-base pass (pin tables only)

Datasheets came from the Battery-Bank repo's `datasheets/` folder (60 PDFs), so no network was needed.

- `kb_extract.py` reads the pin table with no LLM and keeps the page and source line for every pin.
- `kb_check.py` compares each symbol pin with the datasheet name for that number, and checks ground pins.

| Datasheet | Pins read | Note |
|---|---|---|
| TPD6S300 | 20 of 21 | thermal pad has no number in the table |
| TPS62177 | 10 of 11 | same |
| TPS25751D | 38 of 39 | same |
| BQ25756 | 34 of 37 | a two-number row and the pad missed |
| TPS62933 | 8 of 8 | |
| TVS2200 | wrong | read the device-comparison table as pins; the count happened to match |
| M24512, SiZ240DT | 0 | not TI table layout |
| TPS7A4101 | | no datasheet in the folder |

Findings:

1. **Every symbol pin name agrees with the datasheet on the five parts read correctly** (about 110 pins), with
   no LLM tokens. This is the check aimed at the top historical bug source.
2. **The TVS2200 misread is why one source is not enough.** A wrong table passed the pin-count test. A second,
   independent read has to agree before a fact is accepted.
3. **It flagged the TPS25751D symbol: no pins 21, 22, 24, 25, 33, 35.** On the board the custom footprint has
   single pads 20, 23, 32, 34, so this looks like deliberately merged lands. For Logan to confirm.
4. **Pin names alone add almost nothing against the seeded faults: 2 of 65, both already caught.** Only 12 of
   the 65 faults sit on a part with facts, and a signal pin moved to the wrong net still has the right name.
5. **What is missing is intent, not more datasheet text.** To catch a wrong divider or an enable pin on a
   17 V rail the checker needs three things together: the pin's limit from the datasheet, the highest voltage
   each net can reach, and the value the block is meant to produce (for example "this divider sets 5.0 V").
   The last two belong in the block's code as declarations, next to the constraints spike 1 added.

## Next

- Declarations for net voltage range and expected values in the kernel; rules for ratings and absolute maxima.
- A second, independent read of each pin table, and absolute-maximum tables.
- Re-run this same fault set and report detection again.

## Run it

```
python3 mutate.py <good build dir> muts --n 10 --seed 1 [--extra historical.json]
SYMBOL_DIRS=... python3 score.py <good build dir> muts <spike 1 design dir> --twin "USB Port 1=USB Port 2:100"
```
