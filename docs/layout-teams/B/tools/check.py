"""check.py <fragment or placement json ...> [--png=out.png] [--rings=auto] [--group=<g>] [--json=out.json] [--quiet]
Checks a placement made of one or more fragments / placements (later files win on a shared ref). Parts not in any
file are absent, except the fixed parts, which are always present at the template. Meta files beside fragments
(<name>.meta.json) give rings, reserved boxes and claims; fragments/claims.json next to the first file adds claims.
--rings=auto adds a 0.8 mm ring round every present chip with 12 pads or more that has none.
--group limits the per-part report to one group's refs (the obstacles stay).

Reports:
  overlap         courtyards of two parts on one side overlapping by more than 0.05 mm both ways
                  (touching, 0..0.05 mm, is counted separately: the hand board has many)
  keep-out, edge  no-footprint keep-outs on the part's side; outline set back 0.5 mm
  far-side pad    a part's through-hole/back pad under another part's body, or a body on another part's far-side pad
  ring, reserved  courtyard inside a ring (meta) or a reserved box
  region / box    movable part outside its group's region (0.4 mm setback) without a claim; more than 2 mm outside its B1 box
  pin distance    first hot-loop capacitor: supply and return pad within 1.5 mm (pad edge to pad edge) of the switch's
                  supply and return pads; serves capacitors: up to 1 uF 2 mm, up to 10 uF 4 mm, larger 10 mm
  escape          every signal pad of a chip with 12 pads or more: a 0.2 mm track with 0.15 mm clearance must run 1.0 mm
                  straight out (away from the chip) without touching a foreign pad or courtyard on that side
                  (parts with a pad on the same net do not count)
  bottom count    movable parts on B
  hpwl            signal half-perimeter (hpwl.py's measure) of the whole board, absent parts at the template
Exit code 1 when an overlap, keep-out, edge, far-side, ring, reserved, region or pin-distance fault is found."""
import sys, os, json, re, math, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blib
from blib import Board, Layout, inter, overlap_xy, box_gap, grow, load_placement

def cap_uF(v):
    t = (v or "").split()[0] if v else ""
    m = re.fullmatch(r"([\d.]+)([pnuµm]?)(\d*)F?", t)
    if not m: return None
    a, u, b = m.groups(); x = float(a + ("." + b if b else "")); return x * {"p": 1e-6, "n": 1e-3, "u": 1, "µ": 1, "m": 1e3, "": 1e6}[u]

def load_all(files):
    B = Board(); P = {}; metas = []; claims = {}
    for f in files:
        for r, v in load_placement(f).items():
            if r in B.parts and r not in B.fixed: P[r] = v
        m = f[:-5] + ".meta.json"
        if os.path.exists(m): metas.append(blib.load_meta(m))
    if files:
        cf = os.path.join(os.path.dirname(os.path.abspath(files[0])), "claims.json")
        if os.path.exists(cf):
            for c in json.load(open(cf)): claims.setdefault(c["ref"], tuple(c["box"]))
    L = Layout(B, P)
    for m in metas:
        for c in m.get("claims", []): claims.setdefault(c["ref"], tuple(c["box"]))
        for z in m.get("reserved", []): L.reserved.append(dict(name=z["name"], box=tuple(z["box"]), sides=z.get("sides", "F"), **({"except": set(z["except"])} if z.get("except") else {})))
        for g in m.get("rings", []):
            if g["chip"] in L.P: L.add_ring(g["chip"], g.get("mm", 0.8), g.get("allow", ()), g.get("serves_mm", 0.3))
    L.claims = claims
    return B, L, P

