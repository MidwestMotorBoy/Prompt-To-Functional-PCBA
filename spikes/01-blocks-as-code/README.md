# Spike 1: two Monolith blocks as code, with generated KiCad sheets

Run 2026-11-11 in the cloud container (KiCad 10.0.8 `kicad-cli` in Docker). Nothing here touched hardware.

## Question

Can the circuit live as code, one small file per block, with the KiCad schematic generated from it and proven
equal, and does a design change keep the link to the board?

## What was built

- `design/kernel.py`: a small Python kernel. Parts, nets, `u["VIN"] += net`, and the constraint declarations the
  Battery-Bank project typed into tools as lists: `serves` (which cap serves which pin), `declare` (net kind,
  current, swing), `hot_loop`, `kelvin`, `section`, `block`. `build()` writes `netlist.json` and
  `constraints.json`.
- `design/symlib.py`: reads pins straight from KiCad symbol libraries, so no symbol is ever written by script.
- `design/draw.py`: draws one KiCad sheet per block instance. Style: each IC with a net label on every pin, and
  around it "cells" (capacitor banks with a "for U403.REGN" caption, divider chains, single parts), grouped in
  titled sections.
- `tools/check.sh` and `tools/compare.py`: export KiCad's own netlist of the drawn sheets and compare it with
  the code's netlist by which pins are joined, not by net name. Exit code 1 on any difference.
- Two blocks written against it: the 3V3 rail (14 parts) and the USB port (94 parts, used twice). The block
  sources and outputs are Monolith's circuit and are held outside this public repo until Logan says they can go
  in.

## Results

| Check | Result |
|---|---|
| Code netlist against the original Monolith netlist, shared parts | 198 parts, 117 nets, 0 differences |
| KiCad's netlist of the generated sheets against the code netlist | 0 differences |
| One wire deleted from a generated sheet | check fails and names the 12 pins that fell off the net |
| Design change (one resistor value, one added capacitor per port) | exactly those changes reported; all 205 existing symbols keep their identifier; 2 new |
| Source size, USB port block | 243 lines, 17 kB (about 5 k tokens) against 516 kB for the hand-drawn `.kicad_sch` |
| Constraints declared with the circuit | 7 hot loops, 4 Kelvin pairs, 23 net declarations, 74 cap-to-pin bindings |

Mistakes the netlist comparison caught in my first draft of the blocks: four footprint library names, one pin
strap that differs between port 1 and port 2 (ADCIN1), and stacked pin numbers that the symbol reader did not
expand. None were visible by reading the code.

## Findings

1. **SKiDL was dropped as the kernel.** SKiDL 3.0 ran, but it was noisy, one documented import failed, and
   symbol pin geometry had to be read from the KiCad libraries anyway to draw sheets. The native kernel is about
   200 lines and keeps the same `part["PIN"] += net` syntax, so moving to SKiDL or Zener later stays possible.
   This changes the recommendation in `docs/research/00-synthesis.md` (stage "Circuit source of truth").
2. **Equality is cheap to prove and catches real errors.** The comparison takes seconds and is name-agnostic.
3. **The board link is by identifier, and identifiers are stable.** Symbol identifiers are derived from the
   block instance and reference, so a rebuild after a change leaves every existing one unchanged. KiCad's
   "Update PCB from Schematic" matches footprints by that identifier. The actual click in KiCad was **not**
   run: `kicad-cli` has no such command. It needs one run on a PC with the KiCad window.
4. **Sheets re-flow on a change.** Adding one capacitor moved 14 other symbols per port on the sheet (not on
   the board). A reviewer comparing two versions by eye would see movement that means nothing. The review of a
   change should be the netlist difference, with the sheet as context.
5. **A general auto-drawer was not good enough; templates and lanes were.** Logan's verdicts in order: label-on-pin
   cells "ok not great, too much floating off in space"; parts wired to a shelf under the IC "placements are super
   odd" and "way too much down wire"; then accepted as good enough to review from (2026-11-10) once the drawer had:
   - **templates** named by the block (`draw_as("buck", ...)`, `draw_as("bridge4", ...)`): input caps on VIN,
     bootstrap cap, inductor in line, feedback divider, output caps; the four-switch stage as a left-to-right
     power path with a mirrored output half bridge;
   - **lanes**: every IC pin with passives fans out, without crossings, to its own horizontal lane; parts to
     ground hang from it, one series part sits in line and ends in a net name, a divider stands across the
     lanes it taps;
   - **inline parts**: a single part on a pin is drawn on the pin's own row;
   - every passive drawn with the IC it belongs to, whatever section the code put it in.
   All of it costs no model tokens, and the netlist check stayed at 0 differences through every rework (it
   caught one short the rework introduced).
6. **Reference for quality: the Battery-Bank sheets.** They read well because each block was laid out once with
   real coordinates and kept. A library block should carry its reviewed drawing; templates cover new blocks.

## Not done

- "Update PCB" click test (finding 3).
- Zener on Logan's PC as the runner-up kernel.
- Differential caps drawn across a sense pair; connector and protection area still sparse.

## Run it

```
export SYMBOL_DIRS=<KiCad symbols folder>:<project library folder>
cd design && ./build.sh out     # needs top.py and blocks/ beside it, and Docker with kicad/kicad:10.0
```

## Monolith as code (added 2026-11-11, with Logan's OK to publish)

`design/top.py` and `design/blocks/` hold the whole Monolith circuit: 285 parts, 168 nets,
0 differences from the original KiCad netlist (the four mounting holes are left out). The
limits files it is checked against are in `../02-seeded-faults/limits/` with
`../02-seeded-faults/limitsmap.json`. Build from `design/`:

    SYMBOL_DIRS=<kicad symbols>:<Battery-Bank hardware/Production> \
    LIMITS_DIR=../../02-seeded-faults/limits LIMITS_MAP=../../02-seeded-faults/limitsmap.json ./build.sh out
