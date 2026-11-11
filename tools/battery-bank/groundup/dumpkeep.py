"""dumpkeep.py board.kicad_pcb out.json (KiCad python)
What dumpcu.py leaves out and a router must respect: the board outline with its cut-outs, unplated holes (pegs, slots),
and rule areas (keep-outs) with what they forbid."""
import pcbnew, sys, json
b = pcbnew.LoadBoard(sys.argv[1]); MM = lambda v: round(v / 1e6, 4)
CU = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu]; LN = ['F', 'In1', 'In2', 'In3', 'In4', 'B']
def polys(ps):
    r = []
    for i in range(ps.OutlineCount()):
        o = ps.Outline(i); pts = [(MM(o.CPoint(j).x), MM(o.CPoint(j).y)) for j in range(o.PointCount())]; hs = []
        for h in range(ps.HoleCount(i)):
            hh = ps.Hole(i, h); hs.append([(MM(hh.CPoint(j).x), MM(hh.CPoint(j).y)) for j in range(hh.PointCount())])
        r.append([pts, hs])
    return r
out = dict(edge=[], npth=[], keepouts=[])
ps = pcbnew.SHAPE_POLY_SET()
ok = b.GetBoardPolygonOutlines(ps, False)
out['edge'] = polys(ps); out['edge_ok'] = bool(ok)
for f in b.GetFootprints():
    for p in f.Pads():
        if p.GetDrillSize().x > 0 and p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            s = p.GetEffectiveHoleShape(); sg = s.GetSeg()
            out['npth'].append(dict(ref=str(f.GetReference()), x1=MM(sg.A.x), y1=MM(sg.A.y), x2=MM(sg.B.x), y2=MM(sg.B.y), w=MM(s.GetWidth())))
def flag(z, *names):
    for n in names:
        if hasattr(z, n): return bool(getattr(z, n)())
    return None
ZZ = [(z, '') for z in b.Zones()] + [(z, str(f.GetReference())) for f in b.GetFootprints() for z in f.Zones()]
for z, ref in ZZ:
    if not z.GetIsRuleArea(): continue
    out['keepouts'].append(dict(name=str(z.GetZoneName()), ref=ref, layers=[n for l, n in zip(CU, LN) if z.IsOnLayer(l)], polys=polys(pcbnew.SHAPE_POLY_SET(z.Outline())),
                                notracks=flag(z, 'GetDoNotAllowTracks'), novias=flag(z, 'GetDoNotAllowVias'), nofill=flag(z, 'GetDoNotAllowZoneFills', 'GetDoNotAllowCopperPour'),
                                nopads=flag(z, 'GetDoNotAllowPads'), nofp=flag(z, 'GetDoNotAllowFootprints')))
json.dump(out, open(sys.argv[2], 'w'))
print('edge outlines', len(out['edge']), 'holes', sum(len(h) for _, h in out['edge']), 'npth', len(out['npth']), 'keepouts', len(out['keepouts']))
for k in out['keepouts']: print('  ', k['ref'], k['name'], k['layers'], 'notracks', k['notracks'], 'novias', k['novias'], 'nofill', k['nofill'])
