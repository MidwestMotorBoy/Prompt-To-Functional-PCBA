"""gndlink.py in.kicad_pcb out.kicad_pcb pieces.json keepu.txt [--w=0.15] [--reach=3.0]: front-layer GND link for every cut-off GND group of
isl.py: a one- or two-segment track from one of the group's pads to copper of the main GND body (via, pad or front fill piece), checked
exactly against other-net pads, tracks, vias and pours (0.15 mm). The shortest clear link is added. KiCad python."""
import sys, json, math, pcbnew
mm, MM = pcbnew.FromMM, pcbnew.ToMM
A = [a for a in sys.argv[1:] if not a.startswith('--')]
OPT = dict(a[2:].split('=') for a in sys.argv[1:] if a.startswith('--') and '=' in a)
W, REACH, CLR = float(OPT.get('w', 0.15)), float(OPT.get('reach', 3.0)), 0.155
b = pcbnew.LoadBoard(A[0]); P = json.load(open(A[2])); V = pcbnew.VECTOR2I
gnd = b.FindNet('GND'); gc = gnd.GetNetCode()
def bb4(bb): return (MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom()))
obst = []
for t in b.GetTracks():
    if t.GetNetCode() == gc: continue
    if t.GetClass() == 'PCB_VIA': obst.append((bb4(t.GetBoundingBox()), t.GetEffectiveShape(pcbnew.F_Cu)))
    elif t.GetLayer() == pcbnew.F_Cu: obst.append((bb4(t.GetBoundingBox()), t.GetEffectiveShape(pcbnew.F_Cu)))
for f in b.GetFootprints():
    for p in f.Pads():
        if p.GetNetCode() != gc and p.IsOnLayer(pcbnew.F_Cu): obst.append((bb4(p.GetBoundingBox()), p.GetEffectiveShape(pcbnew.F_Cu)))
        elif p.GetNetCode() != gc and p.HasHole(): obst.append((bb4(p.GetBoundingBox()), p.GetEffectiveShape(pcbnew.F_Cu)))
SOFT = ('GND_PLANE', 'PACK_P_PLANE', '3V3_PLANE', 'GND_FILL')
for z in list(b.Zones()) + [z for f in b.GetFootprints() for z in f.Zones()]:
    if z.GetIsRuleArea():
        if z.GetDoNotAllowTracks() and z.IsOnLayer(pcbnew.F_Cu):
            ps = pcbnew.SHAPE_POLY_SET(z.Outline()); obst.append((bb4(ps.BBox()), ps))
        continue
    if z.GetNetCode() == gc or z.GetZoneName() in SOFT or not z.IsOnLayer(pcbnew.F_Cu): continue
    ps = pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(pcbnew.F_Cu))
    if ps.OutlineCount(): obst.append((bb4(ps.BBox()), ps))
outline = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(outline, False)
inside = pcbnew.SHAPE_POLY_SET(outline); inside.Deflate(mm(0.26 + W / 2), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.01))
def pip(x, y, poly):
    c = False; n = len(poly); j = n - 1
    for i in range(n):
        xi, yi = poly[i]; xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi: c = not c
        j = i
    return c
iso = P.get('GND@iso', [])
isopad = [it[2:6] for it in iso if it[0] == 'P']
isovia = [(it[2], it[3]) for it in iso if it[0] == 'V']
mainvias = [(MM(t.GetPosition().x), MM(t.GetPosition().y)) for t in b.GetTracks() if t.GetClass() == 'PCB_VIA' and t.GetNetCode() == gc]
mainvias = [v for v in mainvias if not any(math.hypot(v[0] - x, v[1] - y) < 0.05 for x, y in isovia)]
mainpoly = [p[6] for p in P['GND'] if p[0] == 0 and p[1] == 'F.C']
groups = {}
for p in P['GND']:
    if p[0] and p[1] == 'F.C': groups.setdefault(p[0], dict(polys=[], pads=[]))['polys'].append(p[6])
for gi, g in groups.items():
    xs = [q[0] for pl in g['polys'] for q in pl]; ys = [q[1] for pl in g['polys'] for q in pl]
    g['bb'] = (min(xs), min(ys), max(xs), max(ys))
    g['pads'] = [r for r in isopad if r[0] < g['bb'][2] + 0.3 and r[2] > g['bb'][0] - 0.3 and r[1] < g['bb'][3] + 0.3 and r[3] > g['bb'][1] - 0.3]
