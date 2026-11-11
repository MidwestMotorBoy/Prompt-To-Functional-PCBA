"""3-D thermal model of the Monolith cup pack: four BAK N21700CX-65E cells (4S1P), the P0 board with the four loss cuts,
the MJF PA12 cup, carrier, gap filler and TPU bumpers. Finite volumes on a rectilinear voxel grid (about 0.6 x 0.6 x 1.5 mm),
implicit Euler in time, pyamg-preconditioned CG. Face conductances come from a 4x finer material grid (series along the
line between voxel centres, parallel across it), so thin layers (cell wrap, can, 1.5 mm cell gaps) keep their resistance.
The firmware policy from docs/spec.md runs inside the loop (discharge derate on the hottest cell NTC, charge ramp, board
ramp, 5 W re-advertising steps with hysteresis, USB1 priority port sharing).
Estimates, not measurements: every material value and the cell DC resistance are assumptions listed in ASSUMPTIONS.
Run: python pack3d.py [case ...]   (no args = all cases)  -> results/<case>.npz, results/<case>.json
Needs numpy, scipy, pyamg."""
import os, sys, json, time
import numpy as np, scipy.sparse as sp, pyamg

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, 'results')

# ---------------- geometry, mm (shell frame of hardware/mechanical/monolith_shell.py and monolith_cup.py) ----------------
# x across the pack (board on +x), y along the board's width, z along the cells (port end up).
PR = 11.625                                   # cell centres at (+-PR, +-PR), 23.25 mm pitch
R_CELL, R_WRAP_IN, R_CAN_IN, R_CORE = 10.85, 10.70, 10.30, 1.5   # 21.7 mm max cell; wrap and can smeared to >= 1 fine voxel
Z_C0, Z_C1 = 6.35, 77.35                      # cell bottoms / tops (71.0 mm)
END_STEEL, HEADER = 0.4, 2.5                  # can floor / cap steel, header (tab + insulator) under the + cap
CELLS = [('C1', PR, -PR, 'top'), ('C2', -PR, -PR, 'bottom'), ('C3', -PR, PR, 'top'), ('C4', PR, PR, 'bottom')]
FRONT = (0, 3)                                # C1 and C4 face the board
CAV_R, CAV_HW, CAV_XF, CAV_RF = 11.125, 22.75, 30.6, 4.0          # cup cavity: hull of the cells + rounded front box
WALL, BUMP = 1.2, 2.0
Z_SLAB_B, Z_CAP0, Z_MOUTH, Z_TOP0, Z_TOP1, Z_SLAB_T = -8.6, -4.6, -3.0, 79.0, 80.6, 88.6
BAND_B, BAND_T = (-4.6, 4.4), (71.6, 80.6)
FR_B, FR_T, WIN_R = (4.6, 6.2), (77.8, 79.0), 7.0
BOARD_X, BOARD_HW, BOARD_Z = (25.3, 26.9), 21.6, (4.3, 78.65)
FILL_Y, FILL_Z = (7.0, 16.0), (27.0, 53.0)    # gap filler / thermal-via zone, both front cells
# gap filler placements (x0, x1, |y|0, |y|1, z0, z1); only air is filled. Baseline: board B.Cu to the two front cells
FILL_ZONES = [(18.0, 25.3, 7.0, 16.0, 27.0, 53.0)]
FILL_OVER_PA12 = []                           # zones that replace carrier PA12 too (front-back beads in place of the webs)
GRID_TAG = ''
# optional graphite heat-spreader wrap round the four-cell bundle (in the 0.275 mm cell-to-cup gap): None, or
# dict(kt=in-plane conductivity x thickness, W/K, z=(z0, z1)). Added as extra voxel-to-voxel links along the sheet,
# assuming full contact where the wrap touches a can (thin PSA: ~1e-4 K m2/W, far below the sheet's spreading resistance)
SHEET = None
RAIL_Y, RAIL_Z = (6.5, 11.3), ((4.6, 23.0), (56.0, 79.0))
PORT_Y = {1: 6.5, 2: -6.5}                    # USB1 / USB2 receptacles
STAGE_Y = {1: 11.6, 2: -11.6}                 # each port's power stage sits over its own front cell (C4 / C1)
USB_X, USB_HW, USB_Z = (25.3, 28.6), 4.47, (72.6, 80.6)
WELL = (22.43, 31.43, 14.0)                   # port well through the top bumper: x span, |y|

def src_boxes():
    """heat-source boxes (x0, x1, y0, y1, z0, z1) on F.Cu (parts) and the pack path, by loss name"""
    b = {}
    for p, yc in STAGE_Y.items():
        b[f'fet{p}'] = [(26.9, 27.8, yc - 3.65, yc - 0.35, 45.4, 48.7), (26.9, 27.8, yc + 0.35, yc + 3.65, 45.4, 48.7)]
        b[f'ind{p}'] = [(26.9, 30.0, yc - 3.5, yc + 3.5, 34.5, 41.5)]
        b[f'ic{p}'] = [(26.9, 27.7, yc - 3.0, yc + 3.0, 28.0, 32.0)]
        b[f'sense{p}'] = [(26.9, 27.5, yc - 1.6, yc + 1.6, 43.0, 44.6), (26.9, 27.5, yc - 1.0, yc + 1.0, 50.0, 51.3)]
        py = PORT_Y[p]
        b[f'pphv{p}'] = [(26.9, 27.8, py - 3.0, py + 3.0, 62.0, 66.0)]
        b[f'conn{p}'] = [(USB_X[0], USB_X[1], py - USB_HW, py + USB_HW, 73.0, 77.0)]
    b['prot'] = [(26.9, 27.9, -6.0, -1.0, 10.0, 16.0), (26.9, 27.9, 1.0, 6.0, 10.0, 16.0)]   # 2 x BSC007N04LS6, 5 x 6 mm
    b['fuse'] = [(26.9, 27.9, 7.0, 11.0, 8.5, 11.5)]
    b['shunt'] = [(26.9, 27.5, -11.2, -8.0, 9.2, 10.8)]
    b['pack_cu'] = [(25.3, 26.9, -16.0, 16.0, 5.0, 20.0)]
    return b