def escape_faults(B, L, chip):
    c, s, pads = L.geom(chip); out = []
    x, y, q, sd, fl = L.P[chip]
    rows = blib.chip_rows(B, chip, (x, y, q * 90, sd), signal_only=False)
    dirs = {"W": (-1, 0), "E": (1, 0), "N": (0, -1), "S": (0, 1)}
    others = [(r, L.geom(r)) for r in L.P if r != chip and L.geom(r)[1] == s]
    opads = [(r, p) for r, g in others for p in g[2] if s in p[5]]
    for k, rb, nums, sig in rows:
        dx, dy = dirs[k]
        for p in pads:
            if p[0] not in nums or not B.is_signal_net(p[1]): continue
            b = p[4]; hw = 0.25            # 0.2 mm track + 0.15 mm clearance each side: 0.5 mm corridor
            if k in "WE":
                cy = (b[1] + b[3]) / 2; x0 = b[0] if k == "W" else b[2]
                corr = (min(x0, x0 + dx * 1.0), cy - hw, max(x0, x0 + dx * 1.0), cy + hw)
            else:
                cx = (b[0] + b[2]) / 2; y0 = b[1] if k == "N" else b[3]
                corr = (cx - hw, min(y0, y0 + dy * 1.0), cx + hw, max(y0, y0 + dy * 1.0))
            corr = (corr[0] + 0.01 * (k == "E"), corr[1] + 0.01 * (k == "S"), corr[2] - 0.01 * (k == "W"), corr[3] - 0.01 * (k == "N"))
            friends = {r for r, g in others if any(pp[1] == p[1] for pp in g[2])}
            hit = [r for r, g in others if r not in friends and inter(corr, g[0])]
            hit += [f"{r}.{pp[0]}" for r, pp in opads if pp[1] != p[1] and r not in friends and inter(corr, pp[4])]
            if hit: out.append((f"{chip}.{p[0]}", p[1], sorted(set(hit))))
    return out

