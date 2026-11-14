"""blib.py: team B's board-as-data library (placement transform, fixed list, legality, cost terms).

Used by secplace.py, check.py, stitch.py, blame.py. Host python (numpy, shapely not needed).

  python3 blib.py pads <placement.json> [--partial]   prints {ref: {pad num: [[x, y], ...]}} for every present part
                                                        (screen.sh feeds this to apply_b.py as the pad check)
  python3 blib.py info <ref>                           local pads and courtyard of one part

Placement entry: [x, y, turn] or [x, y, turn, side]. turn is 0/90/180/270 relative to the template orientation,
the shared apply_placement.py convention: per quarter turn a local offset (lx, ly) becomes (-ly, lx). side "F"/"B"
(also "F.Cu"/"B.Cu"); when it differs from the template side the part is flipped: local x is mirrored first
(lx -> -lx), then turned. Local offsets are measured from the footprint origin in the template board.

Board data: tools/floorplan/example/monolith/board_dump.json (same positions as tools/score/template/board.kicad_pcb);
real outline and pin names from tools/data/board_extra.json (cu_dump of the bare template)."""
import json, os, re, sys, math
from collections import defaultdict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TEAM = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(TEAM, "..", "..", ".."))
EX = os.path.join(REPO, "tools", "floorplan", "example", "monolith")
DUMP = os.path.join(EX, "board_dump.json")
CONS = os.path.join(EX, "constraints.json")
BOXES = os.path.join(TEAM, "plan", "boxes_B1.json")
CLUSTERS = os.path.join(TEAM, "plan", "clusters_movable.json")
EXTRA = os.path.join(HERE, "data", "board_extra.json")
FRAGS = os.path.join(TEAM, "fragments")

GAP = 0.02          # courtyard to courtyard, mm
EDGE = 0.5          # courtyard to board outline
SETBACK = 0.4       # courtyard to the group's region line
GROUPS = ("port1", "port2", "pack")
NEVER_TARGET = {"GND", "PACK_P", "3V3"}

def rot(x, y, q):
    q %= 4
    if q == 0: return x, y
    if q == 1: return -y, x
    if q == 2: return -x, -y
    return y, -x

def tbox(b, flip, q):
    """local box (x0, y0, x1, y1) -> flipped (mirror x) then turned q quarter turns"""
    if flip: b = (-b[2], b[1], -b[0], b[3])
    a = rot(b[0], b[1], q); c = rot(b[2], b[3], q)
    return (min(a[0], c[0]), min(a[1], c[1]), max(a[0], c[0]), max(a[1], c[1]))

def side1(s):
    s = str(s)
    return "B" if s[:1] == "B" else "F"

def inter(a, b, m=0.0):
    """boxes overlap by more than nothing when a is grown by m"""
    return a[0] - m < b[2] and a[2] + m > b[0] and a[1] - m < b[3] and a[3] + m > b[1]

def overlap_xy(a, b):
    return min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1])

def grow(b, m): return (b[0] - m, b[1] - m, b[2] + m, b[3] + m)

def box_gap(a, b):
    """edge to edge distance of two boxes (0 if they touch or overlap)"""
    dx = max(0.0, max(a[0], b[0]) - min(a[2], b[2])); dy = max(0.0, max(a[1], b[1]) - min(a[3], b[3]))
    return math.hypot(dx, dy)

def group_of_section(name):
    if name.startswith("USB Port 1"): return "port1"
    if name.startswith("USB Port 2"): return "port2"
    return "pack"

def map_ref(ref, m):
    """'4->5': R424 -> R524 (first digit of the number)"""
    a, b = m.split("->"); mm = re.match(r"([A-Z]+)(\d+)$", ref)
    if not mm or not mm.group(2).startswith(a): return None
    return mm.group(1) + b + mm.group(2)[len(a):]

