# Ground-up board against the current board: detailed comparison

Run on 2026-11-10. `base` is the hand-routed board (`Monolith.kicad_pcb` at commit 8dd9eb6, master's board
until PR #66), `new` is the first version of the ground-up board
(commit 6aaa778), `fix` is the ground-up board after the first fix pass (commit ffb0dde) and `fix2` is the board
after the second fix pass (commit dd34285), which is master's `Monolith.kicad_pcb` since PR #66. `tidy2` is `fix2` after the
cleanup pass of 2026-11-11 (branch `claude/project-thread-ploune` only; see `../README.md`, "Cleanup pass"). Every tool reads the board from the `PCB`
environment variable and tags its output with `TAG`, so all boards go through the same code. Nothing here is measured.

## Result

| Topic | Current board | Ground-up, first version | After fix pass 1 | After fix pass 2 | Ahead now |
|---|---|---|---|---|---|
| Charger hot loops, four | 0.54 to 0.67 nH | 0.66 to 1.03 nH | 0.50 to 0.56 nH | 0.50 to 0.56 nH | ground-up |
| Small buck hot loops, three | 0.53 to 1.40 nH | 0.32 to 1.22 nH | 0.31 to 1.22 nH | 0.30 to 1.22 nH | ground-up |
| Gate-drive loops, sum of eight | 49 nH (3.0 to 8.6) | 72 nH (5.0 to 14.1) | 44 nH (3.3 to 8.0) | 44 nH (3.3 to 8.0) | ground-up |
| Port 2 leg A high-side gate loop | 8.6 nH | 14.1 nH | 6.2 nH | 6.2 nH | ground-up |
| Coupling from all switch nodes into signals | 0.36 pF | 2.43 pF | 0.53 pF | 0.39 pF | level |
| Signals that take over 10 mV from one edge | 2 | 14 | 8 | 2 | level |
| Charger feedback pins, step per edge, port 1 / port 2 | under 0.1 / under 0.1 mV | 41 / 204 mV | 24 / 17 mV | 1.2 / under 0.1 mV | current |
| Largest step on a signal other than the two TS pins | 5 mV (P2 5V FB) | 223 mV (TS4) | 28 mV (EN_5V1) | 7 mV (EN_5V2) | level |
| Largest step on an I2C line | 0 mV (P2 I2CC_SDA) | 153 mV (P2 I2CC_SDA) | 26 mV (P1 I2CC_SCL) | 4 mV (P1 I2CC_SCL) | current |
| Highest current in one via | 2.6 A, 0 over 3 A | 4.3 A, 8 over 3 A | 2.3 A, 0 over 3 A | 2.3 A, 0 over 3 A | ground-up |
| Vias under the two gap-filler pads | 141 and 139 | 86 and 77 | 134 and 125 | 133 and 122 | current |
| PACK_P to the stage, port 1 / port 2 | 1.94 / 1.35 mΩ | 2.64 / 1.59 mΩ | 2.40 / 1.36 mΩ | 2.42 / 1.38 mΩ | current |
| Ground return, port 1 / port 2 | 1.60 / 1.53 mΩ | 1.91 / 1.80 mΩ | 1.44 / 1.30 mΩ | 1.42 / 1.27 mΩ | ground-up |
| Copper loss at 100 W, half charge, port 1 / port 2 | 469 / 415 mW | 490 / 416 mW | 435 / 359 mW | 435 / 358 mW | ground-up |
| Minutes at 100 W before the derate, port 1 / port 2 | 5.0 / 5.3 | 5.2 / 5.5 | 5.3 / 5.7 | 5.3 / 5.7 | level |
| Hottest part in a 100 W run, port 1 / port 2 | 59.4 / 60.2 °C | 60.2 / 61.0 °C | 58.1 / 58.9 °C | 58.1 / 58.9 °C | level |
| Kelvin tap error, four charger resistors | within 0.58 % | within 1.18 % | within 1.04 % | within 0.95 % | current |
| Kelvin tap error, gauge shunt | +1.47 % | +1.17 % | +0.82 % | +0.82 % | ground-up |
| Area enclosed by the five sense pairs | 46 mm² | 74 mm² | 74 mm² | 29 mm² | ground-up |
| Signal track cut into the ground planes | 34 mm | 0 mm | 258 mm | 258 mm | current |

After the second fix pass the ground-up board is ahead of or level with the hand-routed board on loop inductance,
copper loss, heat, via current and sense-pair area. On coupling the two are close: on both boards only the two
charger TS pins take over 10 mV from a switch-node edge, and every other signal stays under 7 mV here (EN_5V2 6.9,
port 2 5 V FB 5.9, port 2 CC2 5.4 mV) and under 6 mV on the current board. It is still behind on one thing: 258 mm
of signal track in a ground plane against 34 mm, crossed by 28 slow nets. The hand-routed board is still the one to
build first: it has been reviewed several times and keeps its planes almost whole. The ground-up board is now a
second layout without a known fault that only its author has looked at.

The second pass did not get new thermal runs. It moved two 0402 feedback resistors (R418 0.6 mm, R518 5.1 mm),
changed the copper loss at 100 W by less than 1 mW and left 255 vias under the gap-filler pads where the `fix`
runs had 259, so the `fix2` thermal lines repeat the `fix` runs (`build_page.py` aliases them).

The thermal runs of `fix` used the loss tiles of the board one step before the last (`thermal/cu_fix_thermalrun.json`).
The last step moved three signal vias and three short tracks; the tiles of the final `fix` board (`thermal/cu_fix.json`)
differ by at most 0.013 mΩ on one path (about 0.5 mW), so the runs were not repeated.

## Files

| Step | Script | Output |
|---|---|---|
| Hot loops (3-D partial inductance, 0.3 mm cells) | `run_hot2.py` | `hot_<tag>.json` |
| Gate loops (0.15 mm cells, ground kept within 2 mm of the loop) | `run_gate3.py`, `gbox.py`, `gmerge.py` | `gate3_<tag>.json` |
| Gate-drive track statistics | `groute.py` | `groute_<tag>.json` |
| Kelvin taps (DC grid solver, 0.05 mm) | `k/kelvin.py` with `RES=0.05` | `k/r05_<tag>/kelvin_<tag>.json` |
| Sense-pair routing and enclosed area | `senspair.py` | `senspair_<tag>.json` |
| Path resistance and 2 mm loss tiles | `k/lossmap.py` | `k/cu_<tag>.json` |
| Loss at each load | `thermal/lossload.py` (`NTAG`) | `thermal/lossload_<tag>.json` |
| Thermal runs (on the PC) | `thermal/run_cmp.py`, `thermal/analyze_cmp.py` | `thermal/summary_pc.json` |
| Copper cover and via counts | `custats.py` | `custats_<tag>.json` |
| Per-via current on every power path | `k/viacur.py` | `k/via_<tag>.json` |
| Time and tokens of the work, from the session logs | `worklog.py` | `worklog.json` |
| Field coupling (3-D electrostatic, 0.05 mm) | `coup.py`, `victims.py`, `coup_post.py` | `coup_<tag>.json`, `coup_sum_<tag>.json` |
| Pictures | `figs_cmp.py`, `cmap_fig.py`, `lossfig.py`; `kicad-cli pcb render` for `img/render_*.jpg` | `img/` |
| Ground-plane tracks and what crosses them | `../in4fig.py`, `../in4cross.py` | `img/in4.png`, `img/in4.json`, `in4cross.json` |
| All of the above on one more board | `runfix.sh <board> [tag]` | the `<tag>` files |
| Tidiness of signal routing (length over shortest tree, bends, short segments, vias, widths, width changes) | `PCB=<board> TAG=<tag> tidy.py`, then `tidycmp.py tag1 tag2 ...` | `tidy_<tag>.json`, `tidycmp_<tags>.json` |
| Two boards side by side over every solver result | `cmpsum.py tagA tagB` | printed |
| PACK_P path only, quick check after a hand edit | `k/pk.py` (`RES=0.05` for the fine grid) | printed |
| Page | `NTAG=fix2 build_page.py` with `page_tpl.html`, `page_text.py`, `page_words.py`, `page_fix.py` | one self-contained HTML |

`peec.py`, `loops.py`, `board.py`, `sx.py`, `run_all_defs.py` are the tools of the 2026-11-06 loop study; `k/solve.py`
and `k/run2.py` are the copper solver of the 2026-10-30 review.

## Notes on the method

- Hot loops include every capacitor between the loop's supply net and ground (within 6.1 mm of the IC for the small
  bucks) with its package inductance: 0.3 nH 0402, 0.5 nH 0805, 0.6 nH 1210, 1.5 nH tantalum.
