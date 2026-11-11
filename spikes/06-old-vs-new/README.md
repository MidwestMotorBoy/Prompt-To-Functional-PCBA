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

Next: a task that can separate the two ways. Candidates: a structural change (add input reverse-polarity
protection to the port, wiring and parts), or a change with a trap the gate is meant to catch (raise the input
range so a capacitor or pin rating is exceeded).
