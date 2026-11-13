"""block_floorplan.py <board_dump.json> <netlist.json> <constraints.json> <out dir> [--seeds=3] [--moves=200000] [--first=1] [--review]
--review: no annealing; gather hand.json and every floorplan_<seed>.json in <out dir> into review.json for the review page.
Block floorplan from the power flow, before any part is placed: one rectangle per (section, side) of the circuit
code, sized from its parts, laid out on the board so that every power path is short and in order. The person
reviews these as pictures (coloured blocks and power-flow arrows) and answers in words; the section placer then
fills each block inside its rectangle.

Why: the placer packed sections by signal wiring and hot loops only, so nothing above the part level knew where
power had to flow (Monolith seed 9: the Port 2 PD switch 69 mm from its USB-C connector). Hand-placing the power
parts instead was too much work for the person (Logan, 2026-11-12): it means thinking through most of the board.

Model
  block     the parts of one section on one side; area = summed courtyards x FILL; aspect ratio is a variable
  fixed     connectors, holes, test points (prefixes J, H, TP, SW) stay where the board has them, as points
  power     every power net (constraints.json, current_a) ties the blocks (and fixed parts) holding its series
            terminals (tools/copper/roles.py) to the one holding its source, weight = current in amps
  signal    every other net with pads in two or more blocks: half-perimeter of the block centres, SIGNAL_W per mm
            (CONN_W if it reaches a connector pin); SAME_W per mm keeps a section's two sides' blocks over each other
  cost      sum of power weight x distance between block edges (mm) + signal + OVERLAP_W x overlap area (same side)
            + OVERLAP_W x area outside the board or in a no-footprint keep-out
  loss      a planning estimate for each layout: each power tie as a 2 oz outer-layer path as wide as its current
            needs (roles.width_mm), as long as the gap between the two blocks, I^2 R summed. For comparing layouts.
Writes per seed: floorplan_<seed>.json (block rectangles) and floorplan_<seed>.png; plus hand.png and hand.json,
the same picture and numbers for the blocks as the dump board has them (the reference)."""
import sys, os, json, math, random, colorsys, zlib
from collections import defaultdict
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "copper"))
from power_chains import design
from roles import width_mm

FILL = 1.4          # block area over summed courtyards (1.7 left no room on Monolith's top side: 2840 of 3180 mm2)
SIGNAL_W = 0.15     # cost per mm of signal half-perimeter between block centres (power dominates, as Logan asked)
CONN_W = 1.0        # the same for a net that reaches a connector pin: port protection and the like sit at their connector
PREFER_W = 3.0      # per mm2 of a block on the wrong half of the board (--prefer=SHEET:left|right,...): a soft rule
SAME_W = 3.0        # per mm between the two sides' blocks of one section (a power stage's bottom parts sit under its top ones)
OVERLAP_W = 40.0
FIXED = ("J", "H", "TP", "SW")
RHO_2OZ = 0.245e-3  # ohm per square, 70 um copper

def short(name):
    s = name.split(" / ")[-1]; s = s.split(":")[0].split("(")[0].strip()
    return s if len(s) <= 22 else s[:21] + "."

