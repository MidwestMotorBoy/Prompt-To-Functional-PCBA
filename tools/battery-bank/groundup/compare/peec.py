"""PEEC-lite loop inductance on the real board copper (HF limit, inductive only).
Copper of selected nets is rasterized per layer at cell h; adjacent same-net cells get
x/y bar branches, vias get z branches.  Partial inductances (filament formula, GMD floor)
-> K = A L^-1 A^T (nodal 'inverse-inductance' matrix).  Ideal parts are stamped on K:
shorts (FET/IC pins), cap ESL (1/ESL).  Port L = phi_P - phi_N for unit current.
"""
import math, numpy as np, scipy.sparse as sp, scipy.linalg as sla
from scipy.linalg import lapack
from PIL import Image, ImageDraw
from board import FP, SEG, VIA, ZON, REF

LAYERS = ['F.Cu', 'In1.Cu', 'In2.Cu', 'In3.Cu', 'In4.Cu', 'B.Cu']
TH = {'F.Cu': 0.07, 'B.Cu': 0.07, 'In1.Cu': 0.0175, 'In2.Cu': 0.0175, 'In3.Cu': 0.0175, 'In4.Cu': 0.0175}
# z of layer centre (mm, from top), KiCad stackup: 0.07 Cu /0.2/0.0175/0.3/0.0175/0.39/0.0175/0.3/0.0175/0.2/0.07
ZC = {'F.Cu': 0.035, 'In1.Cu': 0.27875, 'In2.Cu': 0.59625, 'In3.Cu': 1.00375, 'In4.Cu': 1.32125, 'B.Cu': 1.565}
MU4PI = 1e-7  # mu0/4pi [H/m]


def padpoly(p):
    a = math.radians(-p['rot']); w, h = p['w']/2, p['h']/2
    return [(p['x']+dx*math.cos(a)-dy*math.sin(a), p['y']+dx*math.sin(a)+dy*math.cos(a))
            for dx, dy in ((-w, -h), (w, -h), (w, h), (-w, h))]


def padlayers(p):
    if '*.Cu' in p['layers']: return LAYERS
    return [l for l in p['layers'] if l in LAYERS]


def g(x, d):
    return x*np.arcsinh(x/d) - np.sqrt(x*x + d*d)


_GT = {}
def gmd_tab(h, KMAX=10):
    """GMD between two h-wide bar cross-sections: key (k, zA, tA, zB, tB) with lateral offset k*h"""
    if h in _GT: return _GT[h]
    zs = sorted(set((ZC[L], TH[L]) for L in LAYERS)); tab = {}
    ny, nz = 24, 3
    for zA, tA in zs:
        for zB, tB in zs:
            for k in range(KMAX+1):
                if k == 0 and zA == zB:
                    tab[(k, zA, zB)] = 0.2235*(h+tA); continue
                ya = (np.arange(ny)+0.5)/ny*h - h/2; za = zA + ((np.arange(nz)+0.5)/nz-0.5)*tA
                yb = (np.arange(ny)+0.5)/ny*h - h/2 + k*h; zb = zB + ((np.arange(nz)+0.5)/nz-0.5)*tB
                YA, ZA = np.meshgrid(ya, za); YB, ZB = np.meshgrid(yb, zb)
                r = np.hypot(YA.ravel()[:, None]-YB.ravel()[None, :], ZA.ravel()[:, None]-ZB.ravel()[None, :])
                tab[(k, zA, zB)] = float(np.exp(np.mean(np.log(np.maximum(r, 1e-6)))))
    _GT[h] = (tab, KMAX); return _GT[h]


def mpar(a1, a2, b1, b2, d):
    """mutual partial inductance of parallel filaments [a1,a2],[b1,b2] at distance d (mm) -> H"""
    return MU4PI*1e-3*(g(b2-a1, d) - g(b2-a2, d) - g(b1-a1, d) + g(b1-a2, d))


