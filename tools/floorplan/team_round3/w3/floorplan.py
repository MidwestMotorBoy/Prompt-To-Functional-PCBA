"""floorplan.py: the floorplan intent file and its demand score (stage 6).
  extract <board dump.json> <intent.json> [fixed ref prefixes, default J,H,TP,SW]
        reads a placed board (spikes/03-corridor-capacity/dump_board.py) and writes the floorplan it implies:
        board box, fixed parts, one region per block and side (the box round its parts), no lanes.
  score <intent.json> <board dump.json>
        demand of the detailed placement (signal half-perimeter, worst cut line) and of the floorplan alone
        (every part moved to its region's centre), plus how well the placement keeps to the intent.
  Add the code's netlist.json as a last argument to use block sections as the regions, not whole sheets.
Intent file:
  {"box": [x0, y0, x1, y1], "power_nets": [...],
   "fixed": {"J401": [x, y, "F.Cu"]},
   "blocks": {"USB Port 1": [{"side": "F.Cu", "box": [x0, y0, x1, y1], "parts": 61}]},
   "lanes": [{"name": "...", "box": [x0, y0, x1, y1], "layers": ["In2.Cu"], "between": ["A", "B"], "nets": 12}]}
A lane is a declared corridor: parts and power copper must stay out of it on its layers."""
import json, sys
from collections import defaultdict

SECTIONS = None      # optional {ref: "block / section"} from the code netlist, set with a third argument

def load(dump):
    d = json.load(open(dump))
    if SECTIONS:
        for f in d["fps"]: f["sheet"] = SECTIONS.get(f["ref"], f["sheet"])
    side = {f["ref"]: f["side"] for f in d["fps"]}; blk = {f["ref"]: f["sheet"].strip("/") or "top" for f in d["fps"]}
    pos = {f["ref"]: (f["x"], f["y"]) for f in d["fps"]}; pads = defaultdict(list)
    for p in d["pads"]:
        if p["net"]: pads[p["net"]].append((p["x"], p["y"], p["ref"]))
    return d, pos, side, blk, pads

def power_nets(pads, intent=None):
    if intent and intent.get("power_nets"): return set(intent["power_nets"])
    return {n for n, ps in pads.items() if len(ps) >= 12}

def demand(pads, power, where=lambda x, y, ref: (x, y)):
    hp = 0.0; spans = []
    for n, ps in pads.items():
        if n in power or len(ps) < 2: continue
        q = [where(*p) for p in ps]; xs = [a for a, _ in q]; ys = [b for _, b in q]
        hp += max(xs) - min(xs) + max(ys) - min(ys); spans.append((min(xs), max(xs), min(ys), max(ys)))
    return hp, spans

def worst_cut(spans, box, step=1.0):
    best = (0, None)
    for axis, lo, hi in ((0, box[0], box[2]), (1, box[1], box[3])):
        k = lo + step
        while k < hi:
            n = sum(1 for s in spans if s[2 * axis] < k < s[2 * axis + 1])
            if n > best[0]: best = (n, ("x" if axis == 0 else "y", round(k, 1)))
            k += step
    return best

def extract(dump, out, prefixes="J,H,TP,SW"):
    d, pos, side, blk, pads = load(dump); pre = tuple(prefixes.split(","))
    it = dict(box=d["box"], power_nets=sorted(power_nets(pads)), fixed={}, blocks={}, lanes=[])
    grp = defaultdict(list)
    for r, (x, y) in pos.items():
        if r.rstrip("0123456789").upper() in pre: it["fixed"][r] = [x, y, side[r]]
        grp[(blk[r], side[r])].append((x, y))
    for (b, s), pts in sorted(grp.items()):
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        it["blocks"].setdefault(b, []).append(dict(side=s, box=[round(min(xs) - 1, 2), round(min(ys) - 1, 2), round(max(xs) + 1, 2), round(max(ys) + 1, 2)], parts=len(pts)))
    json.dump(it, open(out, "w"), indent=1); return it

def score(intent, dump):
    it = json.load(open(intent)); d, pos, side, blk, pads = load(dump); power = power_nets(pads, it)
    reg = {(b, r["side"]): r["box"] for b, rs in it["blocks"].items() for r in rs}
    def centre(x, y, ref):
        if ref in it["fixed"]: return it["fixed"][ref][0], it["fixed"][ref][1]
        b = reg.get((blk[ref], side[ref])) or next((v for (bb, _), v in reg.items() if bb == blk[ref]), None)
        return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) if b else (x, y)
    hp, spans = demand(pads, power); hpf, spansf = demand(pads, power, centre)
    out = dict(signal_nets=len(spans), half_perimeter_mm=round(hp), worst_cut=worst_cut(spans, it["box"]),
               floorplan_only_half_perimeter_mm=round(hpf), floorplan_only_worst_cut=worst_cut(spansf, it["box"]))
    # nets shared between blocks: what the lanes must carry
    share = defaultdict(int)
    for n, ps in pads.items():
        if n in power: continue
        bs = sorted({blk[p[2]] for p in ps})
        for i, a in enumerate(bs):
            for b in bs[i + 1:]: share[(a, b)] += 1
    out["nets_between_blocks"] = {f"{a} | {b}": n for (a, b), n in sorted(share.items(), key=lambda kv: -kv[1])}
    # how well the placement keeps to the intent
    outside = [r for r in pos if r not in it["fixed"] and (blk[r], side[r]) in reg and not (reg[(blk[r], side[r])][0] <= pos[r][0] <= reg[(blk[r], side[r])][2] and reg[(blk[r], side[r])][1] <= pos[r][1] <= reg[(blk[r], side[r])][3])]
    moved = [r for r, (x, y, s) in it["fixed"].items() if r in pos and (abs(pos[r][0] - x) > 0.01 or abs(pos[r][1] - y) > 0.01 or side[r] != s)]
    inlane = [(l["name"], p["ref"]) for l in it["lanes"] for p in d["pads"] if set(p["layers"]) & set(l["layers"]) and l["box"][0] < p["x"] < l["box"][2] and l["box"][1] < p["y"] < l["box"][3]
              and p["net"] not in l.get("net_names", [])]
    ov = 0.0; rs = list(reg.items())
    for i, ((a, sa), A) in enumerate(rs):
        for (b, sb), B in rs[i + 1:]:
            if sa == sb and a != b: ov += max(0, min(A[2], B[2]) - max(A[0], B[0])) * max(0, min(A[3], B[3]) - max(A[1], B[1]))
    out.update(parts_outside_their_region=len(outside), fixed_parts_moved=len(moved), pads_in_lanes=len(set(inlane)), region_overlap_mm2=round(ov))
    return out

if __name__ == "__main__":
    nl = [a for a in sys.argv if a.endswith("netlist.json")]
    if nl:
        sys.argv.remove(nl[0]); c = json.load(open(nl[0]))["comps"]
        SECTIONS = {r: f"{v['block']} / {v.get('section') or 'main'}" for r, v in c.items()}
    if sys.argv[1] == "extract": it = extract(*sys.argv[2:]); print({b: [(r["side"], r["parts"], r["box"]) for r in rs] for b, rs in it["blocks"].items()})
    else: print(json.dumps(score(*sys.argv[2:]), indent=1))
