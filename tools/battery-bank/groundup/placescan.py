"""placescan.py board REF x0,y0,x1,y1 [step] (KiCad python): free spots for a two-pad F.Cu chip part REF (pad 1 = power net, pad 2 = GND).
A spot passes when the courtyard clears every other F courtyard and rule area, both pads clear other-net F copper and all vias by 0.2 mm,
the GND pad centre sits in the F GND fill, and same-net F copper of pad 1 is within 0.8 mm by a clear straight 0.2 mm track."""
import sys, math, pcbnew
mm, M = pcbnew.FromMM, pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); ref = sys.argv[2]; x0, y0, x1, y1 = [float(v) for v in sys.argv[3].split(',')]
st = float(sys.argv[4]) if len(sys.argv) > 4 else 0.1
fp = b.FindFootprintByReference(ref); pads = {p.GetNumber(): p for p in fp.Pads() if p.GetNumber()}
p1, p2 = pads['1'], pads['2']; n1, n2 = p1.GetNetname(), p2.GetNetname()
rot0 = fp.GetOrientationDegrees(); c0 = fp.GetPosition()
def loc(p):   # pad offset and half size in the footprint's own frame
    d = p.GetPosition() - c0; a = math.radians(rot0)
    lx = M(d.x) * math.cos(a) - M(d.y) * math.sin(a); ly = M(d.x) * math.sin(a) + M(d.y) * math.cos(a)
    s = p.GetSize(pcbnew.F_Cu); return lx, ly, M(s.x) / 2, M(s.y) / 2
L1, L2 = loc(p1), loc(p2)
cb = fp.GetCourtyard(pcbnew.F_Cu).BBox(); chx, chy = M(cb.GetWidth()) / 2, M(cb.GetHeight()) / 2
if round(rot0) % 180 == 90: chx, chy = chy, chx
def rect(cx, cy, hx, hy):
    s = pcbnew.SHAPE_POLY_SET(); s.NewOutline()
    for dx, dy in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)): s.Append(mm(cx + dx), mm(cy + dy))
    return s
cyd = [f.GetCourtyard(pcbnew.F_Cu) for f in b.GetFootprints() if f.GetReference() != ref and not f.IsFlipped()]
cyd = [c for c in cyd if c.OutlineCount()]
rule = [z.Outline() for z in b.Zones() if z.GetIsRuleArea() and z.IsOnLayer(pcbnew.F_Cu)]
oth = {n1: [], n2: []}; own1 = []
for t in b.GetTracks():
    isv = t.GetClass() == 'PCB_VIA'
    if not isv and t.GetLayer() != pcbnew.F_Cu: continue
    q = t.GetPosition()
    if not (x0 - 4 < M(q.x) < x1 + 4 and y0 - 4 < M(q.y) < y1 + 4): continue
    sh = t.GetEffectiveShape(pcbnew.F_Cu)
    for n in (n1, n2):
        if t.GetNetname() != n: oth[n].append(sh)
    if t.GetNetname() == n1: own1.append((sh, [(M(q.x), M(q.y))] if isv else [(M(t.GetStart().x), M(t.GetStart().y)), (M(t.GetEnd().x), M(t.GetEnd().y))]))
for f in b.GetFootprints():
    if f.GetReference() == ref: continue
    for p in f.Pads():
        if not p.IsOnLayer(pcbnew.F_Cu): continue
        q = p.GetPosition()
        if not (x0 - 4 < M(q.x) < x1 + 4 and y0 - 4 < M(q.y) < y1 + 4): continue
        sh = p.GetEffectiveShape(pcbnew.F_Cu)
        for n in (n1, n2):
            if p.GetNetname() != n: oth[n].append(sh)
        if p.GetNetname() == n1: own1.append((sh, [(M(q.x), M(q.y))]))
gnd = [z.GetFilledPolysList(pcbnew.F_Cu) for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname() == n2 and z.IsOnLayer(pcbnew.F_Cu)]
edge = b.GetBoardEdgesBoundingBox()
res = []
y = y0
while y <= y1 + 1e-9:
    x = x0
    while x <= x1 + 1e-9:
        for rot in (0, 90, 180, 270):
            a = math.radians(rot); hx, hy = (chx, chy) if rot % 180 == 0 else (chy, chx)
            cr = rect(x, y, hx, hy)
            if any(c.Collide(cr, 0) for c in cyd) or any(r.Collide(cr, 0) for r in rule): continue
            pp = []
            for lx, ly, sx, sy in (L1, L2):
                px = x + lx * math.cos(a) + ly * math.sin(a); py = y - lx * math.sin(a) + ly * math.cos(a)
                pp.append((px, py, rect(px, py, *((sx, sy) if rot % 180 == 0 else (sy, sx)))))
            if any(s.Collide(pp[0][2], mm(0.2)) for s in oth[n1]) or any(s.Collide(pp[1][2], mm(0.2)) for s in oth[n2]): continue
            if not any(g.Contains(pcbnew.VECTOR2I(mm(pp[1][0]), mm(pp[1][1]))) for g in gnd): continue
            best = None
            for sh, pts in own1:
                for qx, qy in pts:
                    d = math.hypot(qx - pp[0][0], qy - pp[0][1])
                    if d > 1.2 or (best and d >= best[0]): continue
                    seg = pcbnew.SHAPE_SEGMENT(pcbnew.VECTOR2I(mm(pp[0][0]), mm(pp[0][1])), pcbnew.VECTOR2I(mm(qx), mm(qy)), mm(0.2))
                    if any(s.Collide(seg, mm(0.16)) for s in oth[n1]): continue
                    best = (d, qx, qy)
            if best: res.append((best[0], x, y, rot, pp[0][0], pp[0][1], best[1], best[2]))
        x += st
    y += st
res.sort()
print(len(res), 'spots')
for r in res[:25]: print('link %.2f  at %.2f,%.2f rot %d  pad1 %.3f,%.3f -> %s copper at %.3f,%.3f' % (r[0], r[1], r[2], r[3], r[4], r[5], n1, r[6], r[7]))
