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

## Part 3: intent declarations and datasheet limits

Added to the kernel (spike 1): `declare(net, max_v=...)` / `volts(max_v, *nets)` for the highest voltage a net
can reach, and `expect(name, expr, target, tol, unit, **bind)` for what a set of part values is meant to
produce, bound to part references and to datasheet facts:

```
expect("PP5V", "VREF * (1 + Rtop / Rbot)", 5.15, 0.03, "V", VREF="TPS62933.VREF", Rtop="R433", Rbot="R434")
```

`intent_check.py` holds four rules: capacitor rating against net voltage, IC pin absolute maximum against net
voltage, clamp working voltage against net voltage, and expected values. Limits and reference values were
read by hand from six datasheets into one file per part, each number with its page and a quote;
`intent_check.py verify` finds all 36 quotes on the page they name. The two blocks declare a voltage for 115
of 117 nets and seven expectations per port (5 V output, battery regulation voltage, input under- and
overvoltage, charge and input current limits, switching frequency). The netlist is unchanged, the good build
gives no findings, and the same 65 faults were scored again (twin compare left out):

| class | n | before | intent rules alone | now |
|---|---|---|---|---|
| historical | 5 | 2 | 1 | 3 |
| miswire | 10 | 1 | 2 | 3 |
| open | 10 | 10 | 0 | 10 |
| pin_swap | 10 | 3 | 1 | 3 |
| rating | 10 | 0 | 8 | 8 |
| remove | 10 | 5 | 4 | 7 |
| value | 10 | 0 | 2 | 2 |
| all | 65 | 21 | 18 | 36 |

Reading it:

1. **Ratings are solved by a net voltage declaration.** 8 of 10, and the two misses are not faults: a 6.3 V
   capacitor on a 5.5 V and on a 3.6 V net. The historical 18 V clamp on VBUS is caught the same way.
2. **Values are caught exactly where an expectation exists, and nowhere else.** 2 of 10. The other eight: two on
   the 9 V regulator divider (no TPS7A4101 datasheet in the folder, so no reference voltage), two on the
   thermistor divider (no expectation written), and four on pull-ups, a pull-down and sense-filter resistors,
   where ten times the value still "works" and only a behaviour rule (rise time, filter corner) would object.
3. **Wiring faults are still the gap: 14 of 20 moved or swapped pins pass.** 12 of the 14 sit on parts with no
   facts at all (the dual FET, the connector, the EEPROM, the 9 V regulator, the clamp). The voltage rule only
   sees a wrong wire when it lands on a higher-voltage net. What is missing is a function for every pin of
   every part (ground, supply, gate, feedback) and rules on it, plus binding an expectation to the pin it
   feeds, so a feedback pin moved off its divider fails.
4. **The LDO-enable historical bug is still missed, for one reason:** no datasheet for that part. A part with
   no facts must block the design, not pass quietly.
5. Cost: seconds, no LLM tokens. The declarations are 20 lines per block.

A design observation that fell out: with the charger's default feedback setting (1.536 V) the 100k / 10k
divider regulates the pack to 16.90 V, 0.6 % above 16.8 V. Within the 1 % tolerance used here, and trimmable
by register, but it is the value the board has before firmware runs.

## Part 4: ground pins, power-stage pins, expectations bound to a pin, more parts

Four additions, written after looking at what part 3 missed, so a **fresh fault set (seed 2) is the fair
score**:

- `ground`: a pin the symbol names GND, PGND, AGND or VSS must be on a 0 V net; a supply pin must not be.
- `stage`: in a declared hot loop the high-side pins must all be on the supply and the low-side pins all on
  the return (the old constraint check accepted either net for either pin, so a swapped drain and source passed).
- `expect(..., at="U404.FB")`: the pin an expectation is for must touch one of the parts that set it.
- Limits for the EEPROM, the dual FET, the small FET and the 9 V regulator (47 quotes, all found on their page).
- `nofacts`: `intent_check.py check` fails for a part with three or more pins and no limits file. On this
  design it named the 9 V regulator (no datasheet at the time) and the USB-C connector.

| class | first set (65): before | now | fresh set (60): before | now |
|---|---|---|---|---|
| historical | 2 of 5 | 4 | | |
| miswire | 1 of 10 | 7 | 5 of 10 | 7 |
| open | 10 of 10 | 10 | 10 of 10 | 10 |
| pin_swap | 3 of 10 | 10 | 6 of 10 | 8 |
| rating | 0 of 10 | 8 | 0 of 10 | 7 |
| remove | 5 of 10 | 7 | 7 of 10 | 8 |
| value | 0 of 10 | 4 | 0 of 10 | 7 |
| all | 21 of 65 | 50 | 28 of 60 | 47 |

"Before" is one-pin nets, the old constraint check and KiCad ERC. Five of the rating misses across the two
sets are not faults (6.3 V parts on nets of 5.5 V or less), so the fresh set is 47 of 57 real faults.

The "now" columns include the TPS7A4101 datasheet, which Logan added after the first run of this part
(45 of 60 and 46 of 65 without it). It gave four limits, the reference voltage for a 9 V output expectation,
and one lesson: **the historical enable bug is not a limit violation.** The enable pin is rated 60 V, so tying
it to the pack breaks nothing electrically; it only removes the off switch. What catches it is the pull-up
declaring the pin it serves (`R(..., serves="U406.EN")`), the same binding capacitors already use.

What still passes, fresh set:

1. **Signal pins moved between low-voltage nets** (EEPROM clock and data swapped, an address pin on a feedback
   node, an enable pin moved to another 5 V net). Needs pin function beyond ground and supply: a bus pin must
   meet its bus, an enable must meet what drives it.
2. **Pull-up, series and filter resistor values** (3). Ten times the value is still a legal circuit.
3. **One of six parallel bulk capacitors deleted** (2). An expectation on total capacitance would catch it.

Of the five historical bugs only the exposed-pad footprint is left, and that is a footprint check, not a
netlist one.

## Next

- Pin function per pin (bus, enable, feedback, gate) from two independent reads, and rules on it.
- A fact source for connectors (the USB Type-C pin assignment).
- Expectations for bulk capacitance and for the thermistor network.
- Then a third fresh seed.

## Run it

```
python3 mutate.py <good build dir> muts --n 10 --seed 1 [--extra historical.json]
SYMBOL_DIRS=... python3 score.py <good build dir> muts <spike 1 design dir> --twin "USB Port 1=USB Port 2:100"
python3 intent_check.py verify <limits dir> <datasheet dir>
SYMBOL_DIRS=... python3 intent_check.py score <good build dir> muts <limits dir> <kbmap.json> <spike 1 design dir>
SYMBOL_DIRS=... python3 intent_check.py check <good build dir> <limits dir> <kbmap.json> <spike 1 design dir>
```
