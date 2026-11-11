"""viascan.py board net x0,y0,x1,y1 [step] : sites in the box where a 0.45 via of the net clears all other-net tracks/vias/pads by >= 0.15 (KiCad python).
Prints each legal site with the largest clearance it still passes (0.15, 0.2, 0.25)."""
import sys, pcbnew
mm, MM = pcbnew.FromMM, pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); net = sys.argv[2]; x0, y0, x1, y1 = [float(v) for v in sys.argv[3].split(',')]
st = float(sys.argv[4]) if len(sys.argv) > 4 else 0.025
sh = []
for t in b.GetTracks():
    if t.GetNetname() == net: continue
    p = t.GetPosition()
    if MM(p.x) < x0 - 6 or MM(p.x) > x1 + 6 or MM(p.y) < y0 - 6 or MM(p.y) > y1 + 6: continue
    sh.append(t.GetEffectiveShape(pcbnew.F_Cu if t.GetClass() == 'PCB_VIA' else t.GetLayer()))
for f in b.GetFootprints():
    for p in f.Pads():
        if p.GetNetname() == net: continue
        q = p.GetPosition()
        if MM(q.x) < x0 - 3 or MM(q.x) > x1 + 3 or MM(q.y) < y0 - 3 or MM(q.y) > y1 + 3: continue
        for l in (pcbnew.F_Cu, pcbnew.B_Cu):
            if p.IsOnLayer(l): sh.append(p.GetEffectiveShape(l))
out = []
y = y0
while y <= y1 + 1e-9:
    x = x0
    while x <= x1 + 1e-9:
        c = pcbnew.SHAPE_CIRCLE(pcbnew.VECTOR2I(mm(x), mm(y)), mm(0.225)); best = None
        for g in (0.152, 0.2, 0.25):
            if any(s.Collide(c, mm(g)) for s in sh): break
            best = g
        if best: out.append((best, x, y))
        x += st
    y += st
out.sort(reverse=True)
print(len(out), "legal sites")
for g, x, y in sorted(out, key=lambda r: (r[2], r[1])): print("%.3f,%.3f:%.2f" % (x, y, g), end="  ")
print()
