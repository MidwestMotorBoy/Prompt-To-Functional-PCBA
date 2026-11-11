"""near.py board x0,y0,x1,y1 [layer]: list copper items in a box (KiCad python)"""
import sys, pcbnew
MM = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); x0, y0, x1, y1 = [float(v) for v in sys.argv[2].split(",")]
lay = sys.argv[3] if len(sys.argv) > 3 else None
inb = lambda p: x0 <= MM(p.x) <= x1 and y0 <= MM(p.y) <= y1
sn = lambda n: n.split("/")[-1]
for t in b.GetTracks():
    if t.GetClass() == "PCB_VIA":
        if inb(t.GetPosition()): print("V %-14s %.3f,%.3f" % (sn(t.GetNetname()), MM(t.GetPosition().x), MM(t.GetPosition().y)))
    elif (inb(t.GetStart()) or inb(t.GetEnd())) and (lay is None or b.GetLayerName(t.GetLayer()).startswith(lay)):
        print("T %-14s %-4s %.3f,%.3f > %.3f,%.3f w%.2f" % (sn(t.GetNetname()), b.GetLayerName(t.GetLayer())[:3], MM(t.GetStart().x), MM(t.GetStart().y), MM(t.GetEnd().x), MM(t.GetEnd().y), MM(t.GetWidth())))
for f in b.GetFootprints():
    for p in f.Pads():
        if inb(p.GetPosition()) and (lay is None or p.IsOnLayer(b.GetLayerID(lay + ".Cu")) ):
            bb = p.GetBoundingBox()
            print("P %-14s %s.%s %.3f,%.3f  box %.2f %.2f %.2f %.2f" % (sn(p.GetNetname()), f.GetReference(), p.GetNumber(), MM(p.GetPosition().x), MM(p.GetPosition().y), MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom())))
