"""liftnew.py in.kicad_pcb out.kicad_pcb ref.kicad_pcb netregex: remove the tracks / vias of the matching nets that are not in the ref board (KiCad python)"""
import sys, re, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); rx = re.compile(sys.argv[4])
ref = {t.m_Uuid.AsString() for t in pcbnew.LoadBoard(sys.argv[3]).GetTracks()}
n = 0
for t in list(b.GetTracks()):
    if rx.search(t.GetNetname()) and t.m_Uuid.AsString() not in ref: b.Remove(t); n += 1
b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2]); print('removed', n)
