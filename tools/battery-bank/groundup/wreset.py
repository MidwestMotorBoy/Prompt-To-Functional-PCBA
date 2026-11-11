"""wreset.py in out plan.json x0,y0,x1,y1 [...] (KiCad python): put the widened tracks that touch the boxes back to their routed width (plan.json from widen.py)."""
import sys, json, pcbnew
M = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); plan = json.load(open(sys.argv[3])); boxes = [[float(v) for v in a.split(',')] for a in sys.argv[4:]]; n = 0
for t in b.GetTracks():
    u = t.m_Uuid.AsString()
    if u not in plan["orig"] or t.GetClass() != 'PCB_TRACK': continue
    if any(any(x0 <= M(p.x) <= x1 and y0 <= M(p.y) <= y1 for p in (t.GetStart(), t.GetEnd(), t.GetPosition())) for x0, y0, x1, y1 in boxes):
        if M(t.GetWidth()) > plan["orig"][u] + 1e-6: print('reset %s %.2f -> %.2f at %.2f,%.2f %s' % (t.GetNetname()[-14:], M(t.GetWidth()), plan["orig"][u], M(t.GetPosition().x), M(t.GetPosition().y), b.GetLayerName(t.GetLayer())[:3])); n += 1
        t.SetWidth(pcbnew.FromMM(plan["orig"][u]))
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2]); print('reset', n)
