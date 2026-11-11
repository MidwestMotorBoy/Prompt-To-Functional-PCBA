"""setw.py in out net x,y width (KiCad python): set the width of the net's track that has an end at x,y."""
import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); x, y = [float(v) for v in sys.argv[4].split(',')]; M = pcbnew.ToMM; n = 0
for t in b.GetTracks():
    if t.GetClass() == 'PCB_TRACK' and t.GetNetname() == sys.argv[3] and any(abs(M(p.x) - x) < 0.01 and abs(M(p.y) - y) < 0.01 for p in (t.GetStart(), t.GetEnd())):
        t.SetWidth(pcbnew.FromMM(float(sys.argv[5]))); n += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2]); print('set', n)