def build(dumpf, netf, consf):
    D = json.load(open(dumpf)); N = json.load(open(netf))["comps"]; d, _ = design(dumpf, consf)
    fp = {f["ref"]: f for f in D["fps"]}; key = {}
    for r, f in fp.items():
        if r.rstrip("0123456789") in FIXED: continue
        c = N.get(r, {}); key[r] = (f"{c.get('block', f['sheet'])} / {c.get('section') or 'main'}", f["side"])
    blocks = defaultdict(list)
    for r, k in key.items(): blocks[k].append(r)
    B = sorted(blocks); bi = {k: i for i, k in enumerate(B)}
    area = np.array([FILL * sum((fp[r]["court"][2] - fp[r]["court"][0]) * (fp[r]["court"][3] - fp[r]["court"][1]) if "court" in fp[r] else 1.0 for r in blocks[k]) for k in B])
    # power ties: (block or fixed point) pairs with a current
    ties = []
    for net in d.power:
        I = d.current(net); S = [g for g in d.terminals(net) if g["kind"] == "series"]
        if len(S) < 2: continue
        S.sort(key=lambda g: (-g["current_a"], not g["ref"].startswith("J"), g["ref"]))
        def node(r): return ("b", bi[key[r]]) if r in key else ("f", (fp[r]["x"], fp[r]["y"]))
        src = node(S[0]["ref"]); seen = set()
        for g in S[1:]:
            n = node(g["ref"]); w = min(I, g["current_a"])
            if n == src or (n, src) in seen: continue
            seen.add((n, src)); ties.append((src, n, w, net))
    # signal nets between blocks
    sig = defaultdict(set); fix = defaultdict(set)
    for p in D["pads"]:
        if not p["net"] or p["net"] in d.power: continue
        if p["ref"] in key: sig[p["net"]].add(bi[key[p["ref"]]])
        elif p["ref"].rstrip("0123456789") in ("J",): fix[p["net"]].add((round(p["x"], 1), round(p["y"], 1)))     # connector pins pull their blocks
    sig = [(sorted(s), sorted(fix[n]), CONN_W if fix[n] else SIGNAL_W) for n, s in sig.items() if len(s) + len(fix[n]) >= 2]
    same = [(bi[k], bi[(k[0], "B.Cu")]) for k in B if k[1] == "F.Cu" and (k[0], "B.Cu") in bi]
    sig += [([i, j], [], SAME_W) for i, j in same]
    return D, d, B, blocks, area, ties, sig, key

def rects(state, area):
    out = []
    for (x, y, a), A in zip(state, area):
        w = math.sqrt(A * a); h = A / w; out.append((x - w / 2, y - h / 2, x + w / 2, y + h / 2))
    return out

def gap(r, s):
    dx = max(s[0] - r[2], r[0] - s[2], 0); dy = max(s[1] - r[3], r[1] - s[3], 0); return dx + dy

def man(p, q):
    return abs(p[0] - q[0]) + abs(p[1] - q[1])

def ptgap(r, p):
    return max(r[0] - p[0], 0, p[0] - r[2]) + max(r[1] - p[1], 0, p[1] - r[3])

def ov(r, s):
    return max(0, min(r[2], s[2]) - max(r[0], s[0])) * max(0, min(r[3], s[3]) - max(r[1], s[1]))

