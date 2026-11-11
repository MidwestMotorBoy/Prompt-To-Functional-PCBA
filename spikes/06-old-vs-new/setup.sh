#!/bin/bash
# setup.sh <run dir> old|new : make a fresh work folder for one agent run. Needs the private Monolith material:
# SPIKE1 (design folder with blocks/), SPIKE2 (kb/limits, limitsmap.json), BB (Battery-Bank clone), KSYM (KiCad symbols).
set -e
R=$(realpath -m "$1"); H=$(dirname "$(realpath "$0")"); mkdir -p "$R"
if [ "$2" = old ]; then
  cp -r "$BB/hardware/Production" "$R/Production"; rm -f "$R"/Production/*.kicad_pcb "$R"/Production/*-bak "$R"/Production/*.zip
  docker run --rm -u 0 -v "$R/Production":/w -w /w kicad/kicad:10.0 kicad-cli sch export netlist --format kicadsexpr -o /w/base.net Monolith.kicad_sch | tail -1
else
  mkdir -p "$R/work"; cp -r "$SPIKE1" "$R/work/design"; rm -rf "$R"/work/design/out* "$R"/work/design/__pycache__ "$R"/work/design/top_test*
  cp -r "$H/../01-blocks-as-code/tools" "$R/work/tools"; cp "$H/../02-seeded-faults/intent_check.py" "$R/work/tools/"
  cp -r "$SPIKE2/kb/limits" "$R/work/limits"; cp "$SPIKE2/limitsmap.json" "$R/work/"; cp -r "$BB/hardware/Production" "$R/work/lib"; rm -f "$R"/work/lib/*.kicad_pcb "$R"/work/lib/*.kicad_sch
  cat > "$R/work/env.sh" <<E
export SYMBOL_DIRS=$KSYM:$R/work/lib
export LIMITS_DIR=$R/work/limits LIMITS_MAP=$R/work/limitsmap.json INTENT_CHECK=$R/work/tools/intent_check.py
E
  cat > "$R/work/README.md" <<'E'
# Work folder
- `design/kernel.py`: `part`, `net`, `volts(max_v, *nets)`, `expect(name, expr, target, tol, unit, at=pin, **bind)`.
- `design/blocks/*.py`: one file per block; `design/top.py` joins them.
- `design/build.sh out`: code -> `out/netlist.json` and `out/constraints.json` -> intent gate -> KiCad sheets in
  `out/sheets` -> KiCad's netlist of the sheets compared with the code's.
- `limits/*.json`: datasheet facts per part, each with page and quote. `tools/intent_check.py`: the gate.
E
fi
echo ready "$R"
