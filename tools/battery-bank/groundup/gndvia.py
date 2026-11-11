"""gndvia.py in.kicad_pcb out.kicad_pcb pieces.json [--pad] [--clr=0.16]: exact-geometry GND via for every cut-off GND group listed by
isl.py (front / back fill pieces that hold GND pads but have no path to the planes). Candidate centres are tried on a 0.025 mm grid
inside the group's fill pieces (and, with --pad, inside its pads); a site must clear all other-net copper on all six layers, other
holes, keep-outs and the board edge, and sit on the In1 GND plane. KiCad python."""
import sys, json, math, pcbnew
mm, MM = pcbnew.FromMM, pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); P = json.load(open(sys.argv[3]))
INPAD = '--pad' in sys.argv
CLR = float(next((a[6:] for a in sys.argv if a.startswith('--clr=')), 0.16))
R, DR = 0.225, 0.15
gnd = b.FindNet('GND'); gc = gnd.GetNetCode()
CU = list(b.GetEnabledLayers().CuStack())
obst = []   # (bbox mm, shape, need)  need = distance from via centre
holes = []  # (x, y, min centre distance)
def bb4(bb): return (MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom()))
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        c = t.GetPosition(); holes.append((MM(c.x), MM(c.y), DR + MM(t.GetDrill()) / 2 + 0.21))
        if t.GetNetCode() != gc: obst.append((bb4(t.GetBoundingBox()), t.GetEffectiveShape(pcbnew.F_Cu), R + CLR, 'via'))
    elif t.GetNetCode() != gc:
        obst.append((bb4(t.GetBoundingBox()), t.GetEffectiveShape(t.GetLayer()), R + CLR, 'trk ' + b.GetLayerName(t.GetLayer())[:3]))
for f in b.GetFootprints():
    for p in f.Pads():
        if p.HasHole():
            c = p.GetPosition(); d = max(MM(p.GetDrillSize().x), MM(p.GetDrillSize().y))
            holes.append((MM(c.x), MM(c.y), DR + d / 2 + (0.46 if d >= 0.5 else 0.21)))
        if p.GetNetCode() != gc:
            for l in CU:
                if p.IsOnLayer(l): obst.append((bb4(p.GetBoundingBox()), p.GetEffectiveShape(l), R + CLR, 'pad')); break
SOFT = ('GND_PLANE', 'PACK_P_PLANE', '3V3_PLANE', 'GND_FILL')
kos = []
for z in list(b.Zones()) + [z for f in b.GetFootprints() for z in f.Zones()]:
    if z.GetIsRuleArea():
        if z.GetDoNotAllowVias() or z.GetDoNotAllowTracks(): kos.append(z)
        continue
    if z.GetNetCode() == gc or z.GetZoneName() in SOFT: continue
    for l in CU:
        if z.IsOnLayer(l):
            ps = z.GetFilledPolysList(l)
            if ps.OutlineCount(): obst.append((bb4(ps.BBox()), pcbnew.SHAPE_POLY_SET(ps), R + CLR, 'pour ' + z.GetZoneName() + ' ' + b.GetLayerName(l)[:3]))
outline = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(outline, False)
inside = pcbnew.SHAPE_POLY_SET(outline); inside.Deflate(mm(0.26 + R), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.01))
plane = [pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(pcbnew.In1_Cu)) for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetCode() == gc and z.IsOnLayer(pcbnew.In1_Cu)]
V = pcbnew.VECTOR2I
def pip(x, y, poly):
    c = False; n = len(poly); j = n - 1
    for i in range(n):
        xi, yi = poly[i]; xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi: c = not c
        j = i
    return c
groups = {}
for p in P['GND']:
    if p[0] and p[1] in ('F.C', 'B.C'): groups.setdefault(p[0], dict(polys=[], pads=[]))['polys'].append(p[6])
# pads of each group: the iso pads that touch the group's pieces (bbox test against piece bbox)
isopads = [it for it in P.get('GND@iso', []) if it[0] == 'P']
for gi, g in groups.items():
    xs = [q[0] for pl in g['polys'] for q in pl]; ys = [q[1] for pl in g['polys'] for q in pl]
    g['bb'] = (min(xs), min(ys), max(xs), max(ys))
    for it in isopads:
        if it[2] < g['bb'][2] + 0.3 and it[4] > g['bb'][0] - 0.3 and it[3] < g['bb'][3] + 0.3 and it[5] > g['bb'][1] - 0.3: g['pads'].append(it[2:6])
done = miss = 0
for gi, g in sorted(groups.items()):
    x0, y0, x1, y1 = g['bb']
    near = [o for o in obst if o[0][0] < x1 + 1 and o[0][2] > x0 - 1 and o[0][1] < y1 + 1 and o[0][3] > y0 - 1]
    nh = [h for h in holes if x0 - 1.2 < h[0] < x1 + 1.2 and y0 - 1.2 < h[1] < y1 + 1.2]
    pc = [((a + c) / 2, (bq + d) / 2) for a, bq, c, d in g['pads']] or [((x0 + x1) / 2, (y0 + y1) / 2)]
    cands = []
    st = 0.025
    for iy in range(int((y1 - y0) / st) + 2):
        for ix in range(int((x1 - x0) / st) + 2):
            x, y = x0 + ix * st, y0 + iy * st
            inp = any(a + 0.1 <= x <= c - 0.1 and bq + 0.1 <= y <= d - 0.1 for a, bq, c, d in g['pads'])
            touch = any(a - 0.15 <= x <= c + 0.15 and bq - 0.15 <= y <= d + 0.15 for a, bq, c, d in g['pads'])
            if touch and not inp: continue                       # half on a pad: neither in the pad nor clear of it
            if inp and not INPAD: continue
            if not inp and not any(pip(x, y, pl) for pl in g['polys']): continue
            cands.append((1 if inp else 0, min(math.hypot(x - a, y - bq) for a, bq in pc), x, y))
    cands.sort(); found = None; why = {}
    for inp, d, x, y in cands:
        pt = V(mm(x), mm(y))
        if any(math.hypot(x - h[0], y - h[1]) < h[2] for h in nh): why['hole'] = why.get('hole', 0) + 1; continue
        if not inside.Contains(pt): why['edge'] = why.get('edge', 0) + 1; continue
        if not any(pl.Contains(pt) for pl in plane): why['noplane'] = why.get('noplane', 0) + 1; continue
        if any(z.Outline().Contains(pt, -1, mm(R + 0.05)) for z in kos): why['keepout'] = why.get('keepout', 0) + 1; continue
        circ = pcbnew.SHAPE_CIRCLE(pt, mm(0.01))
        hit = next((o for o in near if o[1].Collide(circ, mm(o[2] - 0.01))), None)
        if hit is not None:
            k = hit[3]; why[k] = why.get(k, 0) + 1; continue
        found = (x, y, inp); break
    if found:
        v = pcbnew.PCB_VIA(b); v.SetPosition(V(mm(found[0]), mm(found[1]))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetWidth(mm(2 * R)); v.SetDrill(mm(2 * DR)); v.SetNet(gnd); b.Add(v)
        holes.append((found[0], found[1], DR + DR + 0.21)); done += 1
        print('group %d: via at (%.3f,%.3f)%s' % (gi, found[0], found[1], ' in pad' if found[2] else ''))
    else:
        miss += 1; print('group %d: no site (%d candidates) near (%.2f,%.2f)' % (gi, len(cands), pc[0][0], pc[0][1]), why)
print('vias added %d, groups without a site %d' % (done, miss))
b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