class Model:
    def __init__(self, box, nets, h=0.25, layers=LAYERS, top=(), centre=None):
        # centre=True: a cell is copper when its centre is inside the copper. False is the old behaviour (every
        # cell the outline touches), which makes every plate and pad one cell wider and reads a few percent low.
        import os as _os
        self.centre = (_os.environ.get('PEEC_CENTRE', '1') == '1') if centre is None else centre
        self.top = set(top)
        self.box, self.h, self.layers = box, h, layers
        x0, x1, y0, y1 = box
        self.W = int(round((x1-x0)/h)); self.H = int(round((y1-y0)/h))
        self.nets = list(nets); self.nid = {n: i+1 for i, n in enumerate(self.nets)}
        self.lab = {L: self._raster(L) for L in layers}

    def P(self, x, y):
        return ((x-self.box[0])/self.h, (y-self.box[2])/self.h)

    def _raster(self, L):
        im = Image.new('I', (self.W, self.H), 0); d = ImageDraw.Draw(im); P = self.P; h = self.h
        for z in ZON:
            if z['keepout'] or z['net'] not in self.nid: continue
            for LL, pts in z['fills']:
                if LL == L: d.polygon([P(*q) for q in pts], fill=self.nid[z['net']])
        for s in SEG:
            if s['net'] in self.nid and s['layer'] == L:
                w = s['w']/h; a = P(s['x1'], s['y1']); b = P(s['x2'], s['y2'])
                d.line([a, b], fill=self.nid[s['net']], width=max(1, int(round(w))))
                r = w/2
                for q in (a, b): d.ellipse([q[0]-r, q[1]-r, q[0]+r, q[1]+r], fill=self.nid[s['net']])
        for fp in FP:
            for p in fp['pads']:
                if p['net'] in self.nid and L in padlayers(p):
                    if p['shape'] == 'circle':
                        c = P(p['x'], p['y']); r = p['w']/2/h
                        d.ellipse([c[0]-r, c[1]-r, c[0]+r, c[1]+r], fill=self.nid[p['net']])
                    else:
                        d.polygon([P(*q) for q in padpoly(p)], fill=self.nid[p['net']])
        for v in VIA:
            if v['net'] in self.nid:
                c = P(v['x'], v['y']); r = max(v['size']/2/h, 0.5)
                d.ellipse([c[0]-r, c[1]-r, c[0]+r, c[1]+r], fill=self.nid[v['net']])
        for s in SEG:
            if s['net'] in self.top and s['layer'] == L:
                w = s['w']/h; a = P(s['x1'], s['y1']); b = P(s['x2'], s['y2'])
                d.line([a, b], fill=self.nid[s['net']], width=max(1, int(round(w))))
        for fp in FP:
            for p in fp['pads']:
                if p['net'] in self.top and L in padlayers(p) and p['shape'] != 'circle':
                    d.polygon([P(*q) for q in padpoly(p)], fill=self.nid[p['net']])
        a = np.array(im, dtype=np.int32)
        if self.centre:
            # zone and pad copper counts only where it covers at least half the cell; tracks and vias keep every cell they touch
            keep = Image.new('I', (self.W, self.H), 0); dk = ImageDraw.Draw(keep)
            for s in SEG:
                if (s['net'] in self.nid or s['net'] in self.top) and s['layer'] == L:
                    w = s['w']/h; p1 = P(s['x1'], s['y1']); p2 = P(s['x2'], s['y2'])
                    dk.line([p1, p2], fill=1, width=max(1, int(round(w))))
            for v in VIA:
                if v['net'] in self.nid:
                    c = P(v['x'], v['y']); r = max(v['size']/2/h, 0.5); dk.ellipse([c[0]-r, c[1]-r, c[0]+r, c[1]+r], fill=1)
            for fp in FP:
                for p in fp['pads']:
                    if p['net'] in self.nid and L in padlayers(p) and p['shape'] == 'circle':
                        c = P(p['x'], p['y']); r = p['w']/2/h; dk.ellipse([c[0]-r, c[1]-r, c[0]+r, c[1]+r], fill=1)
            keep = np.array(keep, dtype=bool)
            for net, k in self.nid.items():
                polys = [pts for z in ZON if not z['keepout'] and z['net'] == net for LL, pts in z['fills'] if LL == L]
                polys += [padpoly(p) for fp in FP for p in fp['pads'] if p['net'] == net and L in padlayers(p) and p['shape'] != 'circle']
                cov = self._cover(polys) if polys else np.zeros(a.shape)
                a[(a == k) & ~keep & (cov < 0.5)] = 0
        # make thin diagonal traces 4-connected
        for _ in range(2):
            A = a[:-1, :-1]; B = a[1:, 1:]; C = a[:-1, 1:]; D = a[1:, :-1]
            m1 = (A > 0) & (A == B) & (C != A) & (D != A) & (C == 0)
            C[m1] = A[m1]
            m2 = (C > 0) & (C == D) & (A != C) & (B != C) & (B == 0)
            B[m2] = C[m2]
        return a

    def _cover(self, polys, aa=4):
        """Share of each cell covered by the polygons (cell k spans k*h to (k+1)*h from the box corner)."""
        im = Image.new('L', (self.W*aa, self.H*aa), 0); d = ImageDraw.Draw(im)
        for pts in polys:
            d.polygon([(q[0]*aa-0.5, q[1]*aa-0.5) for q in (self.P(*pt) for pt in pts)], fill=1)
        f = np.array(im, dtype=float)
        er = np.ones_like(f, dtype=bool)
        er[1:, :] &= f[:-1, :] > 0; er[:-1, :] &= f[1:, :] > 0; er[:, 1:] &= f[:, :-1] > 0; er[:, :-1] &= f[:, 1:] > 0
        f[(f > 0) & ~er] = 0.5                      # PIL fills every pixel the outline touches
        return f.reshape(self.H, aa, self.W, aa).mean(axis=(1, 3))

    def cells_in_pad(self, p, L):
        im = Image.new('L', (self.W, self.H), 0); d = ImageDraw.Draw(im)
        if p['shape'] == 'circle':
            c = self.P(p['x'], p['y']); r = p['w']/2/self.h
            d.ellipse([c[0]-r, c[1]-r, c[0]+r, c[1]+r], fill=1)
        else:
            d.polygon([self.P(*q) for q in padpoly(p)], fill=1)
        m = np.array(im, bool)
        if self.centre and p['shape'] != 'circle': m = self._cover([padpoly(p)]) >= 0.5
        m = m & (self.lab[L] == self.nid.get(p['net'], -9))
        if not m.any():  # tiny pad: take nearest cell
            c = self.P(p['x'], p['y']); r, cc = int(c[1]), int(c[0])
            m = np.zeros_like(m); m[r, cc] = True
        return m

    def build(self, groups):
        """groups: dict name -> list of (ref, [padnums]).  Cells inside those pads merge into one node."""
        h = self.h; x0, _, y0, _ = self.box
        nodeid = {}; n = 0
        gid = {}
        for gname in groups: gid[gname] = n; n += 1
        gmask = {L: -np.ones((self.H, self.W), np.int64) for L in self.layers}
        for gname, items in groups.items():
            for ref, nums in items:
                for p in REF[ref]['pads']:
                    if p['num'] in nums and p['net']:
                        for L in padlayers(p):
                            if L in self.layers:
                                gmask[L][self.cells_in_pad(p, L)] = gid[gname]
        self.gid = gid
        self.gcent = {}
        for gname, k in gid.items():
            pts = []
            for L in self.layers:
                r, c = np.nonzero(gmask[L] == k)
                pts += [(x0+(cc+0.5)*h, y0+(rr+0.5)*h, ZC[L]) for rr, cc in zip(r, c)]
            self.gcent[k] = np.mean(pts, axis=0) if pts else np.zeros(3)
        for L in self.layers:
            lab = self.lab[L]; ids = -np.ones(lab.shape, np.int64)
            m = lab > 0; k = int(m.sum()); ids[m] = np.arange(n, n+k); n += k
            gm = gmask[L] >= 0; ids[gm] = gmask[L][gm]
            nodeid[L] = ids
        self.N = n; self.nodeid = nodeid
        br = []  # (n1, n2, axis, cx, cy, z, len, w, t, extra)
        for L in self.layers:
            ids = nodeid[L]; lab = self.lab[L]; z = ZC[L]; t = TH[L]
            ok = (lab[:, :-1] > 0) & (lab[:, :-1] == lab[:, 1:]) & (ids[:, :-1] != ids[:, 1:])
            r, c = np.nonzero(ok)
            for a, b, rr, cc in zip(ids[r, c], ids[r, c+1], r, c):
                br.append((a, b, 0, x0+(cc+1.0)*h, y0+(rr+0.5)*h, z, h, h, t, x0+(cc+0.5)*h, y0+(rr+0.5)*h, z, x0+(cc+1.5)*h, y0+(rr+0.5)*h, z))
            ok = (lab[:-1, :] > 0) & (lab[:-1, :] == lab[1:, :]) & (ids[:-1, :] != ids[1:, :])
            r, c = np.nonzero(ok)
            for a, b, rr, cc in zip(ids[r, c], ids[r+1, c], r, c):
                br.append((a, b, 1, x0+(cc+0.5)*h, y0+(rr+1.0)*h, z, h, h, t, x0+(cc+0.5)*h, y0+(rr+0.5)*h, z, x0+(cc+0.5)*h, y0+(rr+1.5)*h, z))
        # vias / PTH: z branches between consecutive layers holding the net at that cell
        holes = [(v['x'], v['y'], v['drill'], v['net']) for v in VIA if v['net'] in self.nid]
        for fp in FP:
            for p in fp['pads']:
                if p['drill'] is not None and p['net'] in self.nid and '*.Cu' in p['layers']:
                    holes.append((p['x'], p['y'], float(p['drill'][1]) if len(p['drill']) > 1 and p['drill'][1] != 'oval' else 0.8, p['net']))
        nv = 0
        for x, y, dr, net in holes:
            cx, cy = self.P(x, y); cc, rr = int(cx), int(cy)
            if not (0 <= rr < self.H and 0 <= cc < self.W): continue
            pres = [L for L in self.layers if self.lab[L][rr, cc] == self.nid[net]]
            for La, Lb in zip(pres, pres[1:]):
                a, b = nodeid[La][rr, cc], nodeid[Lb][rr, cc]
                if a != b:
                    X, Y = x0+(cc+0.5)*h, y0+(rr+0.5)*h
                    br.append((a, b, 2, X, Y, (ZC[La]+ZC[Lb])/2, ZC[Lb]-ZC[La], dr/2+0.02, 0, X, Y, ZC[La], X, Y, ZC[Lb]))
                    nv += 1
        self.br = np.array(br, dtype=float); self.nvia = nv
        return self

    def K(self):
        br = self.br; N = self.N
        Kt = np.zeros((N, N)); self.inv = {}; self.sel = {}
        for ax in (0, 1, 2):
            sel = np.nonzero(br[:, 2] == ax)[0]
            if len(sel) == 0: continue
            b = br[sel]; n = len(sel)
            if ax < 2:
                u = b[:, 3] if ax == 0 else b[:, 4]      # axial coord
                v = b[:, 4] if ax == 0 else b[:, 3]      # in-plane perpendicular
                z = b[:, 5]; l = b[:, 6]; gmd = 0.2235*(b[:, 7]+b[:, 8])
            else:
                u = b[:, 5]; l = b[:, 6]; gmd = b[:, 7]
            Lm = np.empty((n, n)); tab, KM = gmd_tab(self.h)
            CH = 1500
            for i0 in range(0, n, CH):
                i1 = min(n, i0+CH)
                if ax < 2:
                    dv = np.abs(v[i0:i1, None]-v[None, :]); dz = z[i0:i1, None]-z[None, :]
                    d = np.sqrt(dv**2 + dz**2)
                    k = np.rint(dv/self.h).astype(int)
                    near = k <= KM
                    if near.any():
                        zi = np.broadcast_to(z[i0:i1, None], d.shape)[near]; zj = np.broadcast_to(z[None, :], d.shape)[near]
                        kk = k[near]
                        d[near] = [tab[(a, b, c)] for a, b, c in zip(kk.tolist(), zi.tolist(), zj.tolist())]
                else:
                    d = np.sqrt((b[i0:i1, None, 3]-b[None, :, 3])**2 + (b[i0:i1, None, 4]-b[None, :, 4])**2)
                if ax == 2: d = np.maximum(d, np.maximum(gmd[i0:i1, None], gmd[None, :]))
                a1 = u[i0:i1, None]-l[i0:i1, None]/2; a2 = u[i0:i1, None]+l[i0:i1, None]/2
                b1 = u[None, :]-l[None, :]/2; b2 = u[None, :]+l[None, :]/2
                Lm[i0:i1] = mpar(a1, a2, b1, b2, d)
            # invert SPD
            c, info = lapack.dpotrf(Lm, lower=1, overwrite_a=1)
            assert info == 0, ('chol', ax, info)
            inv, info = lapack.dpotri(c, lower=1, overwrite_c=1)
            assert info == 0
            inv = np.tril(inv) + np.tril(inv, -1).T
            A = sp.csr_matrix((np.r_[np.ones(n), -np.ones(n)],
                               (np.r_[b[:, 0], b[:, 1]].astype(int), np.r_[np.arange(n), np.arange(n)])), shape=(N, n))
            T = A @ inv          # N x n dense
            Kt += A @ T.T
            self.inv[ax] = inv; self.sel[ax] = sel
            del Lm, c, T
        self.Kc = Kt
        return Kt

    def solve(self, port, stamps, extra_ports=()):
        """port=(gP,gN); stamps=list of (gA,gB,admittance 1/H). returns L [H]"""
        K = self.Kc.copy()
        reg = 1e-9*np.mean(np.diag(K)); K[np.diag_indices_from(K)] += reg
        for a, b, y in stamps:
            i, j = self.gid[a], self.gid[b]
            K[i, i] += y; K[j, j] += y; K[i, j] -= y; K[j, i] -= y
        J = np.zeros(self.N); i, j = self.gid[port[0]], self.gid[port[1]]; J[i] = 1; J[j] = -1
        phi = sla.solve(K, J, assume_a='sym')
        self.phi = phi
        return phi[i]-phi[j]

    def currents(self, phi):
        br = self.br; I = np.zeros(len(br))
        v = phi[br[:, 0].astype(int)] - phi[br[:, 1].astype(int)]
        for ax, sel in self.sel.items():
            I[sel] = self.inv[ax] @ v[sel]
        return I

    def moment(self, phi, elements):
        """magnetic moment / I (vector area, mm^2).  elements: list of (gFrom, gTo, current, zoff) for
        ideal parts (current flows gFrom->gTo inside the part) at z = centroid z + zoff"""
        I = self.currents(phi); br = self.br
        Ea = br[:, 9:12]; Eb = br[:, 12:15]
        m = 0.5*np.sum(I[:, None]*np.cross(Ea, Eb), axis=0)
        ng = len(self.gid)
        for col, E in ((0, Ea), (1, Eb)):
            nd = br[:, col].astype(int); sel = nd < ng
            C = np.array([self.gcent[k] for k in nd[sel]]) if sel.any() else np.zeros((0, 3))
            sgn = 1 if col == 0 else -1   # path C_a->E_a for a; E_b->C_b for b
            if sel.any():
                if col == 0: m += 0.5*np.sum(I[sel, None]*np.cross(C, E[sel]), axis=0)
                else: m += 0.5*np.sum(I[sel, None]*np.cross(E[sel], C), axis=0)
        for gf, gt, cur, zoff in elements:
            P = self.gcent[self.gid[gf]].copy(); Q = self.gcent[self.gid[gt]].copy(); P[2] += zoff; Q[2] += zoff
            # vertical legs from pad to body height are equal and opposite -> only the body segment counts,
            # plus legs: pad->body (P0->P), body (P->Q), body->pad (Q->Q0)
            P0 = self.gcent[self.gid[gf]]; Q0 = self.gcent[self.gid[gt]]
            m += 0.5*cur*(np.cross(P0, P) + np.cross(P, Q) + np.cross(Q, Q0))
        return m, I
