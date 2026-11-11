You are working the way the Battery-Bank project was built: the KiCad schematic is the source of truth and you edit
it by script or text.

Work folder: `{WORK}` (a copy of `hardware/Production`; the USB port is the shared sheet `usb_port.kicad_sch`, used
twice). Skills are in `{SKILLS}`; read `kicad-schematic-scripting/SKILL.md` and `schematic-design-review/SKILL.md`
first. Datasheets are in `{DATASHEETS}`.

KiCad 10 runs through Docker:
`docker run --rm -u 0 -v {WORK}:/w -w /w kicad/kicad:10.0 kicad-cli sch export netlist --format kicadsexpr -o /w/result.net Monolith.kicad_sch`
(also `kicad-cli sch erc`). `base.net` is the netlist before your change.

{TASK}

Your result is `{WORK}/result.net`, exported from the edited schematic. Do not read or write anything outside the three
folders named above; keep scratch files inside your work folder.