def load_placement(path):
    """fragment or placement json -> {ref: [x, y, turn, side or None]}"""
    P = json.load(open(path)); out = {}
    for r, v in P.items():
        if r.startswith("_"): continue
        out[r] = [float(v[0]), float(v[1]), int(round(float(v[2]))) % 360, side1(v[3]) if len(v) > 3 and v[3] else None]
    return out


class Board:
    def __init__(self, dump=DUMP, cons=CONS, boxes=BOXES, clusters=CLUSTERS, extra=EXTRA):
        d = json.load(open(dump)); self.D = d
        self.C = json.load(open(cons)); self.BX = json.load(open(boxes)); self.CL = json.load(open(clusters))
        ex = json.load(open(extra)); self.pinfn = ex["pinfn"]; self.outline = ex["outline"][0]["ring"]
        self.parts = {}
        for f in d["fps"]:
            c = f["court"]
            self.parts[f["ref"]] = dict(ref=f["ref"], x0=f["x"], y0=f["y"], side=side1(f["side"]), sheet=f["sheet"].strip("/"), value=f["value"],
                                        court=(c[0] - f["x"], c[1] - f["y"], c[2] - f["x"], c[3] - f["y"]), pads=[])
        self.nets = defaultdict(list)          # net -> [(ref, pad index)]
        for p in d["pads"]:
            P = self.parts[p["ref"]]
            if not p["layers"]: continue       # paste-only apertures: no copper
            sides = set()
            for L in p["layers"]:
                if L == "*.Cu": sides |= {"F", "B"}
                elif L == "F.Cu": sides.add("F")
                elif L == "B.Cu": sides.add("B")
            if len(p["layers"]) >= 6: sides |= {"F", "B"}
            b = p["box"]
            P["pads"].append(dict(num=p["num"], net=p["net"], lx=p["x"] - P["x0"], ly=p["y"] - P["y0"],
                                  box=(b[0] - P["x0"], b[1] - P["y0"], b[2] - P["x0"], b[3] - P["y0"]), sides=frozenset(sides),
                                  clearance=bool(p.get("clearance"))))
            if p["net"]: self.nets[p["net"]].append((p["ref"], len(P["pads"]) - 1))
        # movable refs by section and group, B1 boxes
        self.section_of = {}; self.group_of = {}; self.block_of = {}
        for name, refs in self.CL.items():
            for r in refs:
                self.section_of[r] = name; self.group_of[r] = group_of_section(name)
                self.block_of[r] = self.BX["blocks"].get(name)
        self.movable = set(self.section_of)
        self.fixed = set(self.parts) - self.movable
        fx = set(self.BX.get("fixed_extra", []))
        rule = {r for r in self.parts if re.match(r"[A-Z]+", r).group() in ("J", "H", "TP", "SW")} | fx
        if rule != self.fixed: print(f"blib: fixed list differs from the prefix rule: {sorted(rule ^ self.fixed)}", file=sys.stderr)
        self.regions = self.BX["regions"]
        # nets: power / return (constraints) and plane nets
        self.power = {"GND"}
        bn = sorted(self.nets)
        def board_net(n):
            for b in bn:
                if b == n or b == "/" + n or b.endswith("/" + n): return b
            return None
        self.board_net = board_net
        for n, f in self.C.get("nets", {}).items():
            if f.get("current_a") and f.get("kind") in ("power", "switching"):
                b = board_net(n)
                if b: self.power.add(b)
        self.npads = {r: len([p for p in P["pads"] if p["num"]]) for r, P in self.parts.items()}
        # outline: inside-box and the outside rectangles (rectilinear outline)
        xs = sorted({p[0] for p in self.outline}); ys = sorted({p[1] for p in self.outline})
        self.obox = (xs[0], ys[0], xs[-1], ys[-1]); self.outside = []
        for i in range(len(xs) - 1):
            for j in range(len(ys) - 1):
                cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
                if not self.point_in_outline(cx, cy): self.outside.append((xs[i], ys[j], xs[i + 1], ys[j + 1]))
        self.keepouts = [k for k in d.get("keepouts", []) if k.get("no_footprints")]

    def point_in_outline(self, x, y):
        R = self.outline; n = len(R); c = False
        for i in range(n):
            x1, y1 = R[i]; x2, y2 = R[(i + 1) % n]
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1): c = not c
        return c

    # ---- pin names
    def pin_pads(self, ref, pin):
        """'24' or 'REGN' -> list of pad numbers of ref"""
        nums = {p["num"] for p in self.parts[ref]["pads"]}
        if pin in nums: return [pin]
        t = self.C.get("pin_pads", {}).get(f"{ref}.{pin}")
        if t: return list(t)
        out = [n for n, fn in self.pinfn.get(ref, {}).items() if fn == pin or fn.rsplit("_", 1)[0] == pin]
        return out

    def is_signal_net(self, n):
        return bool(n) and len(self.nets.get(n, ())) >= 2 and n not in self.power and n not in NEVER_TARGET and not n.endswith("/GND")

    def served_pads(self, ref):
        """(chip, [pad nums]) of the pin that constraints 'serves' declares for ref, or None"""
        s = self.C.get("serves", {}).get(ref)
        if not s: return None
        chip, pin = s.split(".", 1)
        if chip not in self.parts: return None
        return chip, self.pin_pads(chip, pin)

    # ---- transform
    def norm(self, ref, v):
        """placement value -> (x, y, q, side, flip)"""
        P = self.parts[ref]
        if v is None: return (P["x0"], P["y0"], 0, P["side"], False)
        s = side1(v[3]) if len(v) > 3 and v[3] else P["side"]
        return (float(v[0]), float(v[1]), int(round(float(v[2]))) // 90 % 4, s, s != P["side"])

    def court(self, ref, v=None):
        x, y, q, s, fl = self.norm(ref, v); b = tbox(self.parts[ref]["court"], fl, q)
        return (x + b[0], y + b[1], x + b[2], y + b[3]), s

    def pads(self, ref, v=None):
        """[(num, net, cx, cy, box, sides)] in board coordinates"""
        x, y, q, s, fl = self.norm(ref, v); out = []
        for p in self.parts[ref]["pads"]:
            lx = -p["lx"] if fl else p["lx"]; dx, dy = rot(lx, p["ly"], q); b = tbox(p["box"], fl, q)
            sides = frozenset({"F": "B", "B": "F"}[t] for t in p["sides"]) if fl else p["sides"]
            out.append((p["num"], p["net"], x + dx, y + dy, (x + b[0], y + b[1], x + b[2], y + b[3]), sides))
        return out

    def local_pads(self, ref, q, flip):
        """pad offsets for a turn and flip: [(num, net, dx, dy, box offset, sides)]"""
        out = []
        for p in self.parts[ref]["pads"]:
            lx = -p["lx"] if flip else p["lx"]; dx, dy = rot(lx, p["ly"], q); b = tbox(p["box"], flip, q)
            sides = frozenset({"F": "B", "B": "F"}[t] for t in p["sides"]) if flip else p["sides"]
            out.append((p["num"], p["net"], dx, dy, b, sides))
        return out

    def is_chip(self, ref):
        return ref.startswith("U") and self.npads.get(ref, 0) >= 12

    def stand_in_boxes(self, group):
        """B1 boxes of the sections of a group that hold a chip with 12 pads or more: [(name, box, side)]"""
        out = []
        for name, refs in self.CL.items():
            if group_of_section(name) != group: continue
            if not any(self.is_chip(r) for r in refs): continue
            b = self.BX["blocks"].get(name)
            if b: out.append((name, tuple(b), "B" if name.endswith("B.Cu") else "F"))
        return out


def chip_rows(B, ref, v, signal_only=True):
    """pad rows of a chip: [(side W/E/N/S, row box, [pad nums], has signal)] at placement v"""
    pads = [p for p in B.pads(ref, v) if p[0]]
    if not pads: return []
    x0 = min(p[4][0] for p in pads); y0 = min(p[4][1] for p in pads); x1 = max(p[4][2] for p in pads); y1 = max(p[4][3] for p in pads)
    rows = defaultdict(list)
    for p in pads:
        b = p[4]; d = {"W": b[0] - x0, "E": x1 - b[2], "N": b[1] - y0, "S": y1 - b[3]}
        k = min(d, key=d.get)
        if d[k] > 0.3: continue                  # thermal pad or inner pad
        rows[k].append(p)
    out = []
    for k, ps in rows.items():
        rb = (min(p[4][0] for p in ps), min(p[4][1] for p in ps), max(p[4][2] for p in ps), max(p[4][3] for p in ps))
        sig = any(B.is_signal_net(p[1]) for p in ps)
        if signal_only and not sig: continue
        out.append((k, rb, sorted({p[0] for p in ps}), sig))
    return out


class Layout:
    """Present parts (fixed at the template + placed), plus rings, reserved boxes, claims and stand-in obstacles."""
    def __init__(self, B, placed=None, group=None, fixed=True):
        self.B = B; self.group = group
        self.P = {}                     # ref -> normalized (x, y, q, side, flip)
        if fixed:
            for r in B.fixed: self.P[r] = B.norm(r, None)
        self.rings = []                 # dict(chip, mm, rows=[(side, box, pads)], allow=set)
        self.reserved = []              # dict(name, box, sides, except)
        self.claims = {}                # ref -> box
        self.stand = []                 # (name, box, side)
        self.cache = {}
        for r, v in (placed or {}).items(): self.put(r, v)

    def put(self, r, v):
        n = self.B.norm(r, v) if not (isinstance(v, tuple) and len(v) == 5) else v
        self.P[r] = n; self.cache.pop(r, None)

    def remove(self, r):
        self.P.pop(r, None); self.cache.pop(r, None)

    def val(self, r):
        x, y, q, s, fl = self.P[r]; return [round(x, 6), round(y, 6), q * 90, s]

    def geom(self, r):
        if r not in self.cache:
            x, y, q, s, fl = self.P[r]; v = (x, y, q * 90, s)
            c, _ = self.B.court(r, v); self.cache[r] = (c, s, self.B.pads(r, v))
        return self.cache[r]

    # ---- obstacle lists for one side
    def courts(self, side, skip=()):
        return [(q, self.geom(q)[0]) for q in self.P if q not in skip and self.geom(q)[1] == side]

    def far_pads_onto(self, side, skip=()):
        """pads of parts on the other side that reach this side: [(ref, box)]"""
        out = []
        for q in self.P:
            if q in skip: continue
            c, s, pads = self.geom(q)
            if s == side: continue
            for p in pads:
                if side in p[5]: out.append((q, p[4]))
        return out

    def ring_boxes(self, r, side):
        """ring rows that apply to part r: [(chip, grown row box)]"""
        out = []
        for g in self.rings:
            if g["chip"] == r or g["chip"] not in self.P or self.geom(g["chip"])[1] != side: continue
            sv = self.B.served_pads(r)
            for k, rb, nums in g["rows"]:
                m = g["mm"]
                if r in g.get("allow", ()) or (sv and sv[0] == g["chip"] and set(sv[1]) & set(nums)): m = min(m, g.get("serves_mm", 0.3))
                out.append((g["chip"], grow(rb, m)))
        return out

    def add_ring(self, chip, mm=0.8, allow=(), serves_mm=0.3):
        x, y, q, s, fl = self.P[chip]
        rows = [(k, rb, nums) for k, rb, nums, sig in chip_rows(self.B, chip, (x, y, q * 90, s))]
        self.rings = [g for g in self.rings if g["chip"] != chip]
        self.rings.append(dict(chip=chip, mm=mm, rows=rows, allow=set(allow), serves_mm=serves_mm))

    def region_ok_box(self, r):
        """(region box inset, claim box or None) for movable part r"""
        g = self.B.group_of.get(r)
        if not g: return None, None
        R = self.B.regions[g]; Ri = (R[0] + SETBACK, R[1] + SETBACK, R[2] - SETBACK, R[3] - SETBACK)
        return Ri, self.claims.get(r)

    # ---- exact legality of one part at a pose (other present parts as they are)
    def faults(self, r, v=None, region=True, rings=True, reserved=True):
        B = self.B
        if v is None: x, y, q, s, fl = self.P[r]; v = (x, y, q * 90, s)
        c, s = B.court(r, v); pads = B.pads(r, v); out = []
        for q2, c2 in self.courts(s, skip=(r,)):
            if inter(c, c2, GAP): out.append(f"courtyard {q2}")
        for name, b, s2 in self.stand:
            if s2 == s and inter(c, b): out.append(f"stand-in box {name[:40]}")
        for k in B.keepouts:
            if (s + ".Cu") in k["layers"] and inter(c, k["box"]): out.append(f"keep-out {k['name'] or 'unnamed'}")
        ob = B.obox
        if c[0] < ob[0] + EDGE or c[1] < ob[1] + EDGE or c[2] > ob[2] - EDGE or c[3] > ob[3] - EDGE or any(inter(c, o, EDGE) for o in B.outside):
            out.append("board edge")
        other = "B" if s == "F" else "F"
        for p in pads:
            if other in p[5]:
                for q2, c2 in self.courts(other, skip=(r,)):
                    if inter(p[4], c2): out.append(f"own far-side pad under {q2}")
        for q2, pb in self.far_pads_onto(s, skip=(r,)):
            if inter(c, pb): out.append(f"on far-side pad of {q2}")
        if reserved:
            for z in self.reserved:
                if s in z["sides"] and r not in z.get("except", ()) and inter(c, z["box"]): out.append(f"reserved {z['name']}")
        if rings:
            for chip, rb in self.ring_boxes(r, s):
                if inter(c, rb): out.append(f"ring {chip}")
        if region and r in B.movable:
            Ri, cl = self.region_ok_box(r)
            inside = lambda b: c[0] >= b[0] - 1e-6 and c[1] >= b[1] - 1e-6 and c[2] <= b[2] + 1e-6 and c[3] <= b[3] + 1e-6
            if not inside(Ri) and not (cl and inside(cl)): out.append(f"outside region {B.group_of[r]}")
        return sorted(set(out))

    # ---- legality on a grid (numpy), the greedy_fill.py stamping
    def legal_mask(self, r, q, side, xs, ys, static_only=False, region=True):
        """bool [len(ys), len(xs)]: True where r at (x, y, turn q, side) is legal"""
        B = self.B; fl = side != B.parts[r]["side"]
        b = tbox(B.parts[r]["court"], fl, q)
        bad = np.zeros((len(ys), len(xs)), bool)
        ob = B.obox
        bad[:, (xs + b[0] < ob[0] + EDGE) | (xs + b[2] > ob[2] - EDGE)] = True
        bad[(ys + b[1] < ob[1] + EDGE) | (ys + b[3] > ob[3] - EDGE), :] = True
        X0, X1, Y0, Y1 = xs[0] + b[0], xs[-1] + b[2], ys[0] + b[1], ys[-1] + b[3]
        def stamp(o, bb, m=0.0):
            if o[2] + m <= X0 - 1 or o[0] - m >= X1 + 1 or o[3] + m <= Y0 - 1 or o[1] - m >= Y1 + 1: return
            i0 = np.searchsorted(xs, o[0] - m - bb[2], "right"); i1 = np.searchsorted(xs, o[2] + m - bb[0], "left")
            j0 = np.searchsorted(ys, o[1] - m - bb[3], "right"); j1 = np.searchsorted(ys, o[3] + m - bb[1], "left")
            if i1 > i0 and j1 > j0: bad[j0:j1, i0:i1] = True
        for o in B.outside: stamp(o, b, EDGE)
        for k in B.keepouts:
            if (side + ".Cu") in k["layers"]: stamp(k["box"], b)
        other = "B" if side == "F" else "F"
        lp = B.local_pads(r, q, fl)
        far = [p[4] for p in lp if other in p[5]]
        if static_only:
            for q2 in B.fixed:
                c2, s2 = B.court(q2)
                if s2 == side: stamp(c2, b, GAP)
                elif far:
                    for pb in far: stamp(c2, pb)
            for q2 in B.fixed:
                c2, s2 = B.court(q2)
                if s2 != side:
                    for p in B.pads(q2):
                        if side in p[5]: stamp(p[4], b)
            return ~bad
        for q2, c2 in self.courts(side, skip=(r,)): stamp(c2, b, GAP)
        for name, bx, s2 in self.stand:
            if s2 == side: stamp(bx, b)
        for q2, pb in self.far_pads_onto(side, skip=(r,)): stamp(pb, b)
        if far:
            for q2, c2 in self.courts(other, skip=(r,)):
                for pb in far: stamp(c2, pb)
        for z in self.reserved:
            if side in z["sides"] and r not in z.get("except", ()): stamp(z["box"], b)
        for chip, rb in self.ring_boxes(r, side): stamp(rb, b)
        ok = ~bad
        if region and r in B.movable:
            Ri, cl = self.region_ok_box(r)
            def inside(R):
                mx = (xs + b[0] >= R[0] - 1e-6) & (xs + b[2] <= R[2] + 1e-6); my = (ys + b[1] >= R[1] - 1e-6) & (ys + b[3] <= R[3] + 1e-6)
                return my[:, None] & mx[None, :]
            reg = inside(Ri)
            if cl: reg = reg | inside(cl)
            ok &= reg
        return ok

    # ---- cost terms on a grid
    def present_pads_of_net(self, n, skip=()):
        out = []
        for ref, i in self.B.nets.get(n, []):
            if ref in self.P and ref not in skip:
                p = self.geom(ref)[2][i]; out.append(p)
        return out

    def hpwl_growth(self, r, q, side, xs, ys, nets):
        """half-perimeter growth of the given nets of r over the present pads, every grid spot"""
        fl = side != self.B.parts[r]["side"]; lp = self.B.local_pads(r, q, fl)
        X = xs[None, :]; Y = ys[:, None]; c = np.zeros((len(ys), len(xs)))
        for n in nets:
            off = [(p[2], p[3]) for p in lp if p[1] == n]
            if not off: continue
            qq = [(p[2], p[3]) for p in self.present_pads_of_net(n, skip=(r,))]
            ox0 = min(a for a, _ in off); ox1 = max(a for a, _ in off); oy0 = min(b for _, b in off); oy1 = max(b for _, b in off)
            if not qq: c = c + (ox1 - ox0) + (oy1 - oy0); continue
            qx0 = min(a for a, _ in qq); qx1 = max(a for a, _ in qq); qy0 = min(b for _, b in qq); qy1 = max(b for _, b in qq)
            c = c + (np.maximum(qx1, X + ox1) - np.minimum(qx0, X + ox0) - (qx1 - qx0)) + (np.maximum(qy1, Y + oy1) - np.minimum(qy0, Y + oy0) - (qy1 - qy0))
        return c

    def target_cost(self, r, q, side, xs, ys, targets):
        """targets {pad num: [target pad (num, net, cx, cy, box, sides)]}: (sum of Manhattan pad-centre distance to the
        nearest target pad, worst edge-to-edge gap) arrays"""
        fl = side != self.B.parts[r]["side"]; lp = self.B.local_pads(r, q, fl)
        X = xs[None, :]; Y = ys[:, None]; cost = np.zeros((len(ys), len(xs))); worst = np.zeros((len(ys), len(xs)))
        for num, tl in targets.items():
            mine = [p for p in lp if p[0] == num]
            if not mine or not tl: continue
            p = mine[0]; hw = (p[4][2] - p[4][0]) / 2; hh = (p[4][3] - p[4][1]) / 2
            dm = None; dg = None
            for t in tl:
                thw = (t[4][2] - t[4][0]) / 2; thh = (t[4][3] - t[4][1]) / 2
                ax = np.abs(X + p[2] - t[2]); ay = np.abs(Y + p[3] - t[3])
                m = ax + ay; g = np.hypot(np.maximum(0, ax - hw - thw), np.maximum(0, ay - hh - thh))
                dm = m if dm is None else np.minimum(dm, m); dg = g if dg is None else np.minimum(dg, g)
            cost = cost + dm; worst = np.maximum(worst, dg)
        return cost, worst

    def pads_between(self, a, b, layer_side, nets_ok, skip=()):
        """pads of other nets crossed by the straight segment from a to b (points) on one side"""
        hits = []
        for q2 in self.P:
            if q2 in skip: continue
            c, s, pads = self.geom(q2)
            for p in pads:
                if layer_side not in p[5] or p[1] in nets_ok: continue
                if seg_box(a, b, p[4]): hits.append(f"{q2}.{p[0]}")
        return hits


def seg_box(a, b, bx):
    """segment a-b crosses box (Liang-Barsky)"""
    x0, y0 = a; dx, dy = b[0] - a[0], b[1] - a[1]; t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - bx[0]), (dx, bx[2] - x0), (-dy, y0 - bx[1]), (dy, bx[3] - y0)):
        if abs(p) < 1e-12:
            if q < 0: return False
        else:
            t = q / p
            if p < 0: t0 = max(t0, t)
            else: t1 = min(t1, t)
            if t0 > t1: return False
    return True

