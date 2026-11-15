"""dlib.py - team D geometry library: load the template dump, apply a placement {ref:[x,y,quarter-turn-degrees]},
check it (courtyard overlap, outline, keep-outs, fixed parts), measure it, render it.
Placement convention is the scorecard's (tools/floorplan/apply_placement.py): x, y of the footprint origin in mm and an
angle in degrees that is a multiple of 90, RELATIVE to the template orientation; one quarter turn maps a local offset
(lx, ly) -> (-ly, lx) (screen coords, y down: that is 90 deg clockwise on screen)."""
import json, os, math, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '../../../..'))
E = os.path.join(ROOT, 'tools/floorplan/example/monolith')
FIXED_PREFIX = ('J', 'H', 'TP', 'SW', 'TH')
FIXED_REFS = {'U301', 'L401', 'L501'}

def rotq(lx, ly, q):
    for _ in range(q % 4): lx, ly = -ly, lx
    return lx, ly

class Board:
    def __init__(self, dump=None):
        d = json.load(open(dump or os.path.join(E, 'board_dump.json')))
        self.net = json.load(open(os.path.join(E, 'netlist.json'))); self.con = json.load(open(os.path.join(E, 'constraints.json')))
        self.box = d['box']; self.keepouts = d['keepouts']
        self.fp = {}                      # ref -> dict(x,y,side,court(local),pads{num:[(lx,ly,box local, net)]})
        for f in d['fps']:
            c = f['court']; self.fp[f['ref']] = dict(x0=f['x'], y0=f['y'], side=f['side'], value=f.get('value', ''),
                court=[c[0]-f['x'], c[1]-f['y'], c[2]-f['x'], c[3]-f['y']], pads=[])
        for p in d['pads']:
            f = self.fp[p['ref']]; b = p['box']
            f['pads'].append(dict(num=p['num'], net=p['net'], lx=p['x']-f['x0'], ly=p['y']-f['y0'],
                                  box=[b[0]-f['x0'], b[1]-f['y0'], b[2]-f['x0'], b[3]-f['y0']], layers=p['layers']))
        self.P = {r: [f['x0'], f['y0'], 0] for r, f in self.fp.items()}
        comps = self.net['comps']
        self.section = {r: (comps[r]['block'] + ' / ' + comps[r]['section']) if r in comps else 'mech' for r in self.fp}
        self.block = {r: comps[r]['block'] if r in comps else 'mech' for r in self.fp}
    def fixed(self, r):
        return r in FIXED_REFS or self.fp[r]['side'] == 'B.Cu' or any(r.startswith(p) and r[len(p):][:1].isdigit() for p in FIXED_PREFIX)
    def set(self, P):
        for r, v in P.items(): self.P[r] = [v[0], v[1], int(v[2]) % 360]
    def court(self, r):
        x, y, a = self.P[r]; c = self.fp[r]['court']; q = a // 90
        pts = [rotq(c[i], c[j], q) for i in (0, 2) for j in (1, 3)]
        return [x+min(p[0] for p in pts), y+min(p[1] for p in pts), x+max(p[0] for p in pts), y+max(p[1] for p in pts)]
    def pads(self, r):
        x, y, a = self.P[r]; q = a // 90; out = []
        for p in self.fp[r]['pads']:
            lx, ly = rotq(p['lx'], p['ly'], q); b = p['box']
            pts = [rotq(b[i], b[j], q) for i in (0, 2) for j in (1, 3)]
            out.append(dict(ref=r, num=p['num'], net=p['net'], x=x+lx, y=y+ly, layers=p['layers'],
                            box=[x+min(t[0] for t in pts), y+min(t[1] for t in pts), x+max(t[0] for t in pts), y+max(t[1] for t in pts)]))
        return out
    def pad(self, r, num):
        ps = [p for p in self.pads(r) if p['num'] == str(num)]
        return (sum(p['x'] for p in ps)/len(ps), sum(p['y'] for p in ps)/len(ps))
    def nets(self):
        n = collections.defaultdict(list)
        for r in self.fp:
            for p in self.pads(r):
                if p['net']: n[p['net']].append(p)
        return n
    # ---- checks
    def check(self, refs=None, gap=0.0):
        """returns list of problem strings: courtyard overlaps (same side), outside board, in a no-footprint keep-out, fixed part moved"""
        out = []; rs = list(self.fp); cs = {r: self.court(r) for r in rs}
        for i, a in enumerate(rs):
            for b in rs[i+1:]:
                if refs is not None and a not in refs and b not in refs: continue
                if self.fp[a]['side'] != self.fp[b]['side']: continue
                A, B = cs[a], cs[b]; ox = min(A[2], B[2]) - max(A[0], B[0]); oy = min(A[3], B[3]) - max(A[1], B[1])
                if ox > -gap + 1e-6 and oy > -gap + 1e-6 and min(ox, oy) > 0.011: out.append(f'OVERLAP {a} {b} by {min(ox,oy):.2f} mm')
        for r in rs:
            if refs is not None and r not in refs: continue
            c = cs[r]; f = self.fp[r]
            if self.fixed(r):
                if abs(self.P[r][0]-f['x0']) + abs(self.P[r][1]-f['y0']) > 1e-6 or self.P[r][2]: out.append(f'FIXED part moved {r}')
                continue
            if c[0] < self.box[0] or c[1] < self.box[1] or c[2] > self.box[2] or c[3] > self.box[3]: out.append(f'OUTSIDE board {r}')
            for k in self.keepouts:
                if not k['no_footprints'] or f['side'] not in k['layers']: continue
                K = k['box']
                if min(c[2], K[2]) - max(c[0], K[0]) > 0.01 and min(c[3], K[3]) - max(c[1], K[1]) > 0.01: out.append(f'KEEPOUT {r} in {k["name"]}')
        return out
    # ---- measures
    def mst(self, pts):
        if len(pts) < 2: return 0.0, []
        inn = [0]; rest = list(range(1, len(pts))); tot = 0; ed = []
        while rest:
            d, i, j = min((abs(pts[i][0]-pts[j][0]) + abs(pts[i][1]-pts[j][1]), i, j) for i in inn for j in rest)
            tot += d; ed.append((i, j)); inn.append(j); rest.remove(j)
        return tot, ed
    def wirelength(self, skip=('GND', 'PACK_P', '3V3')):
        tot = 0; per = {}
        for n, ps in self.nets().items():
            if n in skip: continue
            per[n] = self.mst([(p['x'], p['y']) for p in ps])[0]; tot += per[n]
        return tot, per
    # ---- render
    def render(self, path, region=None, scale=28, rats=True, refs=None, label=True, skip=('GND', 'PACK_P', '3V3'), title=None, boxes=None, hi=None):
        from PIL import Image, ImageDraw, ImageFont
        R = region or [self.box[0]-1, self.box[1]-1, self.box[2]+1, self.box[3]+1]
        W, H = int((R[2]-R[0])*scale), int((R[3]-R[1])*scale); im = Image.new('RGB', (W, H), (250, 250, 250)); d = ImageDraw.Draw(im, 'RGBA')
        X = lambda x: (x-R[0])*scale; Y = lambda y: (y-R[1])*scale
        try: fnt = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', max(9, int(scale*0.42)))
        except Exception: fnt = ImageFont.load_default()
        d.rectangle([X(self.box[0]), Y(self.box[1]), X(self.box[2]), Y(self.box[3])], outline=(0, 0, 0), width=2)
        for g in range(int(R[0]//5*5), int(R[2])+1, 5):
            d.line([X(g), 0, X(g), H], fill=(0, 0, 0, 22)); d.text((X(g)+2, 2), str(g), fill=(90, 90, 90), font=fnt)
        for g in range(int(R[1]//5*5), int(R[3])+1, 5):
            d.line([0, Y(g), W, Y(g)], fill=(0, 0, 0, 22)); d.text((2, Y(g)+2), str(g), fill=(90, 90, 90), font=fnt)
        for k in self.keepouts:
            K = k['box']
            if k['no_footprints'] and 'F.Cu' in k['layers']: d.rectangle([X(K[0]), Y(K[1]), X(K[2]), Y(K[3])], fill=(120, 120, 120, 90))
        secs = sorted(set(self.section.values())); pal = {}
        for i, s in enumerate(secs):
            h = (i * 0.618034) % 1.0; import colorsys
            r, g, b = colorsys.hsv_to_rgb(h, 0.55, 0.95); pal[s] = (int(r*255), int(g*255), int(b*255))
        for r in self.fp:
            c = self.court(r); col = pal[self.section[r]]; back = self.fp[r]['side'] == 'B.Cu'
            if back: d.rectangle([X(c[0]), Y(c[1]), X(c[2]), Y(c[3])], outline=(100, 100, 100, 160), width=1); continue
            d.rectangle([X(c[0]), Y(c[1]), X(c[2]), Y(c[3])], fill=col + (110,), outline=(200, 0, 0) if hi and r in hi else col + (255,), width=3 if hi and r in hi else 1)
        for r in self.fp:
            if self.fp[r]['side'] == 'B.Cu': continue
            for p in self.pads(r):
                b = p['box']; d.rectangle([X(b[0]), Y(b[1]), X(b[2]), Y(b[3])], fill=(60, 60, 60, 200) if p['net'] != 'GND' else (40, 110, 40, 200))
                if scale >= 40 and (b[2]-b[0]) * scale > 14 and len(self.fp[r]['pads']) > 2: d.text((X(b[0])+1, Y(b[1])), p['num'], fill=(255, 255, 0), font=fnt)
        if rats:
            for n, ps in self.nets().items():
                if n in skip: continue
                if refs is not None and not any(p['ref'] in refs for p in ps): continue
                pts = [(p['x'], p['y']) for p in ps]
                for i, j in self.mst(pts)[1]: d.line([X(pts[i][0]), Y(pts[i][1]), X(pts[j][0]), Y(pts[j][1])], fill=(0, 0, 200, 110), width=1)
        for name, bx in (boxes or {}).items():
            d.rectangle([X(bx[0]), Y(bx[1]), X(bx[2]), Y(bx[3])], outline=(0, 0, 0, 255), width=2); d.text((X(bx[0])+3, Y(bx[1])+3), name, fill=(0, 0, 0), font=fnt)
        if label:
            for r in self.fp:
                if self.fp[r]['side'] == 'B.Cu': continue
                c = self.court(r); d.text((X((c[0]+c[2])/2)-len(r)*scale*0.12, Y((c[1]+c[3])/2)-scale*0.25), r, fill=(0, 0, 0), font=fnt)
        if title: d.text((X(self.box[0])+40, 2), title, fill=(0, 0, 0), font=fnt)
        im.save(path); return path

if __name__ == '__main__':
    import sys
    b = Board()
    if len(sys.argv) > 2: b.set(json.load(open(sys.argv[2])))
    print('\n'.join(b.check()) or 'checks clean'); print('wirelength (signal MST, mm): %.0f' % b.wirelength()[0])
    b.render(sys.argv[1])
