"""viaok.py board net x,y [x,y ...]: smallest gap from a 0.45 mm via at each point to other-net tracks, vias and pads, per layer (KiCad python)"""
import sys, pcbnew
mm, MM = pcbnew.FromMM, pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); net = sys.argv[2]
for a in sys.argv[3:]:
    x, y = [float(v) for v in a.split(',')]; pt = pcbnew.VECTOR2I(mm(x), mm(y)); c = pcbnew.SHAPE_CIRCLE(pt, mm(0.225)); worst = {}
    def chk(sh, lab, lay):
        for g in (0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3):
            if sh.Collide(c, mm(g)):
                k = lay
                if k not in worst or g < worst[k][0]: worst[k] = (g, lab)
                return
    for t in b.GetTracks():
        if t.GetNetname() == net or t.GetNetname().split('/')[-1] == net: continue
        p = t.GetPosition()
        if abs(MM(p.x) - x) > 6 or abs(MM(p.y) - y) > 6: continue
        if t.GetClass() == 'PCB_VIA': chk(t.GetEffectiveShape(pcbnew.F_Cu), 'via ' + t.GetNetname().split('/')[-1], 'all')
        else: chk(t.GetEffectiveShape(t.GetLayer()), 'trk ' + t.GetNetname().split('/')[-1], b.GetLayerName(t.GetLayer())[:3])
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() == net or p.GetNetname().split('/')[-1] == net: continue
            q = p.GetPosition()
            if abs(MM(q.x) - x) > 3 or abs(MM(q.y) - y) > 3: continue
            for l in (pcbnew.F_Cu, pcbnew.B_Cu):
                if p.IsOnLayer(l): chk(p.GetEffectiveShape(l), 'pad %s.%s' % (f.GetReference(), p.GetNumber()), b.GetLayerName(l)[:3])
    print(a, 'gap below (mm):', {k: v for k, v in sorted(worst.items())} or 'none under 0.3')
