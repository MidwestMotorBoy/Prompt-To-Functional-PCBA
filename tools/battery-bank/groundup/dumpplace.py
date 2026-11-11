"""dumpplace.py board.kicad_pcb out.json (KiCad python): {ref: [x, y, rot]} of every footprint, for mechcheck.py"""
import sys, json, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); M = pcbnew.ToMM
json.dump({f.GetReference(): [round(M(f.GetPosition().x), 4), round(M(f.GetPosition().y), 4), f.GetOrientationDegrees()] for f in b.GetFootprints()}, open(sys.argv[2], 'w'))
