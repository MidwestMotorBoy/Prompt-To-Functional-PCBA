"""zoom.py <scorecard outdir> <out.png> x0,y0,x1,y1 [layer=F.Cu] [px/mm=40]
Copper render of a window (tools/copper/render.py) with pad numbers, refs and the GHOSTFAIL pads (red circles)
from ghost.log. For finding what walls a blocked pad in."""
import sys, os, json, subprocess, re
from PIL import Image, ImageDraw
d, out, box = sys.argv[1:4]; L = sys.argv[4] if len(sys.argv) > 4 else 'F.Cu'; S = float(sys.argv[5]) if len(sys.argv) > 5 else 40
R = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..'))
subprocess.run(['python3', f'{R}/tools/copper/render.py', f'{d}/cu.kicad_pcb', f'{d}/cu.json', out, L, box, str(S)], check=True, capture_output=True)
x0, y0, x1, y1 = map(float, box.split(',')); im = Image.open(out).convert('RGB'); dr = ImageDraw.Draw(im)
P = lambda x, y: ((x - x0) * S, (y - y0) * S)
D = json.load(open(f'{d}/cu.json'))
fail = set()
if os.path.exists(f'{d}/ghost.log'):
    for l in open(f'{d}/ghost.log'):
        if l.startswith('GHOSTFAIL'):
            for m in re.finditer(r'Pad (\S+) \[[^\]]*\] of (\S+)', l): fail.add((m.group(2), m.group(1)))
for p in D['pads']:
    if L not in p['shapes'] and not p['drill']: continue
    if not (x0 <= p['x'] <= x1 and y0 <= p['y'] <= y1): continue
    x, y = P(p['x'], p['y'])
    if (p['ref'], p['num']) in fail: dr.ellipse([x - 9, y - 9, x + 9, y + 9], outline=(255, 0, 0), width=3)
    if S >= 30: dr.text((x - 4, y - 5), p['num'], fill=(0, 0, 160))
for f in D['fps']:
    if not (x0 <= f['x'] <= x1 and y0 <= f['y'] <= y1): continue
    if (f.get('layer', 'F.Cu') == 'B.Cu') != (L == 'B.Cu'): continue
    x, y = P(f['x'], f['y']); dr.text((x - 10, y + 6), f['ref'], fill=(200, 0, 0))
im.save(out); print(out, im.size, len(fail), 'fail pads')
