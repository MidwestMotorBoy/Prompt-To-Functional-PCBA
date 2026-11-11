"""gndrip.py in.kicad_pcb out.kicad_pcb pieces.json keep.kicad_pcb [--pad] [--dry]: GND vias for the cut-off GND groups that have no free
via site (see gndvia.py). For every group the site is chosen that needs the fewest router-laid signal routes moved; the via goes in and
each blocking route is lifted from junction to junction (pads, branches and hand copper stay), to be re-routed by the router around the
new via. Hand copper (keep board, keepu.txt), pads, pours, Kelvin and high-current nets are never moved. KiCad python."""
import sys, json, math, os, re, pcbnew
mm, MM = pcbnew.FromMM, pcbnew.ToMM
A = [a for a in sys.argv[1:] if not a.startswith('--')]
b = pcbnew.LoadBoard(A[0]); P = json.load(open(A[2]))
keep = {t.m_Uuid.AsString() for t in pcbnew.LoadBoard(A[3]).GetTracks()}
ku = os.path.join(os.path.dirname(A[3]), 'keepu.txt')
if os.path.exists(ku): keep |= set(open(ku).read().split())
INPAD, DRY = '--pad' in sys.argv, '--dry' in sys.argv
CLR, R, DR = 0.16, 0.225, 0.15
HARDNET = re.compile(r'(' + (os.environ.get('HARD') + '|' if os.environ.get('HARD') else '') + r'ACP_F|ACN_F|SRP_F|SRN_F|/SR[PN]$|PACK_P|CELL|FET_MID|VBAT_SYS|PPHV|VBUS|/SW[12]$|AC_SNS_N|BAT_SNS_P|^3V3$|HIDRV|LODRV)')
gnd = b.FindNet('GND'); gc = gnd.GetNetCode()
CU = list(b.GetEnabledLayers().CuStack())
def bb4(bb): return (MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom()))
obst, holes, TR = [], [], {}
for t in b.GetTracks():
    u = t.m_Uuid.AsString(); TR[u] = t
    soft = u not in keep and not HARDNET.search(t.GetNetname())
    if t.GetClass() == 'PCB_VIA':
        c = t.GetPosition(); holes.append((MM(c.x), MM(c.y), DR + MM(t.GetDrill()) / 2 + 0.21, u if (soft and t.GetNetCode() != gc) else None))
        if t.GetNetCode() != gc: obst.append((bb4(t.GetBoundingBox()), t.GetEffectiveShape(pcbnew.F_Cu), R + CLR, u if soft else None))
    elif t.GetNetCode() != gc:
        obst.append((bb4(t.GetBoundingBox()), t.GetEffectiveShape(t.GetLayer()), R + CLR, u if soft else None))
PADS = {}
for f in b.GetFootprints():
    for p in f.Pads():
        PADS.setdefault(p.GetNetCode(), []).append(p)
        if p.HasHole():
            c = p.GetPosition(); d = max(MM(p.GetDrillSize().x), MM(p.GetDrillSize().y))
            holes.append((MM(c.x), MM(c.y), DR + d / 2 + (0.46 if d >= 0.5 else 0.21), None))
        if p.GetNetCode() != gc:
            for l in CU:
                if p.IsOnLayer(l): obst.append((bb4(p.GetBoundingBox()), p.GetEffectiveShape(l), R + CLR, None)); break
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
            if ps.OutlineCount(): obst.append((bb4(ps.BBox()), pcbnew.SHAPE_POLY_SET(ps), R + CLR, None))
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
# ---- connectivity of one net's tracks / vias / pads, for junction-to-junction lifts
def segd(p, a, c):
    dx, dy = c[0] - a[0], c[1] - a[1]; L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)
def geom(t):
    if t.GetClass() == 'PCB_VIA':
        c = t.GetPosition(); return ('V', None, (MM(c.x), MM(c.y)), (MM(c.x), MM(c.y)), 0.225)
    a, c = t.GetStart(), t.GetEnd(); return ('T', t.GetLayer(), (MM(a.x), MM(a.y)), (MM(c.x), MM(c.y)), MM(t.GetWidth()) / 2)
def touch(g1, g2):
    if g1[0] == 'T' and g2[0] == 'T':
        if g1[1] != g2[1]: return False
        return any(segd(e, g2[2], g2[3]) < g2[4] + 0.01 for e in (g1[2], g1[3])) or any(segd(e, g1[2], g1[3]) < g1[4] + 0.01 for e in (g2[2], g2[3]))
    if g1[0] == 'V' and g2[0] == 'V': return False
    v, t = (g1, g2) if g1[0] == 'V' else (g2, g1)
    return segd(v[2], t[2], t[3]) < 0.225 + 0.01
