"""viapick.py board net x0,y0,x1,y1 [pitch=0.8] [gap=0.2] [--inpad] [--max=N] (KiCad python)
Greedy pick of new 0.45/0.3 via sites for a net inside a box: >= gap to other-net tracks, vias and pads on every layer,
>= pitch to every existing or picked via, outside same-net SMD pads unless --inpad, and inside the net's own copper
(zone fill or pad) on at least two layers. Prints a handadd spec list."""
import sys, json, pcbnew
mm, MM = pcbnew.FromMM, pcbnew.ToMM
a = [x for x in sys.argv[1:] if not x.startswith('--')]; o = dict(x[2:].split('=') if '=' in x else (x[2:], '1') for x in sys.argv[1:] if x.startswith('--'))
b = pcbnew.LoadBoard(a[0]); net = a[1]; x0, y0, x1, y1 = [float(v) for v in a[2].split(',')]
pitch = float(a[3]) if len(a) > 3 else 0.8; gap = float(a[4]) if len(a) > 4 else 0.2
CU = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu]
sh = []; vias = []; own = []; ownpad = []
for t in b.GetTracks():
    p = t.GetPosition()
    if t.GetClass() == 'PCB_VIA': vias.append((MM(p.x), MM(p.y)))
    if t.GetNetname() == net: continue
    if t.GetClass() != 'PCB_VIA':
        s, e = t.GetStart(), t.GetEnd()
        if max(MM(s.x), MM(e.x)) < x0 - 1 or min(MM(s.x), MM(e.x)) > x1 + 1 or max(MM(s.y), MM(e.y)) < y0 - 1 or min(MM(s.y), MM(e.y)) > y1 + 1: continue
    elif MM(p.x) < x0 - 1 or MM(p.x) > x1 + 1 or MM(p.y) < y0 - 1 or MM(p.y) > y1 + 1: continue
    sh.append(t.GetEffectiveShape(pcbnew.F_Cu if t.GetClass() == 'PCB_VIA' else t.GetLayer()))
for f in b.GetFootprints():
    for p in f.Pads():
        q = p.GetPosition()
        if MM(q.x) < x0 - 4 or MM(q.x) > x1 + 4 or MM(q.y) < y0 - 4 or MM(q.y) > y1 + 4: continue
        for l in CU:
            if not p.IsOnLayer(l): continue
            if p.GetNetname() == net: ownpad.append((l, p.GetEffectiveShape(l)))
            else: sh.append(p.GetEffectiveShape(l))
        if p.GetDrillSize().x > 0: vias.append((MM(q.x), MM(q.y)))
zs = [z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname() == net]
ko = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
def layers_at(pt):
    n = 0
    for l in CU:
        if any(z.IsOnLayer(l) and z.GetFilledPolysList(l).Contains(pt) for z in zs) or any(pl == l and s.Collide(pt, 0) for pl, s in ownpad): n += 1
    return n
out = []; st = 0.05; y = y0
while y <= y1 + 1e-9:
    x = x0
    while x <= x1 + 1e-9:
        pt = pcbnew.VECTOR2I(mm(x), mm(y)); c = pcbnew.SHAPE_CIRCLE(pt, mm(0.225))
        ok = all((x - vx) ** 2 + (y - vy) ** 2 >= pitch ** 2 for vx, vy in vias + out)
        ok = ok and not any(s.Collide(c, mm(gap)) for s in sh)
        ok = ok and ('inpad' in o or not any(l in (pcbnew.F_Cu, pcbnew.B_Cu) and s.Collide(c, mm(0.05)) for l, s in ownpad))
        ok = ok and not any(z.Outline().Contains(pt) for z in ko)
        ok = ok and layers_at(pt) >= 2
        if ok:
            out.append((round(x, 3), round(y, 3)))
            if 'max' in o and len(out) >= int(o['max']): break
        x += st
    if 'max' in o and len(out) >= int(o['max']): break
    y += st
print(json.dumps([{"net": net, "via": list(p)} for p in out]))