def closest_points(a, b):
    """closest points of two boxes"""
    def cl(lo1, hi1, lo2, hi2):
        if hi1 < lo2: return hi1, lo2
        if hi2 < lo1: return lo1, hi2
        m = (max(lo1, lo2) + min(hi1, hi2)) / 2; return m, m
    x1, x2 = cl(a[0], a[2], b[0], b[2]); y1, y2 = cl(a[1], a[3], b[1], b[3])
    return (x1, y1), (x2, y2)

def hpwl(B, placed):
    """hpwl.py's measure: nets with 2 to 11 pads, pad level, the rest at the template"""
    tot = 0.0
    for n, lst in B.nets.items():
        if not 2 <= len(lst) < 12: continue
        pts = []
        for ref, i in lst:
            v = placed.get(ref); p = B.pads(ref, v)[i]; pts.append((p[2], p[3]))
        tot += max(a for a, _ in pts) - min(a for a, _ in pts) + max(b for _, b in pts) - min(b for _, b in pts)
    return tot

def load_meta(path):
    try: return json.load(open(path))
    except Exception: return {}


if __name__ == "__main__":
    a = sys.argv[1:]
    B = Board()
    if a and a[0] == "pads":
        P = load_placement(a[1]); out = {}
        refs = set(P) | B.fixed if "--partial" in a else set(B.parts)
        for r in sorted(refs):
            d = {}
            for p in B.pads(r, P.get(r)): d.setdefault(p[0], []).append([round(p[2], 5), round(p[3], 5)])
            out[r] = d
        json.dump(out, sys.stdout)
    elif a and a[0] == "info":
        P = B.parts[a[1]]; print(json.dumps({k: v for k, v in P.items() if k != "pads"})); [print(p) for p in P["pads"]]
    else: print(__doc__)
