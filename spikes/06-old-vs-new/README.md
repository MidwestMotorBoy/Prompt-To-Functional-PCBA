# Spike 5: old way against the new pipeline (pilot)

Same task (`task.md`: three charger set points on both USB ports), same model, one run each way.
Old way: edit the KiCad sheet by script with the Battery-Bank skills (`prompt_old.md`).
New way: edit the block code, build through the intent gate (`prompt_new.md`).
`setup.sh` makes a fresh work folder, `score_task.py` scores the resulting netlist, `usage.py` reads the agent log.

| | targets met | other set points held | wiring changed | stale part numbers | model calls | output tokens | context read (cached) | minutes |
|---|---|---|---|---|---|---|---|---|
| old way | 6 of 6 | 10 of 10 | 0 | 0 | 11 | 13.0 k | 803 k | 2.3 |
| new pipeline | 6 of 6 | 10 of 10 | 0 | 0 | 8 | 7.4 k | 523 k | 1.5 |

What the pilot shows:
- Both ways got it right. A value change on a known sheet is too easy to separate them; five more runs of this
  task would mostly measure noise. The new way used about 40 % fewer output tokens and a third less context.
- Both agents, independently, found a mistake in the gate itself: the battery-regulation expectation left out
  the charger's 33 ohm internal FBG resistance (datasheet eq. 10). Fixed: the fact is in the limits file with page
  and quote and the expression is `VFB * (1 + Rtop / (Rbot + RFBG))`. The original design therefore regulates
  at 16.85 V, not the 16.90 V reported in spike 2.
- The old-way agent also updated the notes and sheet title that stated the old values and flagged a firmware
  follow-up (ICHG register against ICHG pin). The block code carries no such notes, so the new way said nothing.
  Design notes need a home in the block code.
- The new-way agent left `volts(16.8, ...)` as a conservative maximum and said so.

## Task 2: a harder change with rating traps

`task2.md`: accept a 24 V adapter (25.2 V continuous), overvoltage cut-off 26.5 V, undervoltage unchanged, and
everything that sees the input rated for it. Hidden traps the scorer knows (`task2.json`): the 22 V TVS, the CC
protector's 24 V pins, and a 25 V capacitor across the input sense resistor. One run each way, same model.

| | targets met | other set points held | TVS replaced | CC protector replaced | PD controller limit reported | model calls | output tokens | context read (cached) | minutes |
|---|---|---|---|---|---|---|---|---|---|
| old way | 2 of 2 | 14 of 14 | yes (TVS2700) | yes (TPD4S201) | yes | 23 | 26.5 k | 2.42 M | 4.8 |
| new pipeline | 2 of 2 | 14 of 14 | yes (TVS2700) | yes (TPD4S201) | yes | 17 | 21.4 k | 1.71 M | 4.4 |

Again a tie on correctness, with the new way about 20 to 30 % cheaper. Both agents chose the same replacement
parts and both refused to call the job done: the PD controller is only specified to 22 V operating, the connector
is rated 20 V, and the new TVS clamps above the PD controller's absolute maximum.

What each way did that the other did not:
- Old way reported more engineering consequences: overvoltage recovery hysteresis close to the adapter voltage,
  the protector's hot-plug short rating (21.5 V), input bulk capacitance not rechecked at 25.2 V, and that the
  input-voltage regulation point moved 0.8 % with the divider. It updated the sheet notes. It left the 25 V
  capacitor alone with the right reason (it only sees the sense voltage).
- New way left a checkable record: a limits file for the new protector with page and quote (56 of 56 facts
  verified), declared voltages raised in code, and a build that passes the gate. It changed the 25 V capacitor
  to 50 V only because the gate flags it.
- Scorer note: the old-way result still shows the protector findings because the agent changed the value but kept
  the old library symbol name; the part itself was replaced.
- One leak: the new-way agent wrote datasheet text extracts to a folder the old-way agent could reach.

## What this says about the pipeline

1. With a strong model and a small edit, the old way is not worse on correctness. The saving from code plus gate
   is real but modest (20 to 40 % of output tokens). Battery-Bank's cost was in layout, not schematic edits, so
   the cost question has to be asked again on placement and routing once those stages exist. Running 20 more
   schematic-edit runs would not change this.
2. The gate passed a design that both agents said does not work. It checks absolute maximum, not recommended
   operating range, so the PD controller at 26.5 V on a 22 V operating limit went through. Needed: recommended
   operating limits as facts, and a rule that normal operation stays inside them.
3. The gate has no rule that a clamp's clamping voltage stays under the absolute maximum of what it protects.
4. A waiver hid a real limit (the connector's 20 V rating). Waivers must still carry voltage and current ratings.
5. The capacitor rule compares rating with the net's voltage to ground. It should use the voltage across the part.
6. The review skill made the old way's answer richer. The new pipeline needs the same review step after the gate,
   and block code needs a place for design notes so they are not lost.
