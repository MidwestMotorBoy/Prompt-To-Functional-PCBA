# Working guide for open-ended improvement tasks

These tasks have no natural end point. The usual failure is stopping after a small, safe change and calling it success when the result is no better than the start. Expect to work for a long time and to iterate many times.

## 1. Start

- Read the rubric and the acceptance check in full. The rubric defines "done"; the check defines what must not break.
- Write down each rubric item as a separate line you can score.
- Record a baseline: run the check, and score the starting point against every rubric item.
- List what you believe the check compares and forbids. Test each belief with a cheap experiment: make a small trial change of that kind, run the check, then revert it. Never avoid a change because you assume the check forbids it.

## 2. Build measurement first

- Before improving anything, write small reusable tools that turn each rubric item into a number or a pass/fail list of specific offences ("looks better" does not count).
- Add one command that runs the acceptance check plus all your measurements over every output.
- When you find a new kind of defect by inspection, add a measurement for it so it cannot return unnoticed.

## 3. Iterate

Repeat this loop:

1. Pick the worst-scoring rubric item or the largest defect.
2. Make one change aimed at it.
3. Run the full command: the check and all measurements, on all outputs.
4. Keep the change if the numbers improve and nothing regresses; otherwise revert it and try a different approach.

Prefer bold changes that fix a whole class of defect over small cosmetic ones. Fix problems in the general solution, so every case benefits. Keep per-case tweaks in a separate, clearly labelled place, and use them only for what the general solution cannot handle.

## 4. Inspect every output

- After each meaningful change, look at every output, including those you did not intend to affect.
- Look at full detail: open the real result and examine each part of it, since a summary or excerpt hides defects.
- Compare against the baseline so you can see regressions as well as gains.

## 5. Grade honestly

- Score each rubric item as a strict reviewer who is looking for faults would score it. Cite the evidence (a measurement or a specific observation) for every score.
- If you cannot point to evidence, score the item as not met.
- Any item below full marks goes on the to-do list. Finish the whole list; a half-done list means the task is not done.

## 6. When to stop

Stop only when all of these hold:

- The acceptance check passes.
- Every rubric item is met with evidence, or you have tried at least two different approaches on it and can say exactly what blocks it.
- Your measurements show a clear improvement over the baseline on every output.
- A final full-detail pass over all outputs finds no new defects.

Running out of obvious ideas is not a reason to stop: re-read the rubric and re-inspect the outputs to find the next defect.

## 7. Report

- Baseline and final numbers for each rubric item, per output.
- What you changed, split into general changes and per-case tweaks.
- The check result, and which assumptions about it you tested.
- Everything still imperfect, untested or skipped, stated plainly.