def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]; opt = dict((x[2:].split("=", 1) + [""])[:2] for x in sys.argv[1:] if x.startswith("--"))
    B, L, P = load_all(a)
    if opt.get("rings") == "auto":
        have = {g["chip"] for g in L.rings}
        for r in L.P:
            if B.is_chip(r) and r not in have: L.add_ring(r, 0.8)
    grp = opt.get("group"); mine = sorted(r for r in P if not grp or B.group_of.get(r) == grp)
    R = dict(overlap=[], touch=[], keepout=[], edge=[], farside=[], ring=[], reserved=[], region=[], box=[], pin=[], escape=[], fixed_moved=[])
    rs = sorted(L.P)
    for i, r1 in enumerate(rs):
        c1, s1, _ = L.geom(r1)
        for r2 in rs[i + 1:]:
            if r1 in B.fixed and r2 in B.fixed: continue
            if grp and r1 not in mine and r2 not in mine: continue
            c2, s2, _ = L.geom(r2)
            if s1 != s2: continue
            ox, oy = overlap_xy(c1, c2)
            if ox > 0.05 and oy > 0.05: R["overlap"].append(f"{r1}/{r2} {ox:.2f}x{oy:.2f}")
            elif ox > 0 and oy > 0: R["touch"].append(f"{r1}/{r2}")
    for r in mine:
        c, s, pads = L.geom(r)
        for k in B.keepouts:
            if (s + ".Cu") in k["layers"] and inter(c, k["box"]): R["keepout"].append(f"{r} in {k['name'] or 'unnamed'}")
        ob = B.obox
        if c[0] < ob[0] + blib.EDGE - 1e-6 or c[1] < ob[1] + blib.EDGE - 1e-6 or c[2] > ob[2] - blib.EDGE + 1e-6 or c[3] > ob[3] - blib.EDGE + 1e-6 or any(inter(c, o, blib.EDGE - 1e-6) for o in B.outside):
            R["edge"].append(r)
        for f in L.faults(r, region=False, rings=False, reserved=False):
            if "far-side" in f: R["farside"].append(f"{r}: {f}")
        for z in L.reserved:
            if s in z["sides"] and r not in z.get("except", ()) and inter(c, z["box"]): R["reserved"].append(f"{r} in {z['name']}")
        for chip, rb in L.ring_boxes(r, s):
            if inter(c, rb): R["ring"].append(f"{r} in ring of {chip}")
        Ri, cl = L.region_ok_box(r)
        ins = lambda b: c[0] >= b[0] - 1e-6 and c[1] >= b[1] - 1e-6 and c[2] <= b[2] + 1e-6 and c[3] <= b[3] + 1e-6
        if Ri and not ins(Ri) and not (cl and ins(cl)): R["region"].append(f"{r} outside {B.group_of[r]}")
        bx = B.block_of.get(r)
        if bx:
            out = max(bx[0] - c[0], bx[1] - c[1], c[2] - bx[2], c[3] - bx[3])
            if out > 2.0: R["box"].append(f"{r} {out:.1f} mm outside its B1 box")
    # pin distances
    for name, hl in B.C["hot_loops"].items():
        cap = hl["caps"][0]; a1, b1 = hl["switch_pins"]; sw = a1.split(".")[0]
        if cap not in L.P or sw not in L.P or (grp and cap not in mine and sw not in mine): continue
        sp = set(B.pin_pads(sw, a1.split(".")[1])); rp = set(B.pin_pads(sw, b1.split(".")[1]))
        swp = L.geom(sw)[2]; cp = L.geom(cap)[2]
        for lab, nums in (("supply", sp), ("return", rp)):
            tp = [p for p in swp if p[0] in nums]; net = tp[0][1]
            mp = [p for p in cp if p[1] == net]
            d = min(box_gap(m[4], t[4]) for m in mp for t in tp) if mp else 99
            if d > 1.5: R["pin"].append(f"{name}: first capacitor {cap} {lab} pad {d:.2f} mm from {sw} (limit 1.5)")
    for r, spec in B.C.get("serves", {}).items():
        if r not in L.P or (grp and r not in mine) or not r.startswith("C"): continue
        sv = B.served_pads(r)
        if not sv or sv[0] not in L.P: continue
        tp = [p for p in L.geom(sv[0])[2] if p[0] in set(sv[1])]
        if not tp: continue
        mp = [p for p in L.geom(r)[2] if p[1] == tp[0][1]]
        if not mp: continue
        d = min(box_gap(m[4], t[4]) for m in mp for t in tp); u = cap_uF(B.parts[r]["value"]); lim = 2.0 if u is not None and u <= 1 else 4.0 if u is not None and u <= 10 else 10.0
        if d > lim: R["pin"].append(f"{r} ({B.parts[r]['value']}) {d:.2f} mm from {spec} (limit {lim})")
    for chip in sorted(r for r in L.P if B.is_chip(r) and (not grp or B.group_of.get(r) == grp or r in B.fixed and False)):
        R["escape"] += [f"{p} {n.split('/')[-1]} blocked by {h}" for p, n, h in escape_faults(B, L, chip)]
    bottom = [r for r in P if L.geom(r)[1] == "B" and r in B.movable]
    full = {r: v for r, v in P.items()}
    hp = blib.hpwl(B, full)
    hard = sum(len(R[k]) for k in ("overlap", "keepout", "edge", "farside", "ring", "reserved", "region", "pin"))
    print(f"check: {len(P)} movable parts present ({len(mine)} reported), {len(L.P) - len(P)} fixed")
    for k in ("overlap", "keepout", "edge", "farside", "ring", "reserved", "region", "box", "pin", "escape"):
        v = R[k]; print(f"  {k:9s} {len(v):3d}" + ("" if not v or "quiet" in opt else "  " + "; ".join(v[:40]) + (" ..." if len(v) > 40 else "")))
    print(f"  touching  {len(R['touch']):3d}  (courtyards closer than 0, overlap 0.05 mm or less)")
    print(f"  bottom    {len(bottom):3d}  {sorted(bottom)}")
    print(f"  hpwl      {hp:.0f} mm (whole board, absent movable parts at the template; hand 2064)")
    print(f"  hard faults {hard}")
    if opt.get("json"): json.dump(dict(R, bottom=sorted(bottom), hpwl=round(hp, 1), hard=hard), open(opt["json"], "w"), indent=1)
    if opt.get("png"): draw(B, L, P, opt["png"], R)
    sys.exit(1 if hard else 0)

