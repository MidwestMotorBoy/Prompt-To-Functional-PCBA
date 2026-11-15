"""freemap.py <gu.json> x0,y0,x1,y1 [ignore refs,..] [--side=F]: ASCII map (0.2 mm cells) of F.Cu courtyard occupancy
in a window, for finding free spots by eye ('#' = courtyard, '.' = free, letters = the ignored parts' current spots)."""
import sys, os, json, numpy as np
A = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
P = {r: tuple(v) for r, v in json.load(open(os.path.abspath(sys.argv[1]))).items()}
os.chdir(f'{A}/stage'); sys.path.insert(0, f'{A}/stage'); import placelib
x0, y0, x1, y1 = map(float, sys.argv[2].split(',')); ign = sys.argv[3].split(',') if len(sys.argv) > 3 else []
W = placelib.world(P); g = 0.2; nx, ny = int((x1 - x0) / g), int((y1 - y0) / g); M = np.full((ny, nx), '.')
for r, w in W.items():
    if w['layer'] != 'F.Cu': continue
    b = w['bb']; i0, i1 = int(np.floor((b[1] - y0) / g)), int(np.ceil((b[3] - y0) / g)); j0, j1 = int(np.floor((b[0] - x0) / g)), int(np.ceil((b[2] - x0) / g))
    i0, i1, j0, j1 = max(0, i0), min(ny, i1), max(0, j0), min(nx, j1)
    if i1 <= i0 or j1 <= j0: continue
    M[i0:i1, j0:j1] = chr(97 + ign.index(r)) if r in ign else '#'
print('      ' + ''.join(str(int(x0 + j * g) % 10) if abs((x0 + j * g) - round(x0 + j * g)) < 1e-6 else ' ' for j in range(nx)))
for i in range(ny): print(f'{y0 + i * g:6.1f}' + ''.join(M[i]))
print('ignored:', {chr(97 + k): r for k, r in enumerate(ign)})
