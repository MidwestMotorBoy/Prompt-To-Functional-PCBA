#!/usr/bin/env python3
"""pad_join_check.py <scorecard outdir>                       (scorecard check mode, run by score_rules.sh step 7)
   pad_join_check.py <board.kicad_pcb, zones filled> <cu_dump.json of that board> <constraints.json>
                     [out.json] [--allow=allow.json] [--all=1] [--tol=0.001]     (single-board mode)

Per-pad power-join check (team A r4_vbus, moved into copper_rules in round 5). dc_score.py treats a part's pads on one
net as one terminal node (a terminal counts as joined when ANY of its pads is on the source's copper, and the source's
own pads are all taken as fed), so a source terminal whose second pad group is a pad-only copper island is not
flagged, nor is a shunt cap on an island. This check looks at every pad on its own.

Copper model (exact polygons, shapely): per net and layer the union of filled zone polygons, track segments (round
caps), via discs and the net's pad shapes, merged at --tol mm (touching = joined; a 0.2 mm gap is a gap). Pieces on
different layers are joined only by a via or a plated hole that lies in both. Pads of one footprint get NO free join.

Which nets and pads: every power net and the return net, as tools/copper/roles.py derives them from constraints.json.
For each net the MAIN piece is the connected copper piece that holds pads of the most distinct terminal parts (ties:
the one holding the source terminal = largest-current series terminal, as dc_score). Then:
  unjoined   every TERMINAL pad (series or shunt pad per roles.py) that is not on the main piece, for terminal parts
             that have 2+ terminal pads on the net, and for whole terminals that are off the main piece
  info       (--all=1, default on) non-terminal pads of parts with 2+ pads on the net that are off the main piece
The allow list is board data: {net_substring: ["REF" | "REF.PAD", ...]} (expected findings, e.g. the charter's allowed
opens). Single-board mode reads it from --allow=<file>; outdir mode from the outdir's rules.json "pad_join"."allow"
(a dict, or a path relative to the repo). Exit code 1 in single-board mode when an unjoined pad is outside it.

Outdir mode: checks cu.kicad_pcb (with cu.json) and, when a full route saved one, routed.kicad_pcb (with routed.json);
writes pad_join.json / pad_join_routed.json and prints
  CHECK {"pad_unjoined": {...not allowed...}, "pad_unjoined_all": {...}, "routed_pad_unjoined": {...}}
which score_rules.sh lifts to the top level of score.json. About 1.5 s per board."""
import sys, os, json


def _stock_dir():
    d = os.environ.get("PLAN_COPPER_DIR")
    if d: return d
    p = os.path.dirname(os.path.abspath(__file__))
    while p != "/":
        if os.path.exists(os.path.join(p, "tools", "copper", "roles.py")): return os.path.join(p, "tools", "copper")
        p = os.path.dirname(p)
    raise SystemExit("pad_join_check: tools/copper/roles.py not found (set PLAN_COPPER_DIR)")


sys.path.insert(0, _stock_dir())
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union
from shapely.strtree import STRtree
from roles import Design, poly
from dc_score import load_copper


