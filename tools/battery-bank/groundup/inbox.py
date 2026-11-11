"""inbox.py board keep.kicad_pcb keepu.txt x0,y0,x1,y1 : nets with tracks/vias in the box; length per layer, how much is router-laid (KiCad python)"""
import sys, pcbnew, collections, math
MM = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); keep = {t.m_Uuid.AsString() for t in pcbnew.LoadBoard(sys.argv[2]).GetTracks()} | set(open(sys.argv[3]).read().split())
x0, y0, x1, y1 = [float(v) for v in sys.argv[4].split(',')]
ins = lambda p: x0 <= MM(p.x) <= x1 and y0 <= MM(p.y) <= y1
R = collections.defaultdict(lambda: collections.Counter())
for t in b.GetTracks():
    k = 'laid' if t.m_Uuid.AsString() not in keep else 'kept'
    if t.GetClass() == 'PCB_VIA':
        if ins(t.GetPosition()): R[t.GetNetname()]['via_' + k] += 1
    elif ins(t.GetStart()) or ins(t.GetEnd()):
        R[t.GetNetname()][b.GetLayerName(t.GetLayer())[:3] + '_' + k] += round(MM(t.GetLength()), 2)
for n in sorted(R): print(n, {k: round(v, 1) for k, v in sorted(R[n].items())})
