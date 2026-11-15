"""showp.py <build dir> <out.png> x0,y0,x1,y1 [scale=40] [side=F]: placement picture (courtyards, pads by net, pad numbers)
from a rebuild dir (base.json + placement_gu.json), via the groundup placelib.show()."""
import sys, os, json
d = os.path.abspath(sys.argv[1]); out = os.path.abspath(sys.argv[2]); os.chdir(d); sys.path.insert(0, d)
from placelib import show
P = {r: tuple(v) for r, v in json.load(open('placement_gu.json')).items()}
box = tuple(map(float, sys.argv[3].split(','))); sc = float(sys.argv[4]) if len(sys.argv) > 4 else 40
show(P, out, box, scale=sc, padnames=True, netlabels=True, side=sys.argv[5] if len(sys.argv) > 5 else 'F')
print(out)