def net_pieces(D, Z, S, V, net, layers, tol):
    """Connected copper pieces of one net over all layers. Returns (pieces per layer [(geom)], piece id per (layer, k))."""
    geo = {L: [] for L in layers}
    for z in Z:
        if z["net"] == net and z["layer"] in geo and len(z["pts"]) > 2:
            g = Polygon(z["pts"]).buffer(0)
            if not g.is_empty: geo[z["layer"]].append(g)
    for s in S:
        if s["net"] == net and s["layer"] in geo:
            a, b = s["a"], s["b"]
            g = LineString([a, b]).buffer(s["w"] / 2, 8) if a != b else Point(a).buffer(s["w"] / 2, 8)
            geo[s["layer"]].append(g)
    vias = [v for v in V if v["net"] == net]
    for v in vias:
        ls = layers if (set(v["layers"]) & {"*.Cu"} or len(v["layers"]) == 2 and v["layers"][0] == layers[0] and v["layers"][-1] == layers[-1]) else [L for L in layers if L in v["layers"]]
        v["_layers"] = ls
        for L in ls: geo[L].append(Point(v["x"], v["y"]).buffer(v["size"] / 2, 16))
    pads = [p for p in D.pads if p["net"] == net]
    for p in pads:
        for L, recs in p["shapes"].items():
            if L in geo:
                for r in recs: geo[L].append(poly(r).buffer(0))
    pieces = {}
    for L in layers:
        if not geo[L]: pieces[L] = []; continue
        u = unary_union([g.buffer(tol / 2, 4) for g in geo[L]])
        pieces[L] = list(getattr(u, "geoms", [u]))
    # union-find over (L, k)
    ids = [(L, k) for L in layers for k in range(len(pieces[L]))]; parent = {i: i for i in ids}
    def f(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    def join(a, b):
        ra, rb = f(a), f(b)
        if ra != rb: parent[ra] = rb
    trees = {L: STRtree(pieces[L]) for L in layers if pieces[L]}
    def at(L, pt):
        if L not in trees: return None
        for k in trees[L].query(pt):
            if pieces[L][k].intersects(pt): return (L, int(k))
        return None
    barrels = [(Point(v["x"], v["y"]), v["_layers"]) for v in vias] + [(Point(p["x"], p["y"]), [L for L in layers if L in p["shapes"]]) for p in pads if p.get("drill")]
    for pt, ls in barrels:
        hits = [h for h in (at(L, pt) for L in ls) if h is not None]
        for h in hits[1:]: join(hits[0], h)
    def pad_comps(p):
        out = set()
        for L, recs in p["shapes"].items():
            if L not in trees: continue
            for r in recs:
                c = poly(r).buffer(0).representative_point()
                h = at(L, c)
                if h is not None: out.add(f(h))
        return out
    return pad_comps, pieces, f


def check(pcb, dump, cons, tol=0.001, want_all=True, allow=None):
    D = Design(dump, cons); Z, S, V = load_copper(pcb); layers = D.D["layers"]
    allow = allow or {}
    res = dict(unjoined={}, unjoined_not_allowed={}, whole_open={}, info={}, main={})
    for net in sorted(D.power) + sorted(D.ret):
        T = D.terminals(net)
        if not T: continue
        pad_comps, pieces, f = net_pieces(D, Z, S, V, net, layers, tol)
        tkeys = {p["key"] for g in T for p in g["pads"]}
        comp_of = {p["key"]: pad_comps(p) for p in D.pads if p["net"] == net}
        # main piece: holds pads of the most terminal parts; tie -> holds the source terminal
        ser = sorted([g for g in T if g["kind"] == "series"] or T, key=lambda g: (-g["current_a"], -len(g["pads"]), g["ref"]))
        src = ser[0]["ref"]; score = {}
        for g in T:
            cs = set().union(*[comp_of[p["key"]] for p in g["pads"]]) if g["pads"] else set()
            for c in cs: score.setdefault(c, set()).add(g["ref"])
        if not score: continue
        main = max(score, key=lambda c: (len(score[c]), src in score[c]))
        res["main"][net] = dict(terminal_parts=len(score[main]), of=len(T), source=src)
        un, wo, inf = [], [], []
        for g in T:
            off = [p["key"] for p in g["pads"] if main not in comp_of[p["key"]]]
            if not off: continue
            if len(off) == len(g["pads"]): wo.append(g["ref"])
            if len(g["pads"]) >= 2 or len(off) == len(g["pads"]): un += off
        if want_all:
            for ref, ps in D.by_ref.items():
                on = [p for p in ps if p["net"] == net]
                if len(on) < 2: continue
                inf += [p["key"] for p in on if p["key"] not in tkeys and main not in comp_of[p["key"]]]
        al = [x for k, v in allow.items() if k in net for x in v]
        bad = [k for k in un if k not in al and k.split(".")[0] not in al]
        for name, lst in (("unjoined", un), ("unjoined_not_allowed", bad), ("whole_open", wo), ("info", inf)):
            if lst: res[name][net] = sorted(lst)
    nu = sum(len(v) for v in res["unjoined"].values()); nb = sum(len(v) for v in res["unjoined_not_allowed"].values())
    short = lambda d: "; ".join(f"{n.split('/')[-1] if n.count('/') < 2 else n.split('/')[-2][-1] + ':' + n.split('/')[-1]} " + ",".join(v) for n, v in d.items())
    res["summary"] = f"{nu} unjoined terminal pads ({nb} not allowed): {short(res['unjoined_not_allowed']) or '-'}; info (non-terminal) {sum(len(v) for v in res['info'].values())}"
    return res


def outdir_mode(out):
    """Scorecard check: cu board (and routed board if present) of one outdir; allow list from rules.json."""
    repo = os.path.dirname(os.path.dirname(_stock_dir()))
    rf = os.path.join(out, "rules.json"); ru = json.load(open(rf)) if os.path.exists(rf) else {}
    cons = os.path.join(repo, ru.get("board", {}).get("constraints", ""))
    al = ru.get("pad_join", {}).get("allow", {})
    if isinstance(al, str): al = json.load(open(os.path.join(repo, al)))
    al = {k: v for k, v in al.items() if not k.startswith("_")}
    res = {}
    for pcb, dump, tag in (("cu.kicad_pcb", "cu.json", ""), ("routed.kicad_pcb", "routed.json", "_routed")):
        if not (os.path.exists(os.path.join(out, pcb)) and os.path.exists(os.path.join(out, dump))): continue
        r = check(os.path.join(out, pcb), os.path.join(out, dump), cons, allow=al)
        json.dump(r, open(os.path.join(out, f"pad_join{tag}.json"), "w"), indent=1)
        print("SUMMARY" + tag, r["summary"])
        if tag: res["routed_pad_unjoined"] = r["unjoined_not_allowed"]
        else: res["pad_unjoined"] = r["unjoined_not_allowed"]; res["pad_unjoined_all"] = r["unjoined"]
    print("CHECK " + json.dumps(res))


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]; opt = dict(x[2:].split("=", 1) for x in sys.argv[1:] if x.startswith("--"))
    if len(a) == 1 and os.path.isdir(a[0]): outdir_mode(a[0]); return
    allow = json.load(open(opt["allow"])) if opt.get("allow") else {}
    allow = {k: v for k, v in allow.items() if not k.startswith("_")}
    r = check(a[0], a[1], a[2], tol=float(opt.get("tol", 0.001)), want_all=opt.get("all", "1") != "0", allow=allow)
    if len(a) > 3: json.dump(r, open(a[3], "w"), indent=1)
    print("SUMMARY", r["summary"])
    sys.exit(1 if r["unjoined_not_allowed"] else 0)


if __name__ == "__main__":
    main()