class Model:
    def __init__(self, D, d, B, area, ties, sig):
        self.D, self.d, self.B, self.area, self.ties, self.sig = D, d, B, area, ties, sig
        self.box = D["box"]; self.side = [k[1] for k in B]
        self.ko = [(k["box"], k["layers"]) for k in D.get("keepouts", []) if k.get("no_footprints")]
        self.fixedbox = [(f["court"], f["side"]) for f in D["fps"] if f["ref"].rstrip("0123456789") in FIXED and "court" in f]
        self.docked = {}; self.prefer = {}

    def dock(self, N):
        """A block whose section holds a fixed connector (the USB-C connector and its port protection) is not free: it
        sits against the connector, on the board side of it, as wide as the connector (Logan, 2026-11-12: the USB
        connectors are fixed, so their section's box must not float)."""
        x0, y0, x1, y1 = self.box
        for f in self.D["fps"]:
            if f["ref"].rstrip("0123456789") != "J" or "court" not in f: continue
            c = N.get(f["ref"], {}); k = (f"{c.get('block', f.get('sheet'))} / {c.get('section') or 'main'}", f["side"])
            if k not in self.B: continue
            i = self.B.index(k); b = f["court"]; A = self.area[i]; cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            if min(cy - y0, y1 - cy) <= min(cx - x0, x1 - cx):        # on the top or bottom edge: grow inward in y
                w = min(b[2], x1) - max(b[0], x0); h = A / w; ya = b[3] if cy - y0 < y1 - cy else b[1] - h
                self.docked[i] = (max(b[0], x0), ya, max(b[0], x0) + w, ya + h)
            else:
                h = min(b[3], y1) - max(b[1], y0); w = A / h; xa = b[2] if cx - x0 < x1 - cx else b[0] - w
                self.docked[i] = (xa, max(b[1], y0), xa + w, max(b[1], y0) + h)

    def place(self, st):
        R = rects(st, self.area)
        for i, r in self.docked.items(): R[i] = r
        return R

    def terms(self, R):
        pw = 0.0; loss = 0.0
        for a, b, w, net in self.ties:
            ra = R[a[1]] if a[0] == "b" else None; rb = R[b[1]] if b[0] == "b" else None
            # centre to centre: the parts that carry the current can sit anywhere in their box, and an edge-to-edge gap hid
            # 40 mm of Port 2 PPHV inside tall boxes (round 2, option D)
            cen = lambda r: ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)
            if ra and rb: L = man(cen(ra), cen(rb))
            elif ra: L = man(cen(ra), b[1])
            elif rb: L = man(cen(rb), a[1])
            else: L = abs(a[1][0] - b[1][0]) + abs(a[1][1] - b[1][1])
            pw += w * L; loss += w * w * RHO_2OZ * L / max(width_mm(w), 0.3)
        c = [((r[0] + r[2]) / 2, (r[1] + r[3]) / 2) for r in R]
        sg = 0.0
        for s, f, w in self.sig:
            xs = [c[i][0] for i in s] + [p[0] for p in f]; ys = [c[i][1] for i in s] + [p[1] for p in f]; sg += w * (max(xs) - min(xs) + max(ys) - min(ys))
        o = 0.0; x0, y0, x1, y1 = self.box
        for i, r in enumerate(R):
            for j in range(i + 1, len(R)):
                if self.side[i] == self.side[j]: o += ov(r, R[j])
            inside = max(0, min(r[2], x1) - max(r[0], x0)) * max(0, min(r[3], y1) - max(r[1], y0)); o += (r[2] - r[0]) * (r[3] - r[1]) - inside
            for kb, L in self.ko:
                if self.side[i] in L: o += ov(r, kb)
            for fb, s in self.fixedbox:
                if s == self.side[i]: o += ov(r, fb)
        mid = (x0 + x1) / 2
        for i, r in enumerate(R):
            pf = self.prefer.get(self.B[i][0].split(" / ")[0])
            if pf == "right": o += PREFER_W / OVERLAP_W * max(0, min(r[2], mid) - r[0]) * (r[3] - r[1])
            elif pf == "left": o += PREFER_W / OVERLAP_W * max(0, r[2] - max(r[0], mid)) * (r[3] - r[1])
        return pw, sg, o, loss

    def cost(self, R, ow=OVERLAP_W):
        pw, sg, o, _ = self.terms(R); return pw + sg + ow * o

    def anneal(self, seed, moves, start=None, T0=50.0):
        rnd = random.Random(seed); x0, y0, x1, y1 = self.box; n = len(self.B)
        st = [list(v) for v in start] if start else [[rnd.uniform(x0 + 5, x1 - 5), rnd.uniform(y0 + 5, y1 - 5), rnd.choice([0.5, 0.67, 1, 1.5, 2])] for _ in range(n)]
        free = [i for i in range(n) if i not in self.docked]
        cur = self.cost(self.place(st)); T1 = 0.05
        for s in range(moves):
            t = T0 * (T1 / T0) ** (s / moves); i = rnd.choice(free); old = [list(v) for v in st]; u = rnd.random()
            if u < 0.15: st[i][2] = rnd.choice([0.33, 0.5, 0.67, 1, 1.5, 2, 3])
            elif u < 0.3:
                j = rnd.choice(free)
                if self.side[j] == self.side[i]: st[i][:2], st[j][:2] = st[j][:2], st[i][:2]
            else:
                rad = 0.3 + 15 * t / T0; st[i][0] += rnd.uniform(-rad, rad); st[i][1] += rnd.uniform(-rad, rad)
            ow = OVERLAP_W * min(1.0, 0.05 + 1.2 * s / moves)        # overlap weight rises: blocks pass through each other early on
            if s % 1000 == 0: cur = self.cost(self.place(old), ow)
            new = self.cost(self.place(st), ow)
            if new < cur or rnd.random() < math.exp(-(new - cur) / t): cur = new
            else: st[:] = old
        return st

def color(name):
    h = (zlib.crc32(name.split(" / ")[0].encode()) % 360) / 360; r, g, b = colorsys.hsv_to_rgb(h, 0.45, 0.95); return (int(r * 255), int(g * 255), int(b * 255))