- Gate loops keep ground copper only on the loop's own layer and the plane next to it. `gate3_<tag>_adj.json` holds
  that run for all loops. On the ground-up board this cut the ground return of the port 2 leg A low-side loop (the
  result was meaningless), so that one loop was solved on both boards with both ground planes kept (`BOTH=1`,
  `gate3b_<tag>.json`) and merged in by `gmerge.py`. The both-planes setting reads 5 to 15 % lower on the loops where
  both were run.
- Three ground-up gate loops were too large for memory at 0.15 mm and were solved at 0.175 or 0.2 mm (field `h`).
- The PACK_P paths need the 0.05 mm grid as well when a via or track was added near a narrow neck. In the second fix
  pass a signal via in a 0.85 mm neck of the bus took port 1 from 2.6 to 4.5 mΩ, and the 0.1 mm grid bridged the
  cut-out and showed nothing. `RES=0.05 PCB=<board> python k/pk.py` takes about 90 s.
- `run_gate3.py` skips loops that are already in `gate3_<tag>.json`. Delete the file (and `gate3maps_<tag>.pkl`) before
  running a changed board under a tag that was used before.
- The hot-loop result lists the board loop of every capacitor. Compare that list with the run before: a bulk capacitor
  that drops out of a loop (thousands of nH) means a plane was cut between it and the IC, which no rule check shows.
- Kelvin taps need the 0.05 mm grid. At 0.1 mm the grid bridges the 0.2 mm keep-out rings and reports errors of tens
  of percent that are not real.
- Coupling: the switch node and its bootstrap and high-side gate nets are driven together at 1 V, all other copper
  within 1.5 mm is grounded, and the charge on each net is its coupling capacitance. The step on a victim is
  swing × Cc / (Cc + Cnode), with Cnode = its capacitors + 4 pF per IC pin + 0.1 pF per mm of track + 2 pF. Part
  bodies and magnetic coupling are not in the model.
- `coup.py` with `WHERE='suffix1,suffix2'` prints, for victims whose net name ends in one of the suffixes, the
  coupled charge in 0.5 mm bins per layer. That is how the vias that picked up most of the noise were found.
- Memory: the dense inductance matrix needs about 8 bytes × branches². Above roughly 27 000 branches a run is killed
  in a 14 GB container, and two large loops cannot run side by side.
