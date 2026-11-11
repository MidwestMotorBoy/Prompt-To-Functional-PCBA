# Check of the paper figures the synthesis leans on

Done 2026-11-11 by the lead session, after the five reports. arXiv PDFs could not be downloaded here (the
host is blocked for direct download), so each paper was read again through the fetch tool with a narrow
question that asked for table numbers and exact cell values, and "not found" where a figure was absent. This
is better than the first pass and still not the same as reading the PDF. Logan can open the links to confirm.

| Claim used in the reports | Paper | Result |
|---|---|---|
| Freerouting clears 0.80 of small and 0.78 of larger real boards; GPT-5.4 driving the router clears 0.65 and 0.00; KiCadRoutingTools 0.74 and 0.20 | PCBWorld, [arXiv 2607.05915](https://arxiv.org/abs/2607.05915), Table 3, column CP | **Holds, with two caveats.** The "larger" split (D3-B) is only 10 boards, against 99 in the small split, so 0.78 and 0.00 rest on 10 boards. The Freerouting version (2.1.0 in report 03) is not stated in the paper text I could read |
| Not in the reports, found in the same table | Same | A reinforcement-learning policy (PPO) scored 0.82 to 0.94 on the small split, above Freerouting, and 0.38 to 0.45 on the 10-board split, below it. The abstract says it was trained only on synthetic boards. This weakens the reports' flat "no reinforcement learning": it is not needed for v1, but it is a credible later use of computer-run training |
| Best model 8 % fully correct on whole-board schematics | HWE-Bench, [arXiv 2603.18102](https://arxiv.org/abs/2603.18102), abstract | **Holds.** 8.15 % overall pass, 300 tasks, 2,914 datasheets |
| A verified part-fact knowledge file lifts hard-task pass from 2 % to 47 % | PCBSchemaGen, [arXiv 2602.00510](https://arxiv.org/abs/2602.00510) v2, Table 5 | **Holds.** Hard falls from 47.1 % to 2.0 % when the datasheet-derived knowledge graph is removed (Gemma-4-31B) |
| Error messages naming type and location lift hard-task pass from 57 % to 78 % | Same, cited in report 01 | **Not found in v2.** What v2 reports: coarser (category-level) feedback costs 20.9 points overall, pass/fail-only feedback costs 23.6 points. Direction holds, the two figures do not. They may come from v1 |
| 83 to 88 % pass on SKiDL with a verifier | Same, cited in report 01 | **Not found in v2.** Overall pass in v2 Table 3 runs from 81.3 % (open 31B model) to 94 % (GPT-5.4, Gemini 3.1 Pro). Not re-checked: that the generated code is SKiDL |
| Code with pin-name wiring 60.5 % functionally correct against 3 % for raw KiCad files | SchGen, [arXiv 2605.30345](https://arxiv.org/abs/2605.30345), Table 2 | **Holds, with a caveat.** These are for a fine-tuned 20B model. General models on the same code form scored 37 to 50 % |
| Not in the reports, found in the same table | Same | Dropping relative placement from the code form cut correctness from 60.5 % to 33 %; dropping pin-name wiring cut it to 6 %. So relative placement hints help the model as well as the drawing, which supports the drawer design in report 01 |
| Playbooks: 22 % with an expert trajectory against 7 % without | PCBInnoBench (NeurIPS 2026 poster page) | **Not re-checked** |
| Prompt optimisation fell below baseline on unseen tasks in one test | Cited in report 05 | **Not re-checked** |

## What changes

Nothing in the recommendation changes. Three statements are softened in the synthesis: the routing comparison
rests on 10 boards for the larger split; reinforcement learning is "not now" and not "never"; the 57 to 78 %
and 83 to 88 % figures should not be quoted.
