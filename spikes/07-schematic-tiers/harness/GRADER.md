# Grading instructions

You are grading one anonymous set of generated KiCad schematic sheets for readability. Your entry folder holds
sheet2.png (3V3 Rail), sheet3.png (Cells and Gauge), sheet4.png (MCU), sheet5.png and sheet6.png (USB Port 1 and 2,
same circuit; grade them together as "USB"). 150 dpi renders. Look only at your entry folder and RUBRIC.md here.
Do not look at other entry folders or anywhere else on disk.

Read RUBRIC.md. Look at every sheet in full and in zoomed crops (Python PIL; crop and upscale regions). IMPORTANT: other graders run at the same time, so save every crop ONLY under your own folder work/<GRADER>-<ENTRY>/ (absolute path inside this blind folder; create it) and never in a shared or relative folder such as crops/ or the current directory so you see
text overlaps and wiring detail. All entries are electrically identical (285 parts, 168 nets); judge only readability.

Write your result as JSON to scores/<GRADER>-<ENTRY>.json (that is the only file you may write):
{"entry": "<ENTRY>", "grader": "<GRADER>",
 "scores": {"3V3": {"1":n,...,"8":n}, "Cells": {...}, "MCU": {...}, "USB": {...}},   (each 0-5, integers)
 "overall": n,   (0-10: how comfortable an engineer would be reviewing the whole design from these sheets)
 "best": "one sentence", "worst": ["three", "biggest", "problems"]}
Then reply with one line: the entry, your mean criterion score and overall.
