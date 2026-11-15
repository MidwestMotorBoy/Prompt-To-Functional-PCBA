"""pinmap.py REF [REF...] - pads of a part by side (in its CURRENT orientation on the given placement), with nets.
usage: pinmap.py [--p placement.json] U401 U403"""
import sys, json
from dlib import Board
def pinmap(b, r):
    c = b.court(r); ps = b.pads(r); cx, cy = (c[0]+c[2])/2, (c[1]+c[3])/2; w, h = c[2]-c[0], c[3]-c[1]
    out = [f'{r} ({b.fp[r]["value"]}) centre ({b.P[r][0]:.2f},{b.P[r][1]:.2f}) rot {b.P[r][2]} courtyard {w:.1f} x {h:.1f} mm, {b.section[r]}']
    sides = {'N': [], 'E': [], 'S': [], 'W': [], 'C': []}
    for p in ps:
        dx, dy = (p['x']-cx)/(w/2), (p['y']-cy)/(h/2)
        if max(abs(dx), abs(dy)) < 0.2: s = "C"
        elif abs(dx) > abs(dy): s = 'E' if dx > 0 else 'W'
        else: s = 'S' if dy > 0 else 'N'
        sides[s].append(p)
    for s, key in (('N', lambda p: p['x']), ('E', lambda p: p['y']), ('S', lambda p: p['x']), ('W', lambda p: p['y'])):
        if sides[s]: out.append(f'  {s} side ({"left to right" if s in "NS" else "top to bottom"}): ' + ', '.join(f'{p["num"]}={p["net"].replace("/USB Port ", "P").replace("USB Port ", "P") or "nc"}' for p in sorted(sides[s], key=key)))
    if sides['C']: out.append('  centre: ' + ', '.join(sorted(set(f'{p["num"]}={p["net"] or "nc"}' for p in sides['C']))))
    return '\n'.join(out)
if __name__ == '__main__':
    a = sys.argv[1:]; b = Board()
    if a and a[0] == '--p': b.set(json.load(open(a[1]))); a = a[2:]
    for r in a: print(pinmap(b, r))
