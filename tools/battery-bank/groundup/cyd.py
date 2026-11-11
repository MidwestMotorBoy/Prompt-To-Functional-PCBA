"""cyd.py board ref [ref ...] (KiCad python): courtyard bounding box of each footprint."""
import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); M = pcbnew.ToMM
for r in sys.argv[2:]:
    f = b.FindFootprintByReference(r)
    for side, L in (('F', pcbnew.F_CrtYd), ('B', pcbnew.B_CrtYd)):
        c = f.GetCourtyard(L)
        if c.OutlineCount():
            bb = c.BBox(); print(r, side, round(M(bb.GetLeft()), 3), round(M(bb.GetTop()), 3), round(M(bb.GetRight()), 3), round(M(bb.GetBottom()), 3))
