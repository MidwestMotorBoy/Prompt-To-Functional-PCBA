"""dc_tests.py: known-answer tests of the DC copper solver (tools/battery-bank/review-tools/solve.py).

Each case is a small synthetic board. Strips have a pad across the full width at each end, so the answer is
Rs * (length between pads + 1/3 mm for the spread source) / width, with Rs = 0.246 mOhm per square (2 oz).
The 45 degree track and the neck have no closed form: their reference is the solver itself on a 0.025 mm grid.
Prints the error of the old rasteriser (aa=1) and the covered-share one (aa=8) at 0.2, 0.1 and 0.05 mm grids."""
import os, subprocess, sys, json, math, tempfile
TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../tools/battery-bank/review-tools")
RS = 0.246

def board(body): return '(kicad_pcb (version 20250101) (generator "test")\n' + body + ")\n"
def pad(ref, x, y, w, h, shape="rect"):
    return (f' (footprint "T:P" (layer "F.Cu") (at {x} {y}) (property "Reference" "{ref}") (property "Value" "x")\n'
            f'  (pad "1" smd {shape} (at 0 0) (size {w} {h}) (layers "F.Cu") (net "N")))\n')
def zone(pts):
    p = " ".join(f"(xy {x} {y})" for x, y in pts)
    return f' (zone (net "N") (layers "F.Cu") (polygon (pts {p}))\n  (filled_polygon (layer "F.Cu") (pts {p})))\n'
def strip(w, dy=0.0):
    y = 20 + dy
    return board(pad("R1", 10, y, 1, w) + pad("R2", 60, y, 1, w) + zone([(9.5, y - w / 2), (60.5, y - w / 2), (60.5, y + w / 2), (9.5, y + w / 2)])), RS * (49 + 1 / 3) / w
def diag(w=1.0, L=40.0):
    a = L / math.sqrt(2)
    return board(pad("R1", 10, 10, w, w, "circle") + pad("R2", 10 + a, 10 + a, w, w, "circle")
                 + f' (segment (start 10 10) (end {10 + a} {10 + a}) (width {w}) (layer "F.Cu") (net "N"))\n'), None
def neck():
    pts = [(9.5, 18), (32.5, 18), (32.5, 19.75), (37.5, 19.75), (37.5, 18), (60.5, 18), (60.5, 22), (37.5, 22), (37.5, 20.25), (32.5, 20.25), (32.5, 22), (9.5, 22)]
    return board(pad("R1", 10, 20, 1, 4) + pad("R2", 60, 20, 1, 4) + zone(pts)), None

CASES = [("strip 2.0 mm", strip(2.0)), ("strip 1.0 mm", strip(1.0)), ("strip 0.5 mm", strip(0.5)), ("strip 0.3 mm", strip(0.3)),
         ("strip 0.5 mm, 0.037 mm off the grid", strip(0.5, 0.037)), ("track 1.0 mm at 45 degrees", diag()),
         ("4 mm strip with a 0.5 x 5 mm neck", neck())]
RUN = """
import sys, json
sys.path.insert(0, %r)
from solve import *
out = {}
for aa, res in %r:
    B = build('N', (5, 65, 5, 45), res, aa=aa)
    V, R = solve(B, padnodes(B, 'R1', ['1']), padnodes(B, 'R2', ['1']))
    out['%%d|%%g' %% (aa, res)] = R * 1e3
print(json.dumps(out))
"""
def run(text, combos):
    with tempfile.NamedTemporaryFile("w", suffix=".kicad_pcb", delete=False) as f: f.write(text)
    r = subprocess.run([sys.executable, "-c", RUN % (TOOLS, combos)], capture_output=True, text=True, env=dict(os.environ, PCB=f.name))
    os.unlink(f.name)
    if r.returncode: raise SystemExit(r.stderr[-800:])
    return json.loads(r.stdout.strip().splitlines()[-1])

if __name__ == "__main__":
    grids = (0.2, 0.1, 0.05); combos = [(aa, g) for aa in (1, 8) for g in grids]
    print("| case | reference, mOhm | old, 0.2 / 0.1 / 0.05 mm grid | new, 0.2 / 0.1 / 0.05 mm grid |\n|---|---|---|---|")
    worst = {1: 0, 8: 0}
    for name, (text, ref) in CASES:
        o = run(text, combos); src = "formula"
        if ref is None: ref = run(text, [(8, 0.025)])["8|0.025"]; src = "0.025 mm grid"
        cells = []
        for aa in (1, 8):
            e = [(o[f"{aa}|{g:g}"] / ref - 1) * 100 for g in grids]; worst[aa] = max(worst[aa], abs(e[1]))
            cells.append(" / ".join(f"{x:+.1f} %" for x in e))
        print(f"| {name} | {ref:.3f} ({src}) | {cells[0]} | {cells[1]} |")
    print(f"\nworst error at the 0.1 mm grid: old {worst[1]:.1f} %, new {worst[8]:.1f} %")
    sys.exit(1 if worst[8] > 5.0 else 0)
