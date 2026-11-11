"""Drawing layout pass for the production schematic (run after make_production.py and tidy_production.py).

Moves whole blocks (everything whose anchors lie inside a rectangle) with DevBoard/tools/move_region.py, then
re-places every Reference/Value field with DevBoard/tools/place_fields.py and reports overlaps with
DevBoard/tools/check_overlaps.py. Moves are multiples of 1.27 mm so everything stays on grid. Electrical content is
unchanged: check_netlist.py must still pass afterwards.

Run: "C:/Program Files/KiCad/10.0/bin/python.exe" hardware/Production/tools/layout_production.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROD = os.path.normpath(os.path.join(HERE, ".."))
DEVTOOLS = os.path.normpath(os.path.join(PROD, "..", "DevBoard", "tools"))
PY = sys.executable
G = 1.27

# (x0, y0, x1, y1, dx, dy) in mm, applied in order
MOVES = {
    "gauge.kicad_sch": [
        # pack-wire pads J111/J110/J109/J108 into a 10.16 mm column under J112 (they kept the holders' spacing)
        (20, 72, 62, 88, 0, -12 * G),
        (20, 98, 62, 112, 0, -24 * G),
        (20, 123, 62, 136, 0, -36 * G),
        (20, 136, 62, 150, 0, -34 * G),
        # cell NTC pads beside the pack-wire column
        (64, 128, 112, 172, 0, -56 * G),
        # low-side current sense up into the gap
        (38, 195, 135, 240, 0, -70 * G),
        # test / training pads row and its heading under it
        (125, 250, 290, 278, -74 * G, -74 * G),
        (35, 244, 90, 254, 0, -74 * G),
    ],
    "mcu.kicad_sch": [
        # 3V3_SLEEP pull-up beside the I2C/IRQ pull-ups
        (25, 20, 95, 56, 98 * G, 116 * G),
        # MCU block left, then the SWD + GAUGE Tag-Connects next to it
        (115, 75, 227, 162, -60 * G, 0),
        (282, 78, 420, 166, -80 * G, 0),
        # notes up into the freed top right, 3V3 probe pad into the freed space
        (285, 176, 442, 226, -194 * G, 22 * G),  # notes to the wide free area bottom left
        (200, 224, 250, 244, 60 * G, -44 * G),
        (20, 70, 440, 268, 0, -40 * G),  # everything up into the empty top band
    ],
    "power.kicad_sch": [
        (35, 108, 185, 140, 0, -22 * G),   # shared bulk C208 under the 3V3 rail
        (210, 100, 356, 130, 4 * G, -36 * G),  # notes beside the rail
    ],
}
SHEETS = ["Monolith.kicad_sch", "gauge.kicad_sch", "power.kicad_sch", "mcu.kicad_sch", "usb_port.kicad_sch"]


def run(args):
    r = subprocess.run([PY] + args, cwd=PROD, capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    if r.returncode:
        sys.exit("failed: %s\n%s" % (" ".join(args), out))
    return out


def main():
    for sheet, moves in MOVES.items():
        for x0, y0, x1, y1, dx, dy in moves:
            out = run([os.path.join(DEVTOOLS, "move_region.py"), sheet] + ["%g" % v for v in (x0, y0, x1, y1)]
                      + ["%.2f" % dx, "%.2f" % dy])
            print("%-18s move (%g,%g)-(%g,%g) by (%.2f, %.2f): %s" % (sheet, x0, y0, x1, y1, dx, dy,
                                                                       out.splitlines()[-1] if out else "ok"))
    print(run([os.path.join(DEVTOOLS, "place_fields.py")] + SHEETS).splitlines()[-1])
    print(run([os.path.join(DEVTOOLS, "check_overlaps.py")] + SHEETS).splitlines()[-1])


if __name__ == "__main__":
    main()
