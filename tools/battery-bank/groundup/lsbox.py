"""lsbox.py board keep keepu x0,y0,x1,y1 [layer]: every via and track end in the box with net and laid/kept flag (KiCad python)"""
import sys, pcbnew
MM = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); keep = {t.m_Uuid.AsString() for t in pcbnew.LoadBoard(sys.argv[2]).GetTracks()} | set(open(sys.argv[3]).read().split())
x0, y0, x1, y1 = [float(v) for v in sys.argv[4].split(',')]; lay = sys.argv[5] if len(sys.argv) > 5 else None
ins = lambda p: x0 <= MM(p.x) <= x1 and y0 <= MM(p.y) <= y1
for t in b.GetTracks():
    k = 'kept' if t.m_Uuid.AsString() in keep else 'laid'; n = t.GetNetname().split('/')[-1]
    if t.GetClass() == 'PCB_VIA':
        if ins(t.GetPosition()): print('VIA', n, round(MM(t.GetPosition().x), 3), round(MM(t.GetPosition().y), 3), k)
    elif ins(t.GetStart()) or ins(t.GetEnd()):
        L = b.GetLayerName(t.GetLayer())[:3]
        if lay and L != lay: continue
        print('TRK', n, L, round(MM(t.GetStart().x), 3), round(MM(t.GetStart().y), 3), round(MM(t.GetEnd().x), 3), round(MM(t.GetEnd().y), 3), MM(t.GetWidth()), k)
