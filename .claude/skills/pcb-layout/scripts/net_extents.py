"""Per-net pad count, bounding box and refs — the starting point for a pour plan or high-current path sizing.

    python net_extents.py board.kicad_pcb [regex] [--min-pads N]

Coordinates are mm relative to the top-left of the board outline. The regex filters net names (case-insensitive),
e.g. "PACK|CELL|VBUS|SW[12]|GND". Run with KiCad's bundled python (needs pcbnew).
"""
import collections
import re
import sys

import pcbnew

args = [a for a in sys.argv[1:] if not a.startswith("--")]
min_pads = 1
if "--min-pads" in sys.argv:
    min_pads = int(sys.argv[sys.argv.index("--min-pads") + 1])
    args = [a for a in args if a != str(min_pads)]
board = pcbnew.LoadBoard(args[0])
pat = re.compile(args[1], re.I) if len(args) > 1 else None
bb = board.GetBoardEdgesBoundingBox()
OX, OY = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())

nets = collections.defaultdict(list)
for fp in board.GetFootprints():
    for p in fp.Pads():
        n = p.GetNetname()
        if not n or (pat and not pat.search(n)):
            continue
        q = p.GetPosition()
        nets[n].append((fp.GetReference(), pcbnew.ToMM(q.x) - OX, pcbnew.ToMM(q.y) - OY))

cls = {}
for n in nets:
    ni = board.FindNet(n)
    cls[n] = ni.GetNetClassName() if ni else ""

print(f"{'net':40} {'class':12} {'pads':>4}  {'x range':>15}  {'y range':>15}  refs")
for n in sorted(nets, key=lambda n: (-len(nets[n]), n)):
    v = nets[n]
    if len(v) < min_pads:
        continue
    xs = [x for _, x, _ in v]
    ys = [y for _, _, y in v]
    refs = sorted({r for r, _, _ in v})
    more = f" +{len(refs) - 10}" if len(refs) > 10 else ""
    print(f"{n[-40:]:40} {cls[n][:12]:12} {len(v):4d}  {min(xs):6.1f}-{max(xs):6.1f}  {min(ys):6.1f}-{max(ys):6.1f}  "
          f"{' '.join(refs[:10])}{more}")
