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

## Fixed since (same day)

Points 2 to 5 are now in the gate (`spikes/02-seeded-faults/intent_check.py`) and kernel:
- `recmax`: limits files may carry `rec_max` (recommended operating maximum, page and quote); a net's normal
  voltage (`volts(..., normal=)`, else its maximum) must stay under it.
- `clamp`: a clamp's `clamp_v` must not exceed the absolute maximum of any pin on the net it protects.
- A waiver file may still carry ratings; the USB-C receptacle now has its 20 V rating.
- `across(max_v, ref)` declares the voltage across a part that has no end on ground; the capacitor rule uses it.

Replayed on task 2's conditions (25.2 V running, 26.5 V maximum, TVS2700): the gate now reports the PD controller
(22 V operating), the connector (20 V) and the clamp above the PD controller's 28 V limit. The third unseen fault
set from spike 2 still scores 49 of 60, and the original design still passes with no findings.
Still open: the review step after the gate, and design notes in block code.

## Rerun on Opus 5.5 (2026-11-11)

Logan's rule from this date: benchmarks run on Opus 5.5 subagents, because the aim is for
the infrastructure to carry a cheaper model. Same two tasks, same prompts, one run per
arm, runs isolated from each other. The gate used is the improved one (recmax, clamp,
across), so task 2 is not like for like with the first task 2 run above.

| task | arm | targets met | other set points held | wiring changed | model calls | output tokens | context read (cached) | minutes |
|---|---|---|---|---|---|---|---|---|
| 1 | old way | 6 of 6 | 10 of 10 | 0 | 27 | 17.3 k | 2.25 M | 3.1 |
| 1 | new pipeline | 6 of 6 | 10 of 10 | 0 | 16 | 9.0 k | 1.21 M | 2.6 |
| 2 | old way | 2 of 2 | 14 of 14 | 0 | 30 | 23.4 k | 3.08 M | 4.4 |
| 2 | new pipeline | 2 of 2 | 14 of 14 | 4 pins (intended) | 33 | 29.0 k | 3.79 M | 6.1 |

Task 2 detail:

| | TVS replaced | CC protector replaced | PD controller 22 V limit | TVS clamp above PD abs max | connector 20 V | build forced to pass |
|---|---|---|---|---|---|---|
| old way | yes (TVS2700) | no, left as an open problem | reported | reported | reported | n/a |
| new pipeline | yes (TVS2700) | yes (TPD4S201) | reported (gate) | reported (gate) | reported (gate) | no, stopped and said why |

What it shows:

- Task 1: same result as the stronger model, new pipeline about half the tokens of the old
  way. Both Opus agents used the RFBG term. The old-way agent chose 16.9k for charge
  current on a worst-case argument (never above 3.11 A); the new one took the nearest value.
- Task 2: both found every rating problem. The new pipeline's three unfixable ones came
  straight from gate findings, with page numbers, and the agent refused to weaken the gate
  to get a pass. That is the behaviour the gate is for.
- The old-way agent caught something the gate and every other run missed: the TPD4S201's
  absolute maximum on the CC pins is 28 V, but its tested hot-plug short-to-VBUS tolerance
  (VSTBUS_CC, datasheet electrical table) is 21.5 V. So the swap the gate accepted does not
  actually cover a CC pin shorted to 26.5 V. The limits files hold abs max and recommended
  max only. Gap to close: a third kind of limit for "tested tolerance" rows, checked like
  recmax.
- The new pipeline cost more on task 2 here (29 k against 23 k output tokens) because it
  did more: the protector swap, two new limits files and the hand-run sheet check.
- The 4 changed pins are the TPD4S201's NC pins 16/17/19/20, left floating where the old
  part's were grounded; the datasheet allows either.
- One run per arm. This is a direction, not a measurement.
