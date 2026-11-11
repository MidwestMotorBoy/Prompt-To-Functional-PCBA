# Thermal comparison inputs

Pack thermal model (`pack3d.py`, `smd.py`, `ntc.py`, `cu.py`, copied from the 2026-11-05 inner-copper study) with a
runner that takes each board's heat-source positions, routed-copper loss tiles and copper cover.

- `cu_base.json`, `cu_new.json`: per-port copper resistance and 2 mm loss tiles from the DC grid solver
  (`../lossmap.py`) for master's board and the ground-up board.
- `cu_fix.json`: the same for the ground-up board after the fix pass (final board). `cu_fix_thermalrun.json` is the
  file the `fix` thermal runs actually used (the board one step earlier; at most 0.013 mΩ different on one path).
  To repeat those runs exactly, copy it over `cu_fix.json`.
- `lossload.py` (`NTAG=new` or `fix`) writes `lossload_<tag>.json`, the copper loss at each load.
- `run_cmp.py <boards> <cases> [hours]`: boards `base`, `new`, `new_k38` (ground-up without credit for its extra
  copper cover), `fix`, `fix_k38`. Results go to `results/<board>/<case>_cmp.npz`.
- `analyze_cmp.py`: prints one `RESULT {json}` line per run and writes `results/summary.json`.

Needs numpy, scipy and pyamg (the venv of the thermal model on the PC has them).
