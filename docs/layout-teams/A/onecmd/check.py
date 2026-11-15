#!/usr/bin/env python3
"""check.py <build dir> <placement_gu.json>: groundup placelib.check (courtyard overlaps, edge, lip, notch, peg) with the
build dir's base.json and keep_vias.json. Exit 1 on any error."""
import sys, os, json
D = os.path.abspath(sys.argv[1]); G = os.path.abspath(sys.argv[2]); os.chdir(D); sys.path.insert(0, D)
import placelib
P = {r: tuple(v) for r, v in json.load(open(G)).items()}
errs, miss = placelib.check(P)
print('CHECK', 'clean' if not errs and not miss else f'{len(errs)} errors, {len(miss)} missing')
sys.exit(1 if errs or miss else 0)
