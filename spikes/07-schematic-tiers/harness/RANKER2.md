# Ranking instructions (round 2)

You compare ONE sheet across 12 anonymous versions of the same generated KiCad schematic, in these entry folders:
E03 E06 E08 E13 E14 E16 E18 E19 E22 E24 E27 E28. All versions are electrically identical; only the drawing differs.
Your sheet file name is given in your prompt (sheet2 = 3V3 Rail, sheet3 = Cells and Gauge, sheet4 = MCU, sheet5 =
USB Port). Read RUBRIC.md for what makes a sheet readable. Look at that one file in every listed entry folder, full
view and zoomed crops (Python PIL). Look at no other folders. Other agents run at the same time: save every crop ONLY
under work/rank2-<GRADER>-<SHEET>/ inside this folder.

Rank all 12 from most readable (1) to least (12), judging as an engineer who must review the circuit from it.
Ties are not allowed. Write JSON to scores/rank2-<GRADER>-<SHEET>.json (the only file you may write):
{"grader": "<GRADER>", "sheet": "<SHEET>", "ranking": ["Exx", ...12 entries, best first],
 "notes": {"Exx": "one short reason", ...}}
Then reply with one line: the top three and bottom three.
