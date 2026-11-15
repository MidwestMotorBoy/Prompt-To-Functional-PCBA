"""room.py - hand placement of one room (a group of parts in a box) with instant checks and a picture.

A worker writes a small python script:

    from room import Room
    rm = Room('p1_pd')                      # loads ../rooms/p1_pd.spec.json (box, parts, anchors) and the master placement
    rm.put('U401', 105.1, 79.9, 0)          # absolute: footprint origin x, y (mm) and rotation 0/90/180/270
    rm.beside('C403', 'U401.38', 'N')       # C403's pad on the same net goes straight north of U401 pad 38, bodies 0.15 mm apart
    rm.beside('R402', 'C403', 'E', gap=0.1) # next to another part: courtyards 0.1 mm apart, centred on it
    rm.row(['R402','R403','R404'], 'R441', 'E')   # a row of parts continuing east from R441
    rm.done()                               # checks, measures, saves ../rooms/p1_pd.json and ../rooms/p1_pd.png

Rotation is relative to the template orientation (the scorecard's convention). A quarter turn maps a local offset
(lx, ly) to (-ly, lx) with y pointing DOWN on screen: rot 90 turns the part clockwise as drawn.
Sides: N = smaller y (up on the picture), S = larger y, W = smaller x, E = larger x."""
import json, os, sys
from dlib import Board, HERE
ROOMS = os.path.join(HERE, '..', 'rooms')
MASTER = os.path.join(ROOMS, 'master.json')

