#!/usr/bin/env python3
"""showp.py <base.json> <placement_gu.json> <out.png> [F|B] [x0 y0 x1 y1 scale]  quick picture of a placement (no copper)"""
import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glib, render
db = glib.DB(sys.argv[1]); P = {r: tuple(v) for r, v in json.load(open(sys.argv[2])).items()}
side = sys.argv[4] if len(sys.argv) > 4 else 'F'
box = tuple(map(float, sys.argv[5:9])) if len(sys.argv) > 8 else None
sc = float(sys.argv[9]) if len(sys.argv) > 9 else 30
d = dict(fps=[db.world(r, *P[r]) for r in P], zones=db.d['zones'])
render.render(d, sys.argv[3], box, side, sc, padnames=box is not None, netlabels=box is not None)
