Round {N} of 4: self-review, then improve.

Before doing anything else, grade your own current result as a strict outside reviewer would:
1. Run ./make.sh so the renders are current. Open EVERY out/render/page-*.png (crop and zoom with PIL so you can actually read text).
2. Score each sheet against every criterion in RUBRIC.md (0-5), honestly. Assume the reviewer is harsh: overlapping text, parts tied only by labels, long or crossing wires, cramped or empty areas, and odd placements all cost points.
3. Write the table and a prioritised list of the five changes that would raise the lowest scores most to review-r{N}.md in your folder.
Then make those changes, rebuild, re-check every page, and keep going until the list is done or you run out of good ideas. make.sh must still end with NETLIST OK. Update NOTES.md, then reply with a short summary and your before-scores.
