"""difft.py new.kicad_pcb old.kicad_pcb netregex: tracks / vias of the nets that are in new but not in old (KiCad python)"""
import sys, re, pcbnew
MM = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); old = {t.m_Uuid.AsString() for t in pcbnew.LoadBoard(sys.argv[2]).GetTracks()}; rx = re.compile(sys.argv[3])
for t in b.GetTracks():
    if t.m_Uuid.AsString() in old or not rx.search(t.GetNetname()): continue
    if t.GetClass() == 'PCB_VIA': print('V %.3f,%.3f' % (MM(t.GetPosition().x), MM(t.GetPosition().y)))
    else: print('T %s %.3f,%.3f > %.3f,%.3f w%.2f' % (b.GetLayerName(t.GetLayer())[:3], MM(t.GetStart().x), MM(t.GetStart().y), MM(t.GetEnd().x), MM(t.GetEnd().y), MM(t.GetWidth())))