PART_BOXES = ('fet', 'ic', 'sense', 'pphv', 'prot', 'fuse', 'shunt', 'rbat', 'rac', 'buck5')   # rev7: p0f's RBAT / RAC / TPS62933 boxes were air

# ---------------- materials ----------------
OUT, AIR, PA12, TPU, LAT, JELLY, CAN, WRAP, BOARD, VIAS, FILL, NI, PART, IND, USBC, HEAD, CORE = range(17)
NAMES = ['outside', 'air', 'PA12', 'TPU', 'TPU lattice', 'jelly roll', 'can', 'wrap', 'board', 'board + vias', 'gap filler',
         'nickel', 'part', 'inductor', 'USB-C', 'cell header', 'mandrel void']
# conductivity W/mK: (x, y, z) where anisotropic; rho*c J/m3K
K_ISO = {OUT: 1e-4, AIR: 0.038, PA12: 0.22, TPU: 0.20, LAT: 0.08, CAN: 50 * 0.25 / 0.40, WRAP: 0.16 * 0.15 / 0.10, FILL: 3.0,
         NI: 90.0, PART: 20.0, IND: 6.0, USBC: 25.0, HEAD: 3.0, CORE: 0.03}
K_JELLY_R, K_JELLY_T, K_JELLY_Z = 0.6, 20.0, 20.0        # wound layers: across (radial) vs along (circumferential, axial)
K_BOARD_IN, K_BOARD_THRU, K_VIAS_THRU = 38.0, 0.45, 8.0  # 6 layers, 2 oz outer / 0.5 oz inner; filled via array in the zone
RHOC = {OUT: 0.0, AIR: 1.2e3, PA12: 1.72e6, TPU: 2.16e6, LAT: 0.9e6, JELLY: 2.75e6, CAN: 3.8e6 * 0.25 / 0.40, WRAP: 1.9e6,
        BOARD: 3.6e6, VIAS: 3.6e6, FILL: 3.0e6, NI: 3.9e6, PART: 2.5e6, IND: 3.0e6, USBC: 3.0e6, HEAD: 1.6e6, CORE: 1.2e3}

def in_profile(x, y, off):
    """inside the cup cavity profile grown by `off` mm (hull of the cell circles and the rounded front box)"""
    R, hw, xf, rf = CAV_R + off, CAV_HW + off, CAV_XF + off, CAV_RF + off
    ay = np.abs(y); fcx, fcy = CAV_XF - CAV_RF, CAV_HW - CAV_RF
    back = np.where(ay <= PR, x >= -PR - R, (x + PR)**2 + (ay - PR)**2 <= R**2)
    mid = ay <= hw
    front = np.where(ay <= fcy, x <= xf, (x - fcx)**2 + (ay - fcy)**2 <= rf**2)
    return np.where(x < -PR, back, np.where(x <= fcx, mid, front))

