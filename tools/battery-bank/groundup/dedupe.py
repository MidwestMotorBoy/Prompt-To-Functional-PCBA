"""dedupe.py in out (KiCad python): remove tracks that exactly repeat another track (same net, layer and end points) and vias stacked on a same-net via."""
import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); seen = {}; gone = 0
for t in list(b.GetTracks()):
    if t.GetClass() == 'PCB_VIA': k = ('V', t.GetNetname(), t.GetPosition().x, t.GetPosition().y)
    else:
        a, c = (t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y); k = ('T', t.GetNetname(), t.GetLayer(), min(a, c), max(a, c))
    if k in seen:
        if t.GetClass() != 'PCB_VIA' and t.GetWidth() > seen[k].GetWidth(): seen[k].SetWidth(t.GetWidth())
        b.Remove(t); gone += 1
    else: seen[k] = t
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2]); print('duplicates removed', gone)
