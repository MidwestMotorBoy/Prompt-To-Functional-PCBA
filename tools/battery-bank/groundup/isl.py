"""isl.py board netregex [out.json]: copper islands of a net (KiCad python). Prints every group of copper that is not joined to the
largest group: its pads, vias, track ends and zone pieces (layer, bbox)."""
import sys, re, json, pcbnew
MM = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); rx = re.compile(sys.argv[2])
CU = [l for l in b.GetEnabledLayers().CuStack()]
LN = {l: b.GetLayerName(l)[:3] for l in CU}
out = {}; EDG = []; MAIN = {}; PCS = {}
import os
PICK = dict(kv.split(':') for kv in os.environ.get('PICK', '').split(',') if kv)
for code, net in b.GetNetsByNetcode().items():
    name = net.GetNetname()
    if code == 0 or not rx.search(name): continue
    items = []   # (kind, label, layers, {layer: shape}, bbox)
    def bbx(bb, g=0.02): return (MM(bb.GetLeft()) - g, MM(bb.GetTop()) - g, MM(bb.GetRight()) + g, MM(bb.GetBottom()) + g)
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetCode() != code: continue
            ls = [l for l in CU if p.IsOnLayer(l)]
            if not ls: continue
            items.append(('P', '%s.%s (%.2f,%.2f)' % (f.GetReference(), p.GetNumber(), MM(p.GetPosition().x), MM(p.GetPosition().y)), ls, {l: p.GetEffectiveShape(l) for l in ls}, bbx(p.GetBoundingBox()), ['P', [LN[l] for l in ls]] + list(bbx(p.GetBoundingBox(), 0.0))))
    for t in b.GetTracks():
        if t.GetNetCode() != code: continue
        if t.GetClass() == 'PCB_VIA':
            ls = CU
            items.append(('V', 'via (%.2f,%.2f)' % (MM(t.GetPosition().x), MM(t.GetPosition().y)), ls, {l: t.GetEffectiveShape(l) for l in ls}, bbx(t.GetBoundingBox()), ['V', None, MM(t.GetPosition().x), MM(t.GetPosition().y), 0.225]))
        else:
            l = t.GetLayer()
            items.append(('T', 'trk %s (%.2f,%.2f)>(%.2f,%.2f)' % (LN[l], MM(t.GetStart().x), MM(t.GetStart().y), MM(t.GetEnd().x), MM(t.GetEnd().y)), [l], {l: t.GetEffectiveShape(l)}, bbx(t.GetBoundingBox()), ['T', LN[l], MM(t.GetStart().x), MM(t.GetStart().y), MM(t.GetEnd().x), MM(t.GetEnd().y), MM(t.GetWidth()) / 2]))
    for z in b.Zones():
        if z.GetNetCode() != code or z.GetIsRuleArea(): continue
        for l in CU:
            if not z.IsOnLayer(l): continue
            ps = z.GetFilledPolysList(l)
            for i in range(ps.OutlineCount()):
                one = pcbnew.SHAPE_POLY_SET(); one.AddOutline(ps.Outline(i))
                for h in range(ps.HoleCount(i)): one.AddHole(ps.Hole(i, h))
                bb = one.BBox(); area = one.Area() / 1e12
                items.append(('Z', 'zone %s %s bbox (%.1f,%.1f)-(%.1f,%.1f) %.1f mm2' % (z.GetZoneName(), LN[l], MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom()), area), [l], {l: one}, bbx(bb)))
    n = len(items); par = list(range(n))
    def find(x):
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    # same-item layers are joined by construction (via barrel, TH pad)
    order = sorted(range(n), key=lambda i: items[i][4][0])
    for ai, i in enumerate(order):
        A = items[i]
        for j in order[ai + 1:]:
            B = items[j]
            if B[4][0] > A[4][2]: break
            if B[4][1] > A[4][3] or A[4][1] > B[4][3]: continue
            if find(i) == find(j): continue
            for l in A[2]:
                if l in B[3]:
                    if A[0] == 'Z' and B[0] == 'Z': continue
                    try: c = A[3][l].Collide(B[3][l], 1000)
                    except Exception: c = B[3][l].Collide(A[3][l], 1000)
                    if c: par[find(i)] = find(j); break
    groups = {}
    for i in range(n): groups.setdefault(find(i), []).append(i)
    gs = sorted(groups.values(), key=lambda g: -len(g))
    print('== %s: %d items, %d groups (largest %d)' % (name, n, len(gs), len(gs[0])))
    res = []
    for g in gs[1:]:
        labs = [items[i][1] for i in g]
        kinds = ''.join(sorted(items[i][0] for i in g))
        print('--', kinds[:30]); 
        for s in labs[:8]: print('    ', s)
        if len(labs) > 8: print('     ... %d more' % (len(labs) - 8))
        res.append(labs)
    out[name] = res
    # router input: one open connection per cut-off group (from its largest inner-plane piece, else one of its pads), and a
    # point inside every zone piece (group 0 = main body)
    def interior(sh):
        bb = sh.BBox(); V = pcbnew.VECTOR2I
        for st, m in ((pcbnew.FromMM(0.25), pcbnew.FromMM(0.2)), (pcbnew.FromMM(0.1), pcbnew.FromMM(0.1)), (pcbnew.FromMM(0.05), 0)):
            y = bb.GetTop() + st // 2
            while y < bb.GetBottom():
                x = bb.GetLeft() + st // 2
                while x < bb.GetRight():
                    if sh.Contains(V(x, y)) and (m == 0 or all(sh.Contains(V(x + dx, y + dy)) for dx, dy in ((m, 0), (-m, 0), (0, m), (0, -m)))):
                        return (MM(x), MM(y))
                    x += st
                y += st
        return None
    pcs = []
    for gi, g in enumerate(gs):
        best = None
        for i in g:
            if items[i][0] != 'Z': continue
            l = items[i][2][0]; sh = items[i][3][l]; p = interior(sh)
            if p is None: continue
            ar = sh.Area() / 1e12
            o = sh.Outline(0)
            pcs.append([gi, LN[l], p[0], p[1], round(ar, 1), items[i][1], [[round(MM(o.CPoint(j).x), 3), round(MM(o.CPoint(j).y), 3)] for j in range(o.PointCount())]])
            if gi and ((LN[l] in ('In2', 'In3') and ar >= 2) or (name == 'GND' and LN[l] in ('F.C', 'B.C'))) and (best is None or ar > best[0]): best = (ar, LN[l], p)
        if gi == 0: continue
        if best and 'PADSTART' not in os.environ:
            desc = 'PlanePiece %s #%d [%s]' % (best[1], gi, name); pos = dict(x=best[2][0], y=best[2][1])
        else:
            pads = [items[i] for i in g if items[i][0] == 'P'] or [items[i] for i in g if items[i][0] == 'V']
            if not pads: continue
            pk = int(PICK.get(name, 0)) % len(pads)
            lab = pads[pk][1]; xy = re.search(r'\(([-\d.]+),([-\d.]+)\)', lab)
            if pads[pk][0] == 'P':
                ref, num = lab.split(' ')[0].split('.')
                desc = 'Pad %s [%s] of %s on %s' % (num, name, ref, 'F.Cu' if pcbnew.F_Cu in pads[pk][2] else 'B.Cu')
            else: desc = 'Via [%s] on F.Cu - B.Cu' % name
            pos = dict(x=float(xy.group(1)), y=float(xy.group(2)))
        EDG.append(dict(items=[dict(description=desc, pos=pos), dict(description="Zone 'main' [%s]" % name, pos=pos)]))
    MAIN[name] = [p[1:4] for p in pcs if p[0] == 0]
    PCS[name] = pcs
    PCS[name + '@iso'] = [items[i][5] for g in gs[1:] for i in g if items[i][0] != 'Z']
if len(sys.argv) > 3:
    json.dump(out, open(sys.argv[3], 'w'), indent=0)
    json.dump(dict(unconnected_items=EDG), open(sys.argv[3].replace('.json', '_edges.json'), 'w'))
    json.dump(MAIN, open(sys.argv[3].replace('.json', '_main.json'), 'w'))
    json.dump(PCS, open(sys.argv[3].replace('.json', '_pieces.json'), 'w'))
