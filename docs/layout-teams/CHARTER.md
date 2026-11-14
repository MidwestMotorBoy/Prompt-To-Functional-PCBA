# Ground-up layout teams: charter (2026-11-14)

Logan asked to rebuild the Monolith layout from the ground up with teams of agents. Each team builds the layout skills as it goes, so a cheaper model can repeat what works. Tokens are not the constraint; correctness and skills are.

## Goal
Get a whole-board Monolith placement, plus its power copper, that:
1. **Meets every hard limit.**
   - All power paths are joined (`power_open` empty except 3V3 at L201, which is under 1 A, and the J301/J302 test GND).
   - There are 0 DRC errors.
   - All 7 hot loops pass tier 1.
2. **Routes at least as well as the hand placement.** The full trial route must reach 391 of 448 or better.
3. **Then has less ringing (tier-2 nH), then lower loss.**

Logan's priorities, in his words: hard thresholds first (a violation means the part will not work); then reduce ringing; then losses, which go with thermal spreading. Loop area and power paths matter more than wire length. Look at the renders: Logan rejected a board on sight because its power parts sprawled.

## The scorecard (the only accepted numbers)
`tools/score/score_board.sh <outdir> [placement.json | board.kicad_pcb] [--route=MIN] [--no-hot] [--keep-copper] [--plan="..."]`

It does the following, in order:
1. Applies the placement to the bare template.
2. Plans and writes the power copper.
3. Runs DRC, DC loss and thermal.
4. Renders F and B.
5. Solves the 7 hot loops.
6. Counts **blocked edges**: signal connections with no path even when nothing else is routed. It takes about 2.5 min and is the best quick screen. On the hand board it is 56, against 57 failures in the full route.
7. Runs the full trial route (45 min cap).

The results go in `<outdir>/score.json`. With no input, it scores the hand placement.

| Board | Blocked edges | Full route | Loss | Power |
|---|---|---|---|---|
| Hand placement, generated copper | 56 of 452 | 391 of 448 in 18 min | 1.36 W | PP5V open at U401 |
| Skeleton q7s2 | | 299 of 442 | 1.20 W | all joined |
| Round 3 w1_c | | 346 of 442 | 1.255 W | all joined |

## Inputs
- **Circuit:** `tools/floorplan/example/monolith/` (`netlist.json`, `constraints.json` with hot loops, near limits, Kelvin, heat; `intent.json`; `board_dump.json`).
- **The bare template board** (the hand placement, no copper): `tools/score/template/board.kicad_pcb`.
- **Fixed parts:** the J, H, TP and SW parts stay where the template has them (connectors, holes, test pads, switches), and so do the parts the cup fixes (see `tools/battery-bank/groundup/README.md`).
- **Logan's reviewed block floorplan** (one box per section and side, option r2-d with his 4 moves): `tools/floorplan/example/monolith/floorplan_r2d.json` and `.png`. Teams may deviate, but must say why.
- **Previous rounds:**
  - `tools/floorplan/team_round3/REPORT.md`: why the skeleton-first fill failed. Signal parts got stranded; 93 of 96 failures were blocked by frozen power copper and pads at the PD and port chips.
  - `tools/battery-bank/groundup/`: the earlier scripted whole-board layout, which reached a routed board.
- **Skills to read and improve:** `.claude/skills/` (pcb-scripted-placement, pcb-layout, pcb-scripted-routing, pcb-loop-and-coupling-solvers, pcb-proto-flow).

## Team structure
- Each team has a Fable lead that runs a workflow of Opus workers. Workers may start their own sub-agents.
- A 4-core container runs only 2 workflow agents at once, so keep CPU-heavy runs (router, hot loops) to about 2 at a time per container.
- Each team works on its own branch, `layout-team-<A|B|C>`, in folder `docs/layout-teams/<A|B|C>/`. It never changes shared tools in place: copy them into the team folder, or add new files.

## Deliverables per team
1. **The best placement** as `best_placement.json`, with its `score.json`, `F.png` and `B.png` from the scorecard (full route, hot loops on).
2. **`REPORT.md`:** what was tried, with numbers, what worked, and what did not.
3. **`SKILL-NOTES.md`:** the method written so a cheaper model could follow it step by step. It covers which tools to run, in what order, what to look at, and the traps.
4. **The tools**, committed and pushed to the team branch.

## Hard rules
- Never order PCBs or call any JLCPCB order, quote or cart endpoint.
- Never put secrets in chat, docs or git.
- Logan is reviewer only. Do not ask him to place parts.
- Report real numbers only, from the scorecard. Say when a route timed out.
- No model names in commits or PRs.

## Full routes on Logan's PC (16 cores, approved by Logan 2026-11-14)
`tools/score/route_server.py` runs on Logan's PC and routes up to 12 boards at once. To queue a board:
1. Copy the scorecard's `cu.kicad_pcb`, `cu.kicad_pro` and `cu.kicad_dru` to `docs/layout-teams/<team>/route_queue/<name>.kicad_pcb` (and `.kicad_pro`, `.kicad_dru`).
2. Commit and push to your team branch.

The server checks every 2 minutes. When a route finishes, it pushes the result to branch `route-results`:
`git fetch origin route-results && git show origin/route-results:<team>/<name>-<first 8 of the file's git blob sha>.json`

The result holds the routed count, failed count, total edges, minutes and status, and a `.log` beside it. Use a new name for each changed board. The router is the same one as in score_board.sh, but a route on the PC is one thread, so it is not faster per board, only many at once. Keep running the blocked-edge screen in your own container.