def seg_dist(x, y, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay; t = np.clip(((x - ax)*vx + (y - ay)*vy) / (vx*vx + vy*vy), 0, 1)
    return np.hypot(x - ax - t*vx, y - ay - t*vy)

def materials(X, Y, Z):
    """material id and cell index (-1 = none) at broadcast points X (nx,1,1), Y (1,ny,1), Z (1,1,nz)"""
    shp = np.broadcast_shapes(X.shape, Y.shape, Z.shape)
    m = np.full(shp, OUT, np.uint8); ci = np.full(shp, -1, np.int8)
    def put(mask, v): m[np.broadcast_to(mask, shp)] = v
    p32, p12, p0 = in_profile(X, Y, WALL + BUMP), in_profile(X, Y, WALL), in_profile(X, Y, 0.0)
    put(p32 & (((Z >= Z_SLAB_B) & (Z < Z_CAP0)) | ((Z >= Z_TOP1) & (Z <= Z_SLAB_T))), LAT)
    put((Z >= Z_TOP1) & (X >= WELL[0]) & (X <= WELL[1]) & (np.abs(Y) <= WELL[2]), OUT)
    put(p32 & ~p12 & (((Z >= BAND_B[0]) & (Z < BAND_B[1])) | ((Z >= BAND_T[0]) & (Z < BAND_T[1]))), TPU)
    put(p12 & (Z >= Z_CAP0) & (Z < Z_TOP1), PA12)
    cav = p0 & (Z >= Z_MOUTH) & (Z < Z_TOP0)
    put(cav, AIR)
    put(cav & (Z < FR_B[0]) & (X < 22.7), TPU)                                        # TPU pad in the cap
    near_cell = np.zeros(shp, bool)
    for _, cx, cy, _ in CELLS: near_cell |= np.broadcast_to((X - cx)**2 + (Y - cy)**2 < WIN_R**2, shp)
    frames = cav & (X < 22.7) & (((Z >= FR_B[0]) & (Z < FR_B[1])) | ((Z >= FR_T[0]) & (Z < FR_T[1])))
    put(frames & ~near_cell, PA12)
    zc = (Z >= FR_B[0]) & (Z < FR_T[1])
    put(zc & (np.abs(X) <= 1.5) & (np.abs(Y) >= 17.35) & cav, PA12)                  # side spines
    put(zc & (X <= -17.35) & (np.abs(Y) <= 1.5) & cav, PA12)                         # back spine
    put(zc & (np.abs(X) <= 2.0) & (np.abs(np.abs(Y) - PR) <= 4.5), PA12)             # front-back webs
    rail = (X >= 22.7) & (X < BOARD_X[0]) & (np.abs(Y) >= RAIL_Y[0]) & (np.abs(Y) <= RAIL_Y[1])
    put(rail & (((Z >= RAIL_Z[0][0]) & (Z < RAIL_Z[0][1])) | ((Z >= RAIL_Z[1][0]) & (Z < RAIL_Z[1][1]))), PA12)
    fillz = (np.abs(Y) >= FILL_Y[0]) & (np.abs(Y) <= FILL_Y[1]) & (Z >= FILL_Z[0]) & (Z <= FILL_Z[1])
    def zone(x0, x1, y0, y1, z0, z1): return (X >= x0) & (X < x1) & (np.abs(Y) >= y0) & (np.abs(Y) <= y1) & (Z >= z0) & (Z <= z1)
    for zz in FILL_ZONES: put(zone(*zz) & (m == AIR), FILL)
    for zz in FILL_OVER_PA12: put(zone(*zz) & np.isin(m, (AIR, PA12)), FILL)
    brd = (X >= BOARD_X[0]) & (X < BOARD_X[1]) & (np.abs(Y) <= BOARD_HW) & (Z >= BOARD_Z[0]) & (Z < BOARD_Z[1])
    brd &= ~((np.abs(Y) > 16.6) & (Z < 9.1))
    for py in PORT_Y.values(): brd &= ~((np.abs(Y - py) <= 5.1) & (Z > 73.15))      # receptacle notches
    put(brd, BOARD); put(brd & fillz, VIAS)
    for name, boxes in src_boxes().items():
        mat = IND if name.startswith('ind') else USBC if name.startswith('conn') else PART if name.startswith(PART_BOXES) else None
        if mat is None: continue
        for x0, x1, y0, y1, z0, z1 in boxes:
            if mat == USBC: z0, z1 = USB_Z
            put((X >= x0) & (X < x1) & (Y >= y0) & (Y < y1) & (Z >= z0) & (Z < z1), mat)
    for k, (_, cx, cy, pend) in enumerate(CELLS):
        r = np.sqrt((X - cx)**2 + (Y - cy)**2)
        inc = (r < R_CELL) & (Z >= Z_C0) & (Z < Z_C1)
        hz0, hz1 = (Z_C1 - END_STEEL - HEADER, Z_C1 - END_STEEL) if pend == 'top' else (Z_C0 + END_STEEL, Z_C0 + END_STEEL + HEADER)
        mat = np.where(r >= R_WRAP_IN, WRAP, np.where((r >= R_CAN_IN) | (Z < Z_C0 + END_STEEL) | (Z >= Z_C1 - END_STEEL), CAN,
              np.where((Z >= hz0) & (Z < hz1), HEAD, np.where(r < R_CORE, CORE, JELLY))))
        mask = np.broadcast_to(inc, shp)
        m[mask] = np.broadcast_to(mat, shp)[mask]; ci[mask] = k
    # nickel: series strips (C1-C2 top, C3-C4 top, C2-C3 bottom), PACK- / PACK+ tabs from C1 / C4 bottoms to the board
    xy = dict((n, (cx, cy)) for n, cx, cy, _ in CELLS)
    top, bot = (Z >= Z_C1) & (Z < Z_C1 + 0.4), (Z >= Z_C0 - 0.4) & (Z < Z_C0)
    for a, b_, zm, w in (('C1', 'C2', top, 5.0), ('C3', 'C4', top, 5.0), ('C2', 'C3', bot, 5.0)):
        put(zm & (seg_dist(X, Y, *xy[a], *xy[b_]) <= w), NI)
    for a, ye in (('C1', -12.0), ('C4', 12.0)):
        put(bot & (seg_dist(X, Y, *xy[a], BOARD_X[0], ye) <= 2.7), NI)
    return m, ci

# ---------------- grid ----------------
NXYZ = (100, 87, 64); FINE = 4
BOX = ((-25.95, 33.85), (-25.95, 25.95), (Z_SLAB_B, Z_SLAB_T))

class Grid:
    def __init__(self, nxyz=NXYZ):
        self.n = nxyz
        self.edges = [np.linspace(lo, hi, n + 1) for (lo, hi), n in zip(BOX, nxyz)]
        self.c = [0.5*(e[1:] + e[:-1]) for e in self.edges]
        self.h = [(hi - lo)/n for (lo, hi), n in zip(BOX, nxyz)]          # mm
        self.fn = tuple(n*FINE for n in nxyz)
        self.fh = [h/FINE for h in self.h]
        self.fc = [lo + (np.arange(fn) + 0.5)*fh for (lo, _), fn, fh in zip(BOX, self.fn, self.fh)]

    def build(self):
        t0 = time.time()
        X, Y, Z = self.fc[0][:, None, None], self.fc[1][None, :, None], self.fc[2][None, None, :]
        m = np.empty(self.fn, np.uint8); ci = np.empty(self.fn, np.int8)
        step = 32
        for k in range(0, self.fn[2], step):
            m[:, :, k:k+step], ci[:, :, k:k+step] = materials(X, Y, Z[:, :, k:k+step])
        self.mf, self.cif = m, ci
        print(f'  fine materials {self.fn} in {time.time() - t0:.0f} s')
        nx, ny, nz = self.n; F = FINE
        def blocks(a):                                    # (nx*F, ny*F, nz*F) -> (nx, ny, nz, F^3)
            return a.reshape(nx, F, ny, F, nz, F).transpose(0, 2, 4, 1, 3, 5).reshape(nx, ny, nz, F**3)
        rc = np.zeros(256, np.float32)
        for k_, v in RHOC.items(): rc[k_] = v
        vol = np.prod(self.h) * 1e-9                       # m3
        self.C = (blocks(rc[m]).mean(-1) * vol).astype(np.float64)     # J/K per voxel
        out_frac = blocks((m == OUT).astype(np.float32)).mean(-1)
        self.dom = out_frac < 0.5
        # dominant material per voxel (for plotting) and per-cell volume weights
        cnt = np.stack([blocks((m == k_).astype(np.uint8)).sum(-1, dtype=np.int16) for k_ in range(17)], -1)
        self.mat = cnt.argmax(-1).astype(np.uint8)
        self.cellw = np.stack([blocks(((ci == k) & (m == JELLY)).astype(np.uint8)).sum(-1, dtype=np.int16) for k in range(4)], -1).astype(np.float32)
        self.cellany = np.stack([blocks((ci == k).astype(np.uint8)).sum(-1, dtype=np.int16) for k in range(4)], -1)
        self.niw = blocks((m == NI).astype(np.uint8)).sum(-1, dtype=np.int16).astype(np.float32)
        self.fill_cc = float((m == FILL).sum() * np.prod(self.fh) * 1e-3)
        self._conductances()
        print(f'  grid built in {time.time() - t0:.0f} s: {self.dom.sum()} active voxels')

    def kfine(self, d, k_out=None):
        """fine-grid conductivity in direction d (0 x, 1 y, 2 z); k_out overrides the outside value"""
        m = self.mf
        lut = np.zeros(256, np.float32)
        for k_, v in K_ISO.items(): lut[k_] = v
        if k_out is not None: lut[OUT] = k_out
        lut[JELLY] = K_JELLY_Z if d == 2 else K_JELLY_R
        lut[BOARD] = K_BOARD_THRU if d == 0 else K_BOARD_IN
        lut[VIAS] = K_VIAS_THRU if d == 0 else K_BOARD_IN
        k = lut[m]
        if d < 2:                                           # wound layers: radial k across, tangential k along the turns
            X, Y = self.fc[0][:, None], self.fc[1][None, :]
            for c, (_, cx, cy, _) in enumerate(CELLS):
                r = np.hypot(X - cx, Y - cy) + 1e-9
                cos2 = ((X - cx) / r)**2 if d == 0 else ((Y - cy) / r)**2
                kk = (K_JELLY_R*cos2 + K_JELLY_T*(1 - cos2)).astype(np.float32)
                sel = (m == JELLY) & (self.cif == c)
                k[sel] = np.broadcast_to(kk[:, :, None], m.shape)[sel]
        return k

    def _conductances(self):
        """face conductances (W/K) between neighbouring voxels and to the outside, from series/parallel fine lines"""
        nx, ny, nz = self.n; F = FINE
        self.G, self.Gh = [], []                            # internal faces per direction; half-voxel line resistances
        for d in range(3):
            k = self.kfine(d)
            hf = self.fh[d] * 1e-3
            r = hf / k                                     # K m2 / W per fine cell, along d
            r = np.moveaxis(r, d, 0)                       # (n_d*F, a*F, b*F)
            sh = r.shape
            r = r.reshape(sh[0] // F, F, sh[1], sh[2])
            rm, rp = r[:, :F//2].sum(1), r[:, F//2:].sum(1)  # centre->minus face, centre->plus face, per fine line
            # exterior faces: a voxel's outside fine cells are air beyond the surface, not a barrier, so give them no resistance
            re = np.moveaxis(hf / self.kfine(d, k_out=1e6), d, 0).reshape(sh[0] // F, F, sh[1], sh[2])
            rme, rpe = re[:, :F//2].sum(1), re[:, F//2:].sum(1); del re
            other = [i for i in range(3) if i != d]
            a_line = self.fh[other[0]] * self.fh[other[1]] * 1e-6
            g_line = a_line / (rp[:-1] + rm[1:])          # (n_d - 1, aF, bF)
            na, nb = self.n[other[0]], self.n[other[1]]
            G = g_line.reshape(g_line.shape[0], na, F, nb, F).sum((2, 4))
            self.G.append(np.moveaxis(G, 0, d).astype(np.float64))
            def blocksum_inv(rr, extra, a_line=a_line, na=na, nb=nb, d=d):
                g = a_line / (rr + extra)
                return np.moveaxis(g.reshape(rr.shape[0], na, F, nb, F).sum((2, 4)), 0, d)
            self.Gh.append((rme, rpe, blocksum_inv))
            del k, r

    def assemble(self, h_ext):
        """conductance matrix K (W/K) on active voxels and the exterior conductance vector"""
        nx, ny, nz = self.n
        idx = -np.ones(self.n, np.int64); idx[self.dom] = np.arange(self.dom.sum())
        self.idx = idx; N = int(self.dom.sum())
        rows, cols, vals = [], [], []
        gext = np.zeros(self.n)
        for d in range(3):
            G = self.G[d]
            sl0 = [slice(None)]*3; sl1 = [slice(None)]*3
            sl0[d] = slice(0, -1); sl1[d] = slice(1, None)
            a, b = self.dom[tuple(sl0)], self.dom[tuple(sl1)]
            both = a & b
            i0 = idx[tuple(sl0)][both]; i1 = idx[tuple(sl1)][both]; g = G[both]
            rows += [i0, i1]; cols += [i1, i0]; vals += [-g, -g]
            # exterior: active voxel next to an inactive one, or on the box boundary
            rm, rp, bs = self.Gh[d]
            gm = bs(rm, 1.0/h_ext)                         # through the minus face
            gp = bs(rp, 1.0/h_ext)
            nb_minus = np.ones(self.n, bool); nb_plus = np.ones(self.n, bool)   # neighbour is outside?
            s_hi = [slice(None)]*3; s_lo = [slice(None)]*3; s_hi[d] = slice(1, None); s_lo[d] = slice(0, -1)
            nb_minus[tuple(s_hi)] = ~self.dom[tuple(s_lo)]
            nb_plus[tuple(s_lo)] = ~self.dom[tuple(s_hi)]
            gext += np.where(self.dom & nb_minus, gm, 0) + np.where(self.dom & nb_plus, gp, 0)
        ge = gext[self.dom]
        if SHEET:
            i0, i1, g = self.sheet_links(SHEET['kt'], SHEET['z'])
            rows += [i0, i1]; cols += [i1, i0]; vals += [-g, -g]
        K = sp.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(N, N)).tocsr()
        diag = -np.asarray(K.sum(1)).ravel() + ge
        K = K + sp.diags(diag)
        return K.tocsr(), ge

    def sheet_links(self, kt, zr, step=0.05):
        """links (i0, i1, G) of a sheet wrapped round the cell bundle hull: a rounded square, R_CELL + 0.05 mm out from the
        square through the four cell centres. Walk the loop, collapse it to the voxels it passes, and link neighbours along
        the loop (kt * dz / arc) and along z (kt * arc_in_voxel / dz)"""
        R = R_CELL + 0.05
        pts = []                                           # closed loop, counter-clockwise from the front flat
        corners = [(PR, PR, 0.0), (-PR, PR, 0.5*np.pi), (-PR, -PR, np.pi), (PR, -PR, 1.5*np.pi)]
        for k, (cx, cy, a0) in enumerate(corners):
            nx_, ny_ = corners[(k + 1) % 4][:2]
            p0 = np.array([cx + R*np.cos(a0), cy + R*np.sin(a0)])   # flat from the end of the previous arc
            pp = corners[k - 1]; q = np.array([pp[0] + R*np.cos(a0), pp[1] + R*np.sin(a0)])
            n = max(2, int(np.hypot(*(p0 - q)) / step))
            pts += list(q + (p0 - q)*np.linspace(0, 1, n, endpoint=False)[:, None])
            th = a0 + np.linspace(0, 0.5*np.pi, max(2, int(0.5*np.pi*R/step)), endpoint=False)
            pts += list(np.stack([cx + R*np.cos(th), cy + R*np.sin(th)], 1))
        pts = np.array(pts)
        seg = np.hypot(*np.diff(np.vstack([pts, pts[:1]]), axis=0).T)
        ix = np.searchsorted(self.edges[0], pts[:, 0]) - 1; iy = np.searchsorted(self.edges[1], pts[:, 1]) - 1
        key = ix*10000 + iy
        runs = []                                          # (ix, iy, arc length, arc position of the run's middle)
        s = np.concatenate([[0], np.cumsum(seg)])[:-1]
        start = 0
        for j in range(1, len(key) + 1):
            if j == len(key) or key[j] != key[start]:
                runs.append((ix[start], iy[start], seg[start:j].sum(), s[start] + 0.5*seg[start:j].sum())); start = j
        if runs[0][:2] == runs[-1][:2]:                    # the loop starts mid-voxel: merge the two ends
            a, b = runs[0], runs.pop()
            runs[0] = (a[0], a[1], a[2] + b[2], b[3] - b[2]/2 + (a[2] + b[2])/2)
        L = s[-1] + seg[-1]
        kz = [k for k in range(self.n[2]) if zr[0] <= self.c[2][k] <= zr[1]]
        dz = self.h[2]
        I0, I1, G = [], [], []
        for k in kz:
            for j in range(len(runs)):
                a, b = runs[j], runs[(j + 1) % len(runs)]
                d = (b[3] - a[3]) % L
                ia, ib = self.idx[a[0], a[1], k], self.idx[b[0], b[1], k]
                if ia < 0 or ib < 0 or ia == ib: continue
                I0.append(ia); I1.append(ib); G.append(kt*dz/d)
                if k + 1 in kz:
                    ic = self.idx[a[0], a[1], k + 1]
                    if ic >= 0: I0.append(ia); I1.append(ic); G.append(kt*a[2]/dz)
        return np.array(I0), np.array(I1), np.array(G)

    def box_weights(self, boxes):
        """fraction of each box's volume in each voxel (normalised to 1 over all boxes, by volume)"""
        w = np.zeros(self.n); tot = 0.0
        for x0, x1, y0, y1, z0, z1 in boxes:
            ov = []
            for e, (lo, hi) in zip(self.edges, ((x0, x1), (y0, y1), (z0, z1))):
                ov.append(np.clip(np.minimum(e[1:], hi) - np.maximum(e[:-1], lo), 0, None))
            w += ov[0][:, None, None] * ov[1][None, :, None] * ov[2][None, None, :]
            tot += (x1 - x0)*(y1 - y0)*(z1 - z0)
        w = w / w.sum()
        return w

# ---------------- electrical model (P0 parts, BAK 65E) ----------------
CAP_AH = 6.5
SOC_PTS = [0.0, 0.02, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.0]
OCV_PTS = [2.90, 3.05, 3.16, 3.27, 3.37, 3.44, 3.50, 3.56, 3.63, 3.72, 3.83, 3.96, 4.17]   # Si-graphite / NMC shape, ~3.5 V mean
def ocv(soc): return float(np.interp(soc, SOC_PTS, OCV_PTS))
R25 = 0.014                                   # DC (10 s) resistance per cell at 25 C, mid charge: ASSUMED (AC <= 8 mOhm)
def r_cell(soc, t_c):
    f_soc = float(np.interp(soc, [0.0, 0.05, 0.10, 0.20, 0.30, 1.0], [1.8, 1.45, 1.25, 1.08, 1.0, 1.0]))
    return R25 * f_soc * float(np.exp(1500.0 * (1.0/(t_c + 273.15) - 1.0/298.15)))
P0 = dict(prot=2*0.00085, fuse=0.0025, shunt=0.001, pack_cu=0.002, nickel=0.0041, rbat=0.005, rac=0.005, fet=0.013, ind=0.012,
          core=0.15, fsw=500e3, pphv=0.018, conn=0.010, gate=0.20)
T_EDGE, T_DEAD, V_BODY, C_OSS = 10e-9, 45e-9, 0.8, 600e-12
def port_loss(p_usb, v_usb, v_bus, sink, prm=P0):
    """one BQ25756 stage + its USB side. Returns ({part: W}, battery-side current A)"""
    if p_usb <= 0: return dict(fet=0, ind=0, ic=0, sense=0, pphv=0, conn=0), 0.0
    i_usb = p_usb / v_usb; i_b = p_usb / v_bus
    for _ in range(5):
        v_hi = max(v_usb, v_bus); i_l = i_b if v_bus < v_usb else i_usb      # inductor on the low-voltage side
        fsw = prm['fsw']
        L = dict(fet=prm['fet']*i_l**2*2 + 0.5*v_hi*i_l*T_EDGE*fsw + 0.5*C_OSS*v_hi**2*fsw + 2*T_DEAD*fsw*V_BODY*i_l,
                 ind=prm['ind']*i_l**2 + prm['core']*min(1.0, v_hi/20.0), ic=prm['gate'],
                 sense=prm['rbat']*i_b**2 + prm['rac']*i_usb**2, pphv=prm['pphv']*i_usb**2, conn=prm['conn']*i_usb**2)
        tot = sum(L.values())
        i_b = (p_usb - tot)/v_bus if sink else (p_usb + tot)/v_bus
    return L, i_b

# ---------------- firmware policy (docs/spec.md, Ports, charging and power policy) ----------------
def lin(t, t0, t1, v0, v1): return float(np.interp(t, [t0, t1], [v0, v1]))
DERATE = (33.0, 39.0, 40.0)                   # hottest cell: ramp start, ramp end, sustain power (spec 10-21 policy)
DERATE_HOT = (45.0, 55.0)                     # then sustain power until the first, ramp to 0 at the second
CHG_HOT = (40.0, 45.0)                        # charge current: 4.55 A until the first, ramp to 0 at the second
def p_allow_cell(t):
    t0, t1, ps = DERATE
    if t <= t0: return 100.0
    if t <= t1: return lin(t, t0, t1, 100, ps)
    if t <= DERATE_HOT[0]: return ps
    if t <= DERATE_HOT[1]: return lin(t, DERATE_HOT[0], DERATE_HOT[1], ps, 0)
    return 0.0
BOARD_RAMP = (55.0, 70.0)
TS_PT = {1: (26.6, 11.82, 44.16), 2: (26.6, -11.20, 44.16)}   # rev7: charger TS NTCs TH401 / TH501 (F.Cu, KiCad (111.82, 97.31) / (88.80, 97.31))
def board_factor(t): return lin(t, BOARD_RAMP[0], BOARD_RAMP[1], 1, 0)
def i_chg_ramp(t):
    return float(np.interp(t, [0, 0.01, 5, 6.5, 15, 16.5, *CHG_HOT], [0, 0.65, 0.65, 3.25, 3.25, 4.55, 4.55, 0])) if t > 0 else 0.0
I_CHG_MAX, MAX_SOC, USB2_MIN = 4.55, 0.95, 20.0

# ---------------- cases ----------------
# ports: {port: (mode, contract W, V)}; 'src' = pack sources to the device, 'snk' = a charger feeds the pack
CASES = {
    'idle':        dict(title='Idle (sleep, BLE advertising)', ports={}, soc0=0.6, hours=0, idle_w=0.006),
    'dis30':       dict(title='30 W out, one port (15 V 2 A)', ports={1: ('src', 30, 15.0)}, soc0=1.0, hours=4.0, dt=20),
    'dis60':       dict(title='60 W out, one port (20 V 3 A)', ports={1: ('src', 60, 20.0)}, soc0=1.0, hours=2.5, dt=10),
    'dis100':      dict(title='100 W asked, one port (20 V 5 A)', ports={1: ('src', 100, 20.0)}, soc0=1.0, hours=2.5, dt=10),
    'dis100x2':    dict(title='100 W asked, both ports (65 W + 35 W)', ports={1: ('src', 65, 20.0), 2: ('src', 35, 15.0)},
                        soc0=1.0, hours=2.5, dt=10),
    'chg1':        dict(title='Charging, one port (100 W charger)', ports={1: ('snk', 100, 20.0)}, soc0=0.05, hours=3.0, dt=20),
    'chg2':        dict(title='Charging, both ports (2 x 45 W chargers)', ports={1: ('snk', 45, 20.0), 2: ('snk', 45, 20.0)},
                        soc0=0.05, hours=3.0, dt=20),
    'pass':        dict(title='Pass-through: 100 W charger on USB1, 30 W out of USB2', ports={1: ('snk', 100, 20.0), 2: ('src', 30, 15.0)},
                        soc0=0.20, hours=2.0, dt=20),
}

def can_point(k, ang, z):
    """a point just inside cell k's can: `ang` degrees round from the board-facing line (+x), positive away from the
    pack's y centre line (toward the board edge), at height z"""
    _, cx, cy, _ = CELLS[k]; a = np.radians(ang); r = R_CELL - 0.3
    return (cx + r*np.cos(a), cy + np.sign(cy)*r*np.sin(a), z)

def vox(g, p): return tuple(int(np.searchsorted(e, v) - 1) for e, v in zip(g.edges, p))

def ntc_points(g, ntc_front=None):
    """voxel index of each cell's NTC (assumed: on the can at mid-length, on the side facing the pack centre)
    and of an alternative spot on the front cells (board-facing side, just above the gap filler).
    ntc_front = (angle, z) moves the front cells' NTCs (C1, C4) to that spot (see can_point)"""
    pts, alt = [], []
    zm = 0.5*(Z_C0 + Z_C1)
    for k, (_, cx, cy, _) in enumerate(CELLS):
        u = -np.array([cx, cy]) / np.hypot(cx, cy)
        pts.append((cx + u[0]*(R_CELL - 0.3), cy + u[1]*(R_CELL - 0.3), zm))
        if ntc_front is not None and k in FRONT: pts[-1] = can_point(k, *ntc_front)
        alt.append((cx + (R_CELL - 0.3), cy, 56.5))
    return [vox(g, p) for p in pts], [vox(g, p) for p in alt]

def cell_surface_mask(g, k):
    """the outermost ring of cell k's voxels in each z layer (its can surface, for surface max and min)"""
    from scipy.ndimage import binary_erosion
    v = (g.cellany[..., k] >= 32) & g.dom
    return v & ~binary_erosion(v, structure=np.array([[[0], [1], [0]], [[1], [1], [1]], [[0], [1], [0]]], bool))

def run_case(g, name, h_ext=10.0, amb=25.0, verbose=True, tag='', ntc_side='centre', hours=None, ntc_front=None, probes=(), th0=None, soc0=None):
    """ntc_side: 'centre' (assumed placement) or 'board' (front-cell NTCs on the board-facing side, above the filler).
    ntc_front: (angle, z) puts the front cells' NTCs there instead (see can_point); the policy then reads TS1-TS4 only.
    probes: extra (x, y, z) points whose temperatures are recorded every step (rec_probe).
    th0, soc0: start from this temperature rise (an earlier run's 'end' snapshot) and charge state instead of cold"""
    cs = dict(CASES[name]); cs['hours'] = hours if hours is not None else cs['hours']
    K, ge = g.assemble(h_ext)
    dom = g.dom; N = K.shape[0]
    Cv = g.C[dom]
    boxes = src_boxes()
    W = {n: g.box_weights(b)[dom] for n, b in boxes.items()}
    cw = g.cellw[dom]; cw = cw / cw.sum(0)
    niw = g.niw[dom]; niw = niw / niw.sum()
    ntc, ntc_alt = ntc_points(g, ntc_front)
    ntc_i = [g.idx[v] for v in ntc]; alt_i = [g.idx[v] for v in ntc_alt]
    probe_i = [g.idx[vox(g, p)] for p in probes]
    assert min(ntc_i + alt_i + probe_i, default=0) >= 0, 'an NTC or probe point is outside the model'
    cellmask = [np.flatnonzero(((g.cellany[..., k] >= 32))[dom]) for k in range(4)]
    surfmask = [np.flatnonzero(cell_surface_mask(g, k)[dom]) for k in range(4)]
    boardmask = np.flatnonzero(np.isin(g.mat, (BOARD, VIAS))[dom])
    partmask = np.flatnonzero(np.isin(g.mat, (PART, IND))[dom])
    PART_NAMES = [n for n in boxes if n.startswith(('fet', 'ind', 'ic', 'rbat', 'rac', 'pphv', 'buck5', 'prot', 'fuse', 'shunt', 'conn'))]
    pm = {}
    for n in PART_NAMES:
        sel = (W[n] > 0) & np.isin(g.mat[dom], (PART, IND, USBC)); pm[n] = np.flatnonzero(sel if sel.any() else W[n] > 0)
    LOSS_KEYS = []
    ts_i = {p: g.idx[tuple(int(np.searchsorted(e, v) - 1) for e, v in zip(g.edges, TS_PT[p]))] for p in (1, 2)}
    # outer skin: active voxels with an exterior face
    skin = np.flatnonzero(ge > 0)
    if cs['hours'] == 0:                                  # steady state at a constant tiny load
        q = cs['idle_w'] * (0.5*W['ic1'] + 0.5*W['prot'])
        th = pyamg.smoothed_aggregation_solver(K, symmetry='symmetric').solve(q, tol=1e-10, accel='cg', maxiter=500)
        rec = dict(t=np.array([0.0]))
        snaps = {'steady': th.astype(np.float32)}
        meta = dict(name=name, title=cs['title'], peak_cell=float(th[np.concatenate(cellmask)].max()), amb=amb)
        save(g, name, rec, snaps, meta); return meta
    dt = cs['dt']; A = (sp.diags(Cv/dt) + K).tocsr()
    ml = pyamg.smoothed_aggregation_solver(A, symmetry='symmetric', max_coarse=500)
    th = np.zeros(N) if th0 is None else np.asarray(th0, float).copy()
    soc = cs['soc0'] if soc0 is None else soc0; ports = cs['ports']
    offer = 100.0; t_cut = 1e9; t_last = -1e9
    keys = ['t', 'soc', 'v_bus', 'i_bat', 'p_out', 'p_in', 'p1', 'p2', 'q_cells', 'q_board', 'q_ni', 'offer', 'i_chg']
    rec = {k: [] for k in keys}
    for k in ('ntc', 'ntc_alt', 'cell_mean', 'cell_max', 'cell_min', 'surf_max', 'surf_min'): rec[k] = []
    for k in ('board_max', 'part_max', 'ts1', 'ts2', 'skin_max', 'skin_mean', 'probe'): rec[k] = []
    rec['parts'] = []; rec['part_mean'] = []; rec['loss'] = []
    snaps = {}; best = dict(cell=-1, board=-1)
    nsteps = int(cs['hours']*3600/dt); t0 = time.time()
    snap_t = [5, 10, 20, 30, 45, 60, 90, 120, 150, 180]
    for i in range(nsteps):
        t = i*dt
        T = th + amb
        t_ntc = T[ntc_i]
        t_ctl = np.maximum(t_ntc, T[alt_i]) if ntc_side == 'board' else t_ntc
        t_hot = float(t_ctl.max())
        t_cells = np.array([float((T*cw[:, k]).sum()) for k in range(4)])
        ts = {p: float(T[ts_i[p]]) for p in (1, 2)}
        bf = min(board_factor(ts[1]), board_factor(ts[2]))
        # ---- policy ----
        src = {p: v for p, v in ports.items() if v[0] == 'src'}; snk = {p: v for p, v in ports.items() if v[0] == 'snk'}
        p_set = {}
        if src:
            target = 5.0*np.floor(min(p_allow_cell(t_hot), 100.0*bf) / 5.0 + 1e-9)
            if target < offer: offer, t_cut, t_last = target, t_hot, t
            elif target > offer and t_hot <= t_cut - 2.0 and t - t_last >= 10: offer, t_last = target, t
            req = {p: v[1] for p, v in src.items()}
            if 2 in req and 1 in req:
                g2 = min(req[2], USB2_MIN); p1 = min(req[1], max(offer - g2, 0)); p2 = min(req[2], max(offer - p1, 0))
                p_set = {1: p1, 2: p2}
            else:
                p_set = {p: min(r, offer) for p, r in req.items()}
        # ---- electrical ----
        rc = np.array([r_cell(soc, tc) for tc in t_cells])
        ocv_sum = 4*ocv(soc); r_path = P0['prot'] + P0['fuse'] + P0['shunt'] + P0['pack_cu']
        r_tot = rc.sum() + r_path + P0['nickel']
        i_bat = 0.0; L = {}; p_snk = {}
        i_chg_target = 0.0
        if snk and soc < MAX_SOC:
            i_chg_target = min(I_CHG_MAX, i_chg_ramp(t_hot), max(0.0, (16.8 - ocv_sum)/r_tot))
            i_chg_target *= bf
        for _ in range(6):
            v_bus = ocv_sum - i_bat*r_tot
            L = {}; ib_src = 0.0
            for p, pw in p_set.items():
                L[p], ib = port_loss(pw, src[p][2], v_bus, False); ib_src += ib
            ib_snk = 0.0
            if snk:
                need = i_chg_target + ib_src                      # sinks also carry the pass-through load
                share = need / len(snk)
                for p, (_, cap, vu) in snk.items():
                    pw = share*v_bus*1.04
                    for _ in range(4):                            # solve the charger input that delivers `share` to the bus
                        Lp, ib = port_loss(pw, vu, v_bus, True)
                        pw = min(cap, pw + (share - ib)*v_bus)
                    Lp, ib = port_loss(pw, vu, v_bus, True)
                    L[p] = Lp; p_snk[p] = pw; ib_snk += ib
            i_bat = ib_src - ib_snk
        q_cells = rc * i_bat**2
        q_path = {n: P0[n]*i_bat**2 for n in ('prot', 'fuse', 'shunt', 'pack_cu')}
        q_ni = P0['nickel']*i_bat**2
        q = (cw * q_cells[None, :]).sum(1) + niw*q_ni
        for n, w in q_path.items(): q = q + W[n]*w
        for p, Lp in L.items():
            for part, w in Lp.items(): q = q + W[f'{part}{p}']*w
        q_board = sum(q_path.values()) + sum(sum(Lp.values()) for Lp in L.values())
        # ---- record ----
        T_all = T
        rec['t'].append(t/60); rec['soc'].append(soc); rec['v_bus'].append(v_bus); rec['i_bat'].append(i_bat)
        rec['p_out'].append(sum(p_set.values())); rec['p_in'].append(sum(p_snk.values()))
        rec['p1'].append(p_set.get(1, -p_snk.get(1, 0))); rec['p2'].append(p_set.get(2, -p_snk.get(2, 0)))
        rec['q_cells'].append(q_cells.sum()); rec['q_board'].append(q_board); rec['q_ni'].append(q_ni)
        rec['offer'].append(offer if src else 0); rec['i_chg'].append(max(0.0, -i_bat))
        rec['ntc'].append(t_ntc.tolist()); rec['ntc_alt'].append(T[alt_i].tolist()); rec['cell_mean'].append(t_cells.tolist())
        rec['cell_max'].append([float(T[m].max()) for m in cellmask]); rec['cell_min'].append([float(T[m].min()) for m in cellmask])
        rec['surf_max'].append([float(T[m].max()) for m in surfmask]); rec['surf_min'].append([float(T[m].min()) for m in surfmask])
        rec['board_max'].append(float(T[boardmask].max())); rec['part_max'].append(float(T[partmask].max()))
        rec['ts1'].append(ts[1]); rec['ts2'].append(ts[2]); rec['probe'].append(T[probe_i].tolist())
        rec['skin_max'].append(float(T[skin].max())); rec['skin_mean'].append(float(T[skin].mean()))
        rec['parts'].append([float(T[pm[n]].max()) for n in PART_NAMES]); rec['part_mean'].append([float(T[pm[n]].mean()) for n in PART_NAMES])
        lv = {f'{part}{p}': w for p, Lp in L.items() for part, w in Lp.items()}; lv.update(q_path)
        rec['loss'].append([float(lv.get(n, 0.0)) for n in PART_NAMES])
        cm = max(rec['cell_max'][-1]); bm = rec['part_max'][-1]
        if cm > best['cell']: best['cell'] = cm; snaps['peak_cell'] = th.astype(np.float32); best['t_cell'] = t/60
        if bm > best['board']: best['board'] = bm; snaps['peak_board'] = th.astype(np.float32); best['t_board'] = t/60
        if snap_t and t/60 >= snap_t[0]: snaps[f't{snap_t.pop(0)}'] = th.astype(np.float32)
        # ---- step ----
        b = Cv/dt*th + q
        th = ml.solve(b, x0=th, tol=1e-5, accel='cg', maxiter=60)
        soc -= i_bat*dt/3600/CAP_AH
        v_cell_min = (ocv(soc) - i_bat*rc.max())
        done = (src and not snk and (soc <= 0.0 or v_cell_min < 2.8)) or (snk and soc >= MAX_SOC and not src) \
            or (snk and src and soc >= MAX_SOC and t > 3600)
        if verbose and i % max(1, int(600/dt)) == 0:
            print(f'   {name} t={t/60:6.1f} min soc={soc:5.2f} P={sum(p_set.values()):5.1f}/{sum(p_snk.values()):5.1f} W  I={i_bat:5.2f} A  '
                  f'cells {q_cells.sum():4.2f} W board {q_board:4.2f} W  NTC max {t_hot:5.1f}  cell max {cm:5.1f}  part {bm:5.1f}  '
                  f'({time.time() - t0:.0f} s)')
        if done: break
    snaps['end'] = th.astype(np.float32)
    rec = {k: np.array(v) for k, v in rec.items()}
    meta = dict(name=name, title=cs['title'], amb=amb, h_ext=h_ext, dt=dt, t_end=float(rec['t'][-1]),
                t_peak_cell=best['t_cell'], t_peak_board=best['t_board'], ntc_side=ntc_side, r25=R25,
                ntc_front=ntc_front, derate=DERATE, derate_hot=DERATE_HOT, chg_hot=CHG_HOT, part_names=PART_NAMES,
                board_ramp=list(BOARD_RAMP))
    save(g, name + tag, rec, snaps, meta)
    return meta

def save(g, name, rec, snaps, meta):
    os.makedirs(OUT_DIR, exist_ok=True)
    np.savez_compressed(os.path.join(OUT_DIR, f'{name}.npz'), **{f'rec_{k}': v for k, v in rec.items()},
                        **{f'snap_{k}': v for k, v in snaps.items()})
    with open(os.path.join(OUT_DIR, f'{name}.json'), 'w') as f: json.dump(meta, f, indent=1)

def get_grid():
    cache = os.path.join(OUT_DIR, f'grid{GRID_TAG}.npz')
    g = Grid()
    if os.path.exists(cache):
        z = np.load(cache, allow_pickle=True)
        for k in ('C', 'dom', 'mat', 'cellw', 'cellany', 'niw'): setattr(g, k, z[k])
        g.fill_cc = float(z['fill_cc']) if 'fill_cc' in z else None
        g.G = [z[f'G{d}'] for d in range(3)]
        g.Gh = []
        for d in range(3):
            rm, rp = z[f'rm{d}'], z[f'rp{d}']
            other = [i for i in range(3) if i != d]; F = FINE
            a_line = g.fh[other[0]]*g.fh[other[1]]*1e-6; na, nb = g.n[other[0]], g.n[other[1]]
            def bs(rr, extra, a_line=a_line, na=na, nb=nb, d=d):
                gg = a_line/(rr + extra)
                return np.moveaxis(gg.reshape(rr.shape[0], na, F, nb, F).sum((2, 4)), 0, d)
            g.Gh.append((rm, rp, bs))
        return g
    g.build()
    os.makedirs(OUT_DIR, exist_ok=True)
    np.savez_compressed(cache, fill_cc=g.fill_cc, C=g.C, dom=g.dom, mat=g.mat, cellw=g.cellw, cellany=g.cellany, niw=g.niw,
                        **{f'G{d}': g.G[d] for d in range(3)}, **{f'rm{d}': g.Gh[d][0] for d in range(3)},
                        **{f'rp{d}': g.Gh[d][1] for d in range(3)})
    return g

if __name__ == '__main__':
    g = get_grid()
    cells_c = [float(g.C[(g.cellany[..., k] >= 32)].sum()) for k in range(4)]
    print(f'  heat capacity: each cell ~{np.mean(cells_c):.0f} J/K, whole pack {g.C.sum():.0f} J/K')
    names = sys.argv[1:] or list(CASES)
    for n in names:
        print(f'case {n}: {CASES[n]["title"]}'); m = run_case(g, n); print('  ', m)
