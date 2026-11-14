# Ranking instructions

You compare ONE sheet across 14 anonymous versions (folders E01..E14) of the same generated KiCad schematic. All
versions are electrically identical; only the drawing differs. Your sheet file name is given in your prompt
(sheet2 = 3V3 Rail, sheet3 = Cells and Gauge, sheet4 = MCU, sheet5 = USB Port). Read RUBRIC.md for what makes a
sheet readable. Look at that one file in every entry folder, full view and zoomed crops (Python PIL). Other
agents run at the same time: save every crop ONLY under work/rank-<GRADER>-<SHEET>/ inside this folder.

Rank all 14 from most readable (1) to least (14), judging as an engineer who must review the circuit from it.
Ties are not allowed. Write JSON to scores/rank-<GRADER>-<SHEET>.json (the only file you may write):
{"grader": "<GRADER>", "sheet": "<SHEET>", "ranking": ["Exx", ...14 entries, best first],
 "notes": {"Exx": "one short reason", ...}}
Then reply with one line: the top three and bottom three.
