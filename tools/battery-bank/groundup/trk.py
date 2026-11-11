"""trk.py board netregex : list tracks/vias of nets (KiCad python)"""
import sys, re, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); rx = re.compile(sys.argv[2]); M = pcbnew.ToMM
for t in b.GetTracks():
    if not rx.search(t.GetNetname()): continue
    if t.GetClass() == "PCB_VIA": print("V  %.3f,%.3f" % (M(t.GetPosition().x), M(t.GetPosition().y)), t.GetNetname()[-12:])
    else: print("%-3s %.3f,%.3f > %.3f,%.3f w%.2f" % (b.GetLayerName(t.GetLayer())[:3], M(t.GetStart().x), M(t.GetStart().y), M(t.GetEnd().x), M(t.GetEnd().y), M(t.GetWidth())), t.GetNetname()[-12:])