def draw(M, R, out, title):
    S = 9; x0, y0, x1, y1 = M.box; W = int((x1 - x0) * 2 * S + 3 * S * 4); H = int((y1 - y0) * S + 70)
    im = Image.new("RGB", (W, H), (252, 252, 250)); dr = ImageDraw.Draw(im, "RGBA")
    try: font = ImageFont.truetype("DejaVuSans.ttf", 11); big = ImageFont.truetype("DejaVuSans-Bold.ttf", 14)
    except Exception: font = big = ImageFont.load_default()
    dr.text((10, 8), title, fill=(0, 0, 0), font=big)
    for k, side in enumerate(("F.Cu", "B.Cu")):
        ox = 10 + k * ((x1 - x0) * S + 4 * S); oy = 50
        P = lambda x, y: (ox + (x - x0) * S, oy + (y - y0) * S)
        dr.rectangle([P(x0, y0), P(x1, y1)], outline=(0, 0, 0), width=2); dr.text((ox, oy - 16), "top side" if k == 0 else "bottom side (seen from top)", fill=(0, 0, 0), font=font)
        for kb, L in M.ko:
            if side in L: dr.rectangle([P(kb[0], kb[1]), P(kb[2], kb[3])], fill=(200, 200, 200, 160))
        for fb, s in M.fixedbox:
            if s == side: dr.rectangle([P(fb[0], fb[1]), P(fb[2], fb[3])], fill=(120, 120, 120, 200))
        for i, r in enumerate(R):
            if M.side[i] != side: continue
            dr.rectangle([P(r[0], r[1]), P(r[2], r[3])], fill=color(M.B[i][0]) + (200,), outline=(60, 60, 60, 255))
            blk = M.B[i][0].split(" / ")[0].replace("USB Port ", "P"); dr.text(P(r[0] + 0.3, r[1] + 0.2), f"{blk}: {short(M.B[i][0])}", fill=(0, 0, 0), font=font)
        for a, b, w, net in M.ties:
            pa = ((R[a[1]][0] + R[a[1]][2]) / 2, (R[a[1]][1] + R[a[1]][3]) / 2) if a[0] == "b" else a[1]
            pb = ((R[b[1]][0] + R[b[1]][2]) / 2, (R[b[1]][1] + R[b[1]][3]) / 2) if b[0] == "b" else b[1]
            sa = M.side[a[1]] if a[0] == "b" else side; sb = M.side[b[1]] if b[0] == "b" else side
            if side not in (sa, sb): continue
            dr.line([P(*pa), P(*pb)], fill=(200, 30, 30, 200 if sa == sb == side else 90), width=max(1, int(w / 1.5)))
    im.save(out)

def summary(M, R):
    pw, sg, o, loss = M.terms(R); return dict(power_mm_amps=round(pw), signal_cost=round(sg), overlap_mm2=round(float(o), 1), loss_estimate_W=round(float(loss), 2))

def slug(k):
    import re
    return re.sub(r"[^a-z0-9]+", "-", f"{k[0].split(' / ')[0]} {short(k[0])} {'top' if k[1] == 'F.Cu' else 'bot'}".lower()).strip("-")

def review(M, blocks, out):
    """review.json for the floorplan review page: the board, the blocks (id, name, side, parts) and power ties once,
    then each option's rectangles keyed by block id."""
    D = M.D; ids = [slug(k) for k in M.B]; fp = {f["ref"]: f for f in D["fps"]}
    def node(n): return {"block": ids[n[1]]} if n[0] == "b" else {"point": [round(n[1][0], 2), round(n[1][1], 2)], "ref": next((f["ref"] for f in D["fps"] if abs(f["x"] - n[1][0]) < 1e-3 and abs(f["y"] - n[1][1]) < 1e-3), "")}
    board = dict(box=D["box"], keepouts=[dict(box=[round(v, 2) for v in kb], sides=L) for kb, L in M.ko],
                 fixed=[dict(ref=f["ref"], value=f.get("value", ""), side=f["side"], box=[round(v, 2) for v in f["court"]]) for f in D["fps"] if f["ref"].rstrip("0123456789") in FIXED and "court" in f],
                 blocks=[dict(id=ids[i], sheet=k[0].split(" / ")[0], section=k[0].split(" / ", 1)[1], side="top" if k[1] == "F.Cu" else "bottom",
                              area=round(float(M.area[i]), 1), docked=i in M.docked, parts=sorted(blocks[k], key=lambda r: (r.rstrip("0123456789"), int(r[len(r.rstrip("0123456789")):] or 0)))) for i, k in enumerate(M.B)],
                 ties=[dict(a=node(a), b=node(b), amps=round(w, 2), width_mm=round(max(width_mm(w), 0.3), 3), net=net.strip("/")) for a, b, w, net in M.ties], rho_2oz=RHO_2OZ)
    opts = {}
    for f in sorted(os.listdir(out)):
        if f.endswith(".json") and (f == "hand.json" or f.startswith("floorplan_")):
            J = json.load(open(f"{out}/{f}")); name = {k[0] + " | " + k[1]: ids[i] for i, k in enumerate(M.B)}
            opts[f[:-5]] = dict(summary=J["summary"], rects={name[k]: [round(v, 2) for v in r] for k, r in J["blocks"].items()})
    json.dump(dict(board=board, options=opts), open(f"{out}/review.json", "w")); print("review data ->", f"{out}/review.json")