def chain(u0, gone):
    t0 = TR[u0]; net = t0.GetNetCode()
    its = {u: geom(t) for u, t in TR.items() if t.GetNetCode() == net and u not in gone}
    pads = PADS.get(net, [])
    def npads(g):
        k = 0
        for p in pads:
            ends = [g[2]] if g[0] == 'V' else [g[2], g[3]]
            if any(p.HitTest(V(mm(e[0]), mm(e[1]))) and (g[0] == 'V' or p.IsOnLayer(g[1])) for e in ends): k += 1
        return k
    nb = {u: [w for w in its if w != u and touch(its[u], its[w])] for u in its}
    deg = {u: len(nb[u]) + npads(its[u]) for u in its}
    out, todo = {u0}, [u0]
    while todo:
        u = todo.pop()
        for w in nb[u]:
            if w in out or w in keep: continue
            if deg[w] <= 2: out.add(w); todo.append(w)
    return out
groups = {}
for p in P['GND']:
    if p[0] and p[1] in ('F.C', 'B.C'): groups.setdefault(p[0], dict(polys=[], pads=[]))['polys'].append(p[6])
isopads = [it for it in P.get('GND@iso', []) if it[0] == 'P']
for gi, g in groups.items():
    xs = [q[0] for pl in g['polys'] for q in pl]; ys = [q[1] for pl in g['polys'] for q in pl]
    g['bb'] = (min(xs), min(ys), max(xs), max(ys))
    for it in isopads:
        if it[2] < g['bb'][2] + 0.3 and it[4] > g['bb'][0] - 0.3 and it[3] < g['bb'][3] + 0.3 and it[5] > g['bb'][1] - 0.3: g['pads'].append(it[2:6])
gone, lifted_nets, done, miss = set(), {}, 0, 0
SKIPG = {int(v) for v in os.environ.get('SKIPG', '').split(',') if v}
for gi, g in sorted(groups.items()):
    if gi in SKIPG: continue
    x0, y0, x1, y1 = g['bb']
    near = [o for o in obst if o[0][0] < x1 + 1 and o[0][2] > x0 - 1 and o[0][1] < y1 + 1 and o[0][3] > y0 - 1]
    nh = [h for h in holes if x0 - 1.2 < h[0] < x1 + 1.2 and y0 - 1.2 < h[1] < y1 + 1.2]
    pc = [((a + c) / 2, (bq + d) / 2) for a, bq, c, d in g['pads']] or [((x0 + x1) / 2, (y0 + y1) / 2)]
    best = None; st = 0.05
    for iy in range(int((y1 - y0) / st) + 2):
        for ix in range(int((x1 - x0) / st) + 2):
            x, y = x0 + ix * st, y0 + iy * st
            inp = any(a + 0.1 <= x <= c - 0.1 and bq + 0.1 <= y <= d - 0.1 for a, bq, c, d in g['pads'])
            tch = any(a - 0.15 <= x <= c + 0.15 and bq - 0.15 <= y <= d + 0.15 for a, bq, c, d in g['pads'])
            if (tch and not inp) or (inp and not INPAD): continue
            if not inp and not any(pip(x, y, pl) for pl in g['polys']): continue
            pt = V(mm(x), mm(y))
            if not inside.Contains(pt) or not any(pl.Contains(pt) for pl in plane): continue
            if any(z.Outline().Contains(pt, -1, mm(R + 0.05)) for z in kos): continue
            blk, hard = set(), False
            for h in nh:
                if h[3] in gone: continue
                if math.hypot(x - h[0], y - h[1]) < h[2]:
                    if h[3] is None: hard = True; break
                    blk.add(h[3])
            if hard: continue
            circ = pcbnew.SHAPE_CIRCLE(pt, mm(0.01))
            for o in near:
                if o[3] in gone: continue
                if o[1].Collide(circ, mm(o[2] - 0.01)):
                    if o[3] is None: hard = True; break
                    blk.add(o[3])
            if hard: continue
            nets = {TR[u].GetNetname() for u in blk}
            cost = 10 * len(nets) + len(blk) + (8 if inp else 0) + min(math.hypot(x - a, y - bq) for a, bq in pc)
            if best is None or cost < best[0]: best = (cost, x, y, inp, blk, nets)
    if best is None:
        miss += 1; print('group %d: no site near (%.2f,%.2f)' % (gi, pc[0][0], pc[0][1])); continue
    cost, x, y, inp, blk, nets = best
    rm = set()
    for u in blk:
        if u not in rm and u not in gone: rm |= chain(u, gone | rm)
    for u in rm:
        lifted_nets[TR[u].GetNetname()] = lifted_nets.get(TR[u].GetNetname(), 0) + 1
    gone |= rm
    holes.append((x, y, DR + DR + 0.21, None)); done += 1
    print('group %d: via at (%.3f,%.3f)%s, moves %s (%d items)' % (gi, x, y, ' in pad' if inp else '', sorted(n.split('/')[-1] for n in nets), len(rm)))
    if not DRY:
        v = pcbnew.PCB_VIA(b); v.SetPosition(V(mm(x), mm(y))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetWidth(mm(2 * R)); v.SetDrill(mm(2 * DR)); v.SetNet(gnd); b.Add(v)
print('vias %d, no site %d, lifted' % (done, miss), {k.split('/')[-1]: v for k, v in lifted_nets.items()})
print('NETS', '|'.join(sorted('^' + re.escape(k) + '$' for k in lifted_nets)))
if not DRY:
    for u in gone: b.Remove(TR[u])
    b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(A[1])
