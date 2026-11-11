"""cross.py board x0,y0,x1,y1: tracks of any layer whose bounding box overlaps the box, vias and pads inside (KiCad python)"""
import sys, pcbnew
MM = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); x0, y0, x1, y1 = [float(v) for v in sys.argv[2].split(',')]
keep = set(open(sys.argv[3]).read().split()) if len(sys.argv) > 3 else set()
for t in b.GetTracks():
    bb = t.GetBoundingBox()
    if MM(bb.GetLeft()) > x1 or MM(bb.GetRight()) < x0 or MM(bb.GetTop()) > y1 or MM(bb.GetBottom()) < y0: continue
    k = 'K' if t.m_Uuid.AsString() in keep else ' '
    if t.GetClass() == 'PCB_VIA': print('V%s %-16s %.3f,%.3f' % (k, t.GetNetname().split('/')[-1], MM(t.GetPosition().x), MM(t.GetPosition().y)))
    else: print('T%s %-16s %s %.3f,%.3f > %.3f,%.3f w%.2f' % (k, t.GetNetname().split('/')[-1], b.GetLayerName(t.GetLayer())[:3], MM(t.GetStart().x), MM(t.GetStart().y), MM(t.GetEnd().x), MM(t.GetEnd().y), MM(t.GetWidth())))