def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]; opt = dict((x[2:].split("=", 1) + [""])[:2] for x in sys.argv[1:] if x.startswith("--"))
    D, d, B, blocks, area, ties, sig, key = build(*a[:3]); out = a[3]; os.makedirs(out, exist_ok=True); M = Model(D, d, B, area, ties, sig)
    M.dock(json.load(open(a[1]))["comps"])
    if opt.get("prefer"): M.prefer = dict(x.rsplit(":", 1) for x in opt["prefer"].split(","))
    if opt.get("pins"):         # the person's moves and pins from the review page (edits/<option>): those blocks stay put
        Ed = json.load(open(opt["pins"])); ids = {slug(k): i for i, k in enumerate(B)}; ref = json.load(open(opt["start"]))["blocks"] if opt.get("start") else {}
        names = {slug(k): f"{k[0]} | {k[1]}" for k in B}
        for b in Ed.get("pins", []):
            r = Ed.get("rects", {}).get(b) or ref.get(names[b])
            if r and b in ids: M.docked[ids[b]] = tuple(r)
        print("held where the person put them:", ", ".join(Ed.get("pins", [])))
    start = None
    if opt.get("start"):        # a previous option to work from (its rectangles), annealed from a lower temperature
        J = json.load(open(opt["start"])); idx = {f"{k[0]} | {k[1]}": i for i, k in enumerate(B)}; start = [None] * len(B)
        for k, r in J["blocks"].items(): start[idx[k]] = [(r[0] + r[2]) / 2, (r[1] + r[3]) / 2, (r[2] - r[0]) / (r[3] - r[1])]
    if "review" in opt: review(M, blocks, out); return
    fp = {f["ref"]: f for f in D["fps"]}
    # reference: the blocks as the dump board has them (box round each section's parts)
    Rh = []
    for k in B:
        cs = [fp[r]["court"] for r in blocks[k] if "court" in fp[r]]; Rh.append((min(c[0] for c in cs), min(c[1] for c in cs), max(c[2] for c in cs), max(c[3] for c in cs)))
    sh = summary(M, Rh); json.dump(dict(summary=sh, blocks={f"{k[0]} | {k[1]}": r for k, r in zip(B, Rh)}), open(f"{out}/hand.json", "w"), indent=1)
    draw(M, Rh, f"{out}/hand.png", f"Hand board (reference): power {sh['power_mm_amps']} mm.A, loss est. {sh['loss_estimate_W']} W"); print("hand", sh)
    s0 = int(opt.get("first", 1))
    for s in range(s0, s0 + int(opt.get("seeds", 3))):
        st = M.anneal(s, int(opt.get("moves", 200000)), start, float(opt.get("t0", 50))); R = M.place(st); sm = summary(M, R)
        json.dump(dict(summary=sm, blocks={f"{k[0]} | {k[1]}": r for k, r in zip(B, R)}), open(f"{out}/floorplan_{s}.json", "w"), indent=1)
        draw(M, R, f"{out}/floorplan_{s}.png", f"Floorplan {s}: power {sm['power_mm_amps']} mm.A, loss est. {sm['loss_estimate_W']} W, overlap {sm['overlap_mm2']} mm2"); print(s, sm, flush=True)

if __name__ == "__main__":
    main()