ids, done = [], 0
for gi, g in sorted(groups.items()):
    x0, y0, x1, y1 = g['bb']; x0 -= REACH; y0 -= REACH; x1 += REACH; y1 += REACH
    near = [o for o in obst if o[0][0] < x1 and o[0][2] > x0 and o[0][1] < y1 and o[0][3] > y0]
    def clear(a, c):
        if not (inside.Contains(V(mm(a[0]), mm(a[1]))) and inside.Contains(V(mm(c[0]), mm(c[1])))): return False
        seg = pcbnew.SHAPE_SEGMENT(V(mm(a[0]), mm(a[1])), V(mm(c[0]), mm(c[1])), mm(W))
        lo = (min(a[0], c[0]) - 0.4, min(a[1], c[1]) - 0.4, max(a[0], c[0]) + 0.4, max(a[1], c[1]) + 0.4)
        return not any(o[0][0] < lo[2] and o[0][2] > lo[0] and o[0][1] < lo[3] and o[0][3] > lo[1] and o[1].Collide(seg, mm(CLR)) for o in near)
    starts = []
    for a, bq, c, d in g['pads']:
        cx, cy = (a + c) / 2, (bq + d) / 2
        starts += [(cx, cy), (a + 0.1, cy), (c - 0.1, cy), (cx, bq + 0.1), (cx, d - 0.1)]
    ends = [v for v in mainvias if x0 < v[0] < x1 and y0 < v[1] < y1]
    gx0, gy0, gx1, gy1 = g['bb']
    for iy in range(int((gy1 - gy0) / 0.1) + 1):                 # anywhere well inside the group's own fill piece
        for ix in range(int((gx1 - gx0) / 0.1) + 1):
            x, y = gx0 + ix * 0.1, gy0 + iy * 0.1
            if any(pip(x, y, pl) and all(pip(x + dx, y + dy, pl) for dx, dy in ((0.15, 0), (-0.15, 0), (0, 0.15), (0, -0.15))) for pl in g['polys']): starts.append((x, y))
    st = 0.1
    for iy in range(int((y1 - y0) / st) + 1):
        for ix in range(int((x1 - x0) / st) + 1):
            x, y = x0 + ix * st, y0 + iy * st
            if any(pip(x, y, pl) and all(pip(x + dx, y + dy, pl) for dx, dy in ((0.2, 0), (-0.2, 0), (0, 0.2), (0, -0.2))) for pl in mainpoly): ends.append((x, y))
    best = None
    for s in starts:
        for e in ends:
            L = math.hypot(e[0] - s[0], e[1] - s[1])
            if (best is None or L < best[0]) and clear(s, e): best = (L, [s, e])
    if best is None:
        mids = [(x0 + ix * st, y0 + iy * st) for iy in range(int((y1 - y0) / st) + 1) for ix in range(int((x1 - x0) / st) + 1)]
        for s in starts:
            vis = [m for m in mids if math.hypot(m[0] - s[0], m[1] - s[1]) < REACH and clear(s, m)]
            for m in vis:
                l1 = math.hypot(m[0] - s[0], m[1] - s[1])
                for e in ends:
                    L = l1 + math.hypot(e[0] - m[0], e[1] - m[1])
                    if (best is None or L < best[0]) and clear(m, e): best = (L, [s, m, e])
    if best is None:
        print('group %d near (%.2f,%.2f): no clear link (%d starts, %d ends)' % (gi, g['bb'][0], g['bb'][1], len(starts), len(ends))); continue
    pts = best[1]; done += 1
    print('group %d: link %.2f mm' % (gi, best[0]), [(round(x, 3), round(y, 3)) for x, y in pts])
    for a, c in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b); t.SetStart(V(mm(a[0]), mm(a[1]))); t.SetEnd(V(mm(c[0]), mm(c[1]))); t.SetWidth(mm(W)); t.SetLayer(pcbnew.F_Cu); t.SetNet(gnd); b.Add(t); ids.append(t.m_Uuid.AsString())
print('links added', done, 'of', len(groups))
b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(A[1])
open(A[3], 'a').write(''.join(i + '\n' for i in ids))
