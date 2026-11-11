You are working in the Prompt-To-Functional-PCBA pipeline: the circuit is Python code per block, the netlist is built
from it, an intent gate checks ratings and expected values against datasheet facts, and KiCad sheets are generated.

Work folder: `{WORK}`. Read `README.md` there first. The USB port block is `design/blocks/usb_port.py` (used twice);
its expected values are declared with `expect(...)`. Datasheets are in `{DATASHEETS}`; datasheet facts with page and
quote are in `limits/`.

Build and check with: `cd {WORK}/design && ./build.sh out` (environment is in `{WORK}/env.sh`, source it first).
The build stops if the intent gate fails, and it ends by comparing KiCad's netlist of the drawn sheets with the code's.

{TASK}

Your result is `{WORK}/design/out/netlist.json` from a build that passes. Do not read or write anything outside the work
folder and the datasheet folder; keep scratch files inside your work folder.
