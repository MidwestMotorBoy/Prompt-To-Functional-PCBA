---
name: pcb-loop-and-coupling-solvers
description: Compute hot-loop and gate-loop inductance (3-D partial inductance on the real copper) and electric-field coupling from switching copper into every signal (3-D electrostatic solve) straight from a .kicad_pcb, and use the results to compare layouts, find the via that picks up noise, and score routing or placement candidates. Use when judging a switching layout, comparing two versions of a board, hunting a noisy signal, or building a cost function for an auto-router.
---

# Loop inductance and field coupling from the board file

Design rules say copper is legal. The DC solver in `pcb-copper-resistance` says what a power path loses. This
skill covers the two fast-edge questions that neither answers: **how much inductance is in each switching loop**
and **how much of each switching edge lands on each quiet signal**. Both run on the real copper of the board
file, so two layouts of the same circuit can be compared number by number.

The code is in `hardware/Production/groundup/compare/` (`peec.py`, `loops.py`, `caps.py`, `run_hot2.py`,
`run_gate3.py`, `gbox.py`, `gmerge.py`, `coup.py`, `victims.py`, `coup_post.py`, `senspair.py`, `groute.py`,
`board.py`, `sx.py`; `runfix.sh` runs all of them on one board). It needs numpy, scipy, pyamg and Pillow, no
KiCad. Every tool reads the board from the `PCB` environment variable and tags its output with `TAG`.

Nothing here has been checked against a measurement. The numbers are for comparing layouts of one circuit with
one method. They are not absolute.

## 1. Loop inductance (`peec.py`)

Method: rasterise the copper of the loop's nets layer by layer on a square grid; each pair of neighbouring cells
of one net becomes a current branch in x or y, each via a branch in z. Partial self and mutual inductances of
all branches come from the filament formula. Ideal parts close the loop: a short across the FET or IC pins, each
capacitor as its package inductance. The result is the inductance seen at the port for the current distribution
the high-frequency limit picks (inductance only, no resistance).

Settings that mattered:

| Loop | Cell | What is kept |
|---|---|---|
| Hot loop of a power stage (supply net, ground, FET or IC pads, every capacitor between the two nets within reach) | 0.3 mm | All layers of both nets in a box round the stage |
| Gate loop (driver pin, gate resistor, gate, source return to the driver) | 0.15 mm | The drive and return nets; ground only on the loop's own layer and the plane next to it, within 2 mm |

- Capacitor package inductance used: 0.3 nH 0402, 0.5 nH 0805, 0.6 nH 1210, 1.5 nH tantalum.
- **Report the per-capacitor list, not only the loop total.** For each capacitor the solver gives the board loop
  through that capacitor alone. A layout change that cuts one bulk capacitor off from its stage barely moves the
  total and takes that one line from 1.5 nH to thousands of nH.
- **Thousands of nH means no closed path inside the box.** Either the box cut the return (solver artifact) or
  the copper is cut (real fault). Find out which. One gate loop here needed both ground planes kept to close at
  all; the both-planes setting reads 5 to 15 % lower, so compare like with like.
- Memory is 8 bytes × branches². About 27 000 branches is the ceiling in a 14 GB machine and the process is
  killed without a message above it. Coarsen the cell for the largest loops (and record the cell with the
  result), run big loops one at a time.
- A solver that resumes from a result file returns the old board's numbers. Delete the result file before
  running a changed board under the same tag.

What the numbers looked like (four-switch buck-boost charger, 5×6 FET pairs, six layers):

| | Hand-routed | Script, first version | After the fix |
|---|---|---|---|
| Charger hot loops | 0.54 to 0.67 nH | 0.66 to 1.03 nH | 0.50 to 0.56 nH |
| Gate loops, sum of eight | 49 nH | 72 nH | 44 nH |

What moved them: the 100 nF capacitor at the FET pads with ground vias beside it (0.37 to 0.39 nH of board loop
against 0.78 to 0.93 nH when 1.3 to 2.3 mm away), and the high-side gate drive beside or directly over its
switch-node return (6 nH against 14 nH when it took the free way round the controller).

## 2. Field coupling (`coup.py`)

Method: a 3-D finite-difference Laplace solve in a box round one aggressor group. The switch node with its
bootstrap and high-side gate nets is set to 1 V, every other conductor within 1.5 mm to 0 V. The charge induced
on each net is its coupling capacitance to the group. Grid 0.05 mm in the plane, graded through the stack and
into the air; algebraic multigrid (pyamg) solves it in about a minute per group.

From capacitance to a voltage step on the victim:

`step = swing × Cc / (Cc + Cnode)`, with `Cnode` = the victim's own capacitors + 4 pF per IC pin + 0.1 pF per
mm of track + 2 pF.

`victims.py` sorts nets into classes (supply and driven nets are ignored, high-impedance nodes are kept) and
`coup_post.py` lists every signal over a threshold (10 mV per edge was used). Part bodies, the inductor's field
and magnetic coupling are not in the model.

**The location printout is the tool.** `WHERE='<net suffix>,<net suffix>' python coup.py` prints, for those
victims, the induced charge in 0.5 mm bins per layer. In this work every signal that took more than 10 mV did so
at **one via barrel within about 1 mm of switching copper**, or on a short stretch on the layer next to it.
Moving that via 0.3 to 1 mm fixed each one. Re-routing the whole net was never needed.

| | Hand-routed | Script, first version | After two fix passes |
|---|---|---|---|
| Signals over 10 mV per edge | 2 | 14 | 2 |
| Charger feedback pins, port 1 / port 2 | under 0.1 mV | 41 / 204 mV | 1.2 / under 0.1 mV |

## 3. Sense pairs (`senspair.py`)

Follows each Kelvin pair from the sense resistor through its filter to the IC pins and reports route length,
where the tap leaves the power copper, and the plan area enclosed between the two lines. A stacked pair (plus on
one inner layer directly over minus on the next) took one pair from 40 to 7 mm² and another from 13 to 0.6 mm².
Tap error itself is a DC question: `pcb-copper-resistance`, on a 0.05 mm grid.

## 4. Using the solvers as a design loop

- **Compare with the run before, not with a limit.** A number that moved and should not have is the finding.
- Run the loop solvers as soon as the power pours and the hot-loop capacitors exist, before signals. That is
  when the geometry is still free.
- Run coupling after every routing pass. Run it once more after the repairs: both faults of the last fix pass
  here were made by repairs.
- For a router: the solvers are too slow to sit inside a search (minutes per run), but they give the cost terms
  a router can use. The ones that worked: a cost for running within 1 mm of switching copper on the same layer
  and within 0.6 mm on the layers next to it, and no new via within 1 mm of switching copper.
- For candidate scoring: one block (a buck, a gate-drive pair) routed several ways can be solved in seconds to a
  minute each when the box is small. Untested idea: keep the best of N.

## 5. Moving the tools to another board

The physics is general. The tables are this board's. Fill in:

- stack-up heights and copper thicknesses (`peec.py` `TH`, `ZC`; `coup.py` z grid);
- hot loops: supply net, the pads that close the loop, capacitor reach (`run_hot2.py` `DEF`);
- gate loops: driver pin, gate resistor, FET, drive and return nets (`run_all_defs.py`);
- aggressor groups with their voltage swing (`coup.py` `GROUPS`) and the victim classes (`victims.py`);
- sense resistors and their tap nets (`senspair.py`).

Check each tool against a known answer first: a loop on a vendor evaluation board with a published figure, a
plate capacitor for the field solver, a hand calculation of one simple path.