def netcol(n, B):
    if not n: return (200, 200, 200)
    if n == "GND" or n.endswith("/GND"): return (110, 110, 110)
    if n in B.power: return (220, 60, 60)
    h = hashlib.md5(n.encode()).digest(); return (60 + h[0] % 150, 60 + h[1] % 150, 90 + h[2] % 150)

def draw(B, L, P, out, R):
    from PIL import Image, ImageDraw, ImageFont
    bx = B.obox; S = 16; W = int((bx[2] - bx[0]) * S) + 40; H = int((bx[3] - bx[1]) * S) + 40
    im = Image.new("RGB", (2 * W, H), "white"); dr = ImageDraw.Draw(im)
    try: fo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
    except Exception: fo = ImageFont.load_default()
    def px(x, y, s): return (20 + (x - bx[0]) * S + (W if s == "B" else 0), 20 + (y - bx[1]) * S)
    def rect(b, s, **k): dr.rectangle([px(b[0], b[1], s), px(b[2], b[3], s)], **k)
    for s in "FB":
        dr.polygon([px(x, y, s) for x, y in B.outline], outline="black", width=2)
        dr.text(px(bx[0], bx[1] - 1.1, s), "TOP (F)" if s == "F" else "BOTTOM (B), seen from the top", fill="black", font=fo)
        for x in range(80, 122, 5): dr.text(px(x, bx[3] + 0.2, s), str(x), fill="gray", font=fo)
        for y in range(65, 138, 5): dr.text(px(bx[0] - 1.2, y, s), str(y), fill="gray", font=fo)
        for k in B.keepouts:
            if (s + ".Cu") in k["layers"]: rect(k["box"], s, fill=(232, 232, 232))
        for g, b in B.regions.items(): rect(b, s, outline=(180, 180, 255), width=1)
    for name, b in B.BX["blocks"].items():
        s = "B" if name.endswith("B.Cu") else "F"; rect(b, s, outline=(170, 220, 170), width=1)
    for z in L.reserved:
        for s in z["sides"]:
            rect(z["box"], s, outline=(0, 120, 255), width=2)
            b = z["box"]; xx = b[0]
            while xx < b[2]: dr.line([px(xx, b[1], s), px(min(b[2], xx + (b[3] - b[1])), min(b[3], b[1] + (b[2] - xx)), s)], fill=(150, 190, 255)); xx += 0.6
    for g in L.rings:
        if g["chip"] not in L.P: continue
        s = L.geom(g["chip"])[1]
        for k, rb, nums in g["rows"]: rect(grow(rb, g["mm"]), s, outline=(255, 150, 0), width=1)
    bad = set()
    for k in ("overlap", "keepout", "edge", "farside", "ring", "reserved", "region"):
        for t in R[k]: bad |= set(re.findall(r"[A-Z]+\d+", t.split(":")[0].split(" ")[0]))
    for r in L.P:
        c, s, pads = L.geom(r)
        for p in pads:
            for ps in p[5]: rect(p[4], ps, fill=netcol(p[1], B))
    for r in L.P:
        c, s, pads = L.geom(r)
        col = (90, 90, 90) if r in B.fixed else ((230, 0, 0) if r in bad else (0, 0, 0))
        rect(c, s, outline=col, width=2 if r in bad else 1)
        if (c[2] - c[0]) * (c[3] - c[1]) > 1.2 or r in bad: dr.text((px(c[0], c[1], s)[0] + 1, px(c[0], c[1], s)[1]), r, fill=col, font=fo)
    for t in R["escape"]:
        ref, num = t.split(" ")[0].split(".")
        for p in L.geom(ref)[2]:
            if p[0] == num: rect(grow(p[4], 0.15), L.geom(ref)[1], outline=(255, 0, 255), width=2)
    im.save(out)
    print(f"  picture {out}")

if __name__ == "__main__":
    main()