class Room:
    def __init__(self, name, master=None):
        self.name = name; self.b = Board()
        m = master or MASTER
        if os.path.exists(m): self.b.set(json.load(open(m)))
        self.spec = json.load(open(os.path.join(ROOMS, name + '.spec.json')))
        self.box = self.spec['box']; self.parts = list(self.spec['parts']); self.placed = {}
        self.locked = set(self.spec.get('locked', []))        # parts of this room the lead has pinned
        prev = os.path.join(ROOMS, name + '.json')
        if os.path.exists(prev) and '--fresh' not in sys.argv:
            for r, v in json.load(open(prev)).items():
                if r in self.parts: self.b.P[r] = v
    # ---- geometry helpers
    def court(self, r): return self.b.court(r)
    def size(self, r, rot=None):
        if rot is not None: old = self.b.P[r][2]; self.b.P[r][2] = rot % 360
        c = self.b.court(r)
        if rot is not None: self.b.P[r][2] = old
        return c[2]-c[0], c[3]-c[1]
    def pad(self, spec):
        """'U401.38' -> (x, y) of that pad (mean if several share the number)"""
        r, n = spec.split('.', 1); return self.b.pad(r, n)
    def _own(self, r):
        if r not in self.parts: raise SystemExit(f'{r} is not a part of room {self.name}')
        if self.b.fixed(r): raise SystemExit(f'{r} is a fixed part: it cannot move')
        if r in self.locked: raise SystemExit(f'{r} is locked by the lead in this room')
    # ---- placing
    def put(self, r, x, y, rot=0):
        self._own(r); self.b.P[r] = [round(x, 3), round(y, 3), int(rot) % 360]; self.placed[r] = 1; return self
    def move(self, r, dx=0, dy=0):
        self._own(r); self.b.P[r][0] = round(self.b.P[r][0]+dx, 3); self.b.P[r][1] = round(self.b.P[r][1]+dy, 3); return self
    def put_court(self, r, rot=0, left=None, top=None, right=None, bottom=None):
        """place by courtyard edges: give one of left/right and one of top/bottom (mm)"""
        self._own(r); self.b.P[r] = [0, 0, int(rot) % 360]; c = self.b.court(r)
        x = (left - c[0]) if left is not None else (right - c[2]); y = (top - c[1]) if top is not None else (bottom - c[3])
        return self.put(r, x, y, rot)
    def beside(self, r, target, side, gap=0.15, rot=None, pad=None, shift=0.0):
        """Place part r on the given side (N/E/S/W) of target.
        target 'U401.38' (a pad): r's pad on the same net (or pad=<number>) is lined up with that pad, and r's courtyard is
          `gap` mm clear of the target PART's courtyard. rot=None tries all four turns and keeps the one whose connecting pad is
          nearest the target pad.
        target 'R441' (a part): r is centred on that part's courtyard on that side, courtyards `gap` apart.
        shift: slide r along the edge (mm, +x or +y)."""
        self._own(r)
        tr, tn = (target.split('.', 1) + [None])[:2]; T = self.b.court(tr)
        if tn is not None:
            tx, ty = self.b.pad(tr, tn); tnet = [p['net'] for p in self.b.pads(tr) if p['num'] == tn][0]
        else: tx, ty = (T[0]+T[2])/2, (T[1]+T[3])/2; tnet = None
        best = None
        for q in ([rot] if rot is not None else [0, 90, 180, 270]):
            self.b.P[r] = [0, 0, q % 360]; c = self.b.court(r)
            if tn is not None:
                mine = [p for p in self.b.pads(r) if (p['num'] == str(pad) if pad is not None else p['net'] == tnet)]
                if not mine: raise SystemExit(f'{r} has no pad on net {tnet}; give pad=')
                px, py = sum(p['x'] for p in mine)/len(mine), sum(p['y'] for p in mine)/len(mine)
            else: px, py = (c[0]+c[2])/2, (c[1]+c[3])/2
            if side == 'N': x, y = tx - px + shift, T[1] - gap - c[3]
            elif side == 'S': x, y = tx - px + shift, T[3] + gap - c[1]
            elif side == 'W': x, y = T[0] - gap - c[2], ty - py + shift
            else: x, y = T[2] + gap - c[0], ty - py + shift
            d = abs(x + px - tx) + abs(y + py - ty)
            if best is None or d < best[0] - 1e-6: best = (d, x, y, q)
        return self.put(r, best[1], best[2], best[3])
    def row(self, refs, start, side, gap=0.1, rot=None):
        """parts one after another going `side` from part `start` (centred on the previous one)"""
        prev = start
        for r in refs: self.beside(r, prev, side, gap=gap, rot=rot if rot is not None else self.b.P[r][2]); prev = r
        return self
    # ---- report
    def problems(self):
        out = [p for p in self.b.check(refs=set(self.parts), gap=0.0)]
        out = [p for p in out if not (p.startswith('OVERLAP') and float(p.split()[-2]) < 0.1)]     # the template's courtyards touch
        boxes = self.spec.get('boxes') or [self.box]
        for r in self.parts:
            if self.b.fixed(r): continue
            c = self.b.court(r)
            a = sum(max(0, min(c[2], B[2]+0.1) - max(c[0], B[0]-0.1)) * max(0, min(c[3], B[3]+0.1) - max(c[1], B[1]-0.1)) for B in boxes)
            if a < (c[2]-c[0]) * (c[3]-c[1]) - 0.02: out.append(f'OUT OF ROOM {r} courtyard {[round(v,2) for v in c]} (room area = the boxes drawn in black)')
        for k in self.spec.get('keep_free', []):               # lanes the lead reserved: [x0,y0,x1,y1,why]
            for r in self.parts:
                c = self.b.court(r)
                if min(c[2], k[2]) - max(c[0], k[0]) > 0.01 and min(c[3], k[3]) - max(c[1], k[1]) > 0.01: out.append(f'IN RESERVED LANE {r}: {k[4]}')
        return out
    def measures(self):
        """per-net shortest-tree length over the pads of this room's parts (plus the nearest outside pad), and serve distances"""
        nets = self.b.nets(); mine = set(self.parts); rows = []
        for n, ps in nets.items():
            if n in ('GND',): continue
            inn = [p for p in ps if p['ref'] in mine]
            if not inn: continue
            L = self.b.mst([(p['x'], p['y']) for p in ps])[0] if len(ps) <= 40 else 0
            Lin = self.b.mst([(p['x'], p['y']) for p in inn])[0]
            rows.append((Lin, n, len(inn), len(ps), L))
        return sorted(rows, reverse=True)
    def serves(self):
        out = []; pp = self.b.con.get('pin_pads', {})
        for cap, pin in self.b.con.get('serves', {}).items():
            if cap not in self.parts: continue
            r, name = pin.split('.'); nums = pp.get(pin, [name])
            tp = [p for p in self.b.pads(r) if p['num'] in nums]
            if not tp: continue
            tn = tp[0]['net']; cp = [p for p in self.b.pads(cap) if p['net'] == tn]
            if not cp: continue
            d = min(abs(a['x']-c['x']) + abs(a['y']-c['y']) for a in tp for c in cp)
            out.append((d, cap, pin))
        return sorted(out, reverse=True)
    def done(self, picture=True, scale=None):
        pr = self.problems(); un = [r for r in self.parts if not self.b.fixed(r) and r not in self.placed and r not in self.locked]
        print(f'== room {self.name}: {len(self.parts)} parts, {len(self.placed)} placed by this script')
        if un: print('NOT PLACED by this script (still at their old spot):', ' '.join(un))
        print('\n'.join(pr) if pr else 'no overlaps, all inside the room')
        print('-- longest in-room nets (mm over this room\'s pads | net | pads in room / all):')
        for Lin, n, a, t, L in self.measures()[:14]: print(f'   {Lin:5.1f}  {n}  {a}/{t}')
        print('   total in-room signal tree: %.0f mm' % sum(m[0] for m in self.measures() if m[1] not in ('PACK_P', '3V3')))
        sv = self.serves()
        if sv: print('-- decoupling/served pins, pad-to-pad distance (mm), worst first:'); print('   ' + ', '.join(f'{c}->{p} {d:.1f}' for d, c, p in sv[:12]))
        out = {r: self.b.P[r] for r in self.parts if not self.b.fixed(r)}
        json.dump(out, open(os.path.join(ROOMS, self.name + '.json'), 'w'), indent=0)
        if picture:
            bx = self.box; reg = [bx[0]-2.5, bx[1]-2.5, bx[2]+2.5, bx[3]+2.5]
            sc = scale or int(min(70, 1500 / max(reg[2]-reg[0], reg[3]-reg[1])))
            lanes = {('lane: ' + k[4])[:28]: k[:4] for k in self.spec.get('keep_free', [])}
            self.b.render(os.path.join(ROOMS, self.name + '.png'), region=reg, scale=sc, refs=set(self.parts), boxes={**{f'{self.name} {i}': B for i, B in enumerate(self.spec.get('boxes') or [bx])}, **lanes}, hi=set(self.parts))
            print('picture:', os.path.abspath(os.path.join(ROOMS, self.name + '.png')), '(look at it)')
        return pr
