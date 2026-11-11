import sys, pcbnew
from collections import Counter
for f in sys.argv[1:]:
    b = pcbnew.LoadBoard(f); c = Counter(t.GetClass() for t in b.GetTracks()); L = sum(t.GetLength() for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK') / 1e6
    print(f.split('/')[-1], dict(c), 'track length %.0f mm' % L, 'footprints', len(b.GetFootprints()), 'zones', len(b.Zones()))
