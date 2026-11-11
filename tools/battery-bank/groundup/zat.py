import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
for a in sys.argv[2:]:
    x, y = [float(v) for v in a.split(',')]; pt = pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)); r = []
    for z in b.Zones():
        if z.GetIsRuleArea():
            if z.Outline().Contains(pt): r.append('RULEAREA ' + z.GetZoneName())
            continue
        for l in z.GetLayerSet().CuStack():
            if z.GetFilledPolysList(l).Contains(pt): r.append('%s[%s]@%s' % (z.GetZoneName(), z.GetNetname().split('/')[-1], b.GetLayerName(l)[:3]))
    print(a, r)
