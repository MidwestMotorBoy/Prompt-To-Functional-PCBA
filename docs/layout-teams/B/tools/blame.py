"""blame.py <screen outdir> [--json=out.json] [--near=0.35]
Who to blame after a screen (whole or partial): reads <outdir>/ghost.log (blocked edges), dc.json (open power pins),
drc.json (DRC errors), cu.json and cu.kicad_pcb (pads and the planned copper).
Prints:
  - blocked edges by ref, by chip (U parts at either end) and by group (port1, port2, pack, fixed)
  - for every blocked pad: what stands within --near mm of it on its layer: power pours, tracks and vias of other nets
    (by net), pads of other nets of other parts (by ref.pad; the part's own neighbouring pads are not listed)
  - open power pins by net and ref, with the solver's reason
  - DRC errors by ref and type
Writes the same as json to <outdir>/blame.json (or --json)."""
import sys, os, re, json
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blib import Board
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools", "copper"))

PAD = re.compile(r"Pad (\S*) \[([^\]]*)\] of (\S+) on (\S+)")

def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]; opt = dict((x[2:].split("=", 1) + [""])[:2] for x in sys.argv[1:] if x.startswith("--"))
    if not a: print(__doc__); sys.exit(2)
    D = a[0]; near = float(opt.get("near", 0.35)); B = Board()
    grp = lambda r: B.group_of.get(r, "fixed" if r in B.parts else "?")
    out = dict(blocked=[], by_ref={}, by_chip={}, by_group={}, open=[], drc=[])
    # blocked edges
    edges = []
    for l in open(os.path.join(D, "ghost.log")):
        if not l.startswith("GHOSTFAIL "): continue
        net = l[10:].split(" Pad ", 1)[0].strip()
        ends = PAD.findall(l)
        tgt = l.split("->", 1)[1].strip() if "->" in l else ""
        edges.append(dict(net=net, ends=[dict(num=e[0], ref=e[2], layer=e[3]) for e in ends], to=tgt if not tgt.startswith("Pad") else ""))
    m = re.search(r"GHOST noway (\d+) of (\d+)", open(os.path.join(D, "ghost.log")).read())
    by_ref = Counter(); by_chip = Counter(); by_group = Counter()
    for e in edges:
        refs = {x["ref"] for x in e["ends"]}
        for r in refs: by_ref[r] += 1
        for r in refs:
            if r.startswith("U"): by_chip[r] += 1
        for g in {grp(r) for r in refs}: by_group[g] += 1
    # what stands near each blocked pad
    cu = json.load(open(os.path.join(D, "cu.json")))
    from shapely.geometry import Polygon, Point, LineString
    from shapely.ops import unary_union
    from shapely.strtree import STRtree
    pads = {}
    for p in cu["pads"]:
        for L, recs in p["shapes"].items():
            pads.setdefault((p["ref"], p["num"], L), []).append(unary_union([Polygon(r["ring"], r.get("holes") or []) for r in recs]))
    objs = []          # (geom, layer, label, net)
    for p in cu["pads"]:
        for L, recs in p["shapes"].items():
            g = unary_union([Polygon(r["ring"], r.get("holes") or []) for r in recs]); objs.append((g, L, f"pad {p['ref']}.{p['num']}", p["net"]))
    try:
        from dc_score import load_copper
        Z, S, V = load_copper(os.path.join(D, "cu.kicad_pcb"))
        for z in Z:
            if len(z["pts"]) >= 3: objs.append((Polygon(z["pts"]).buffer(0), z["layer"], f"pour {z['net'] or '(no net)'}", z["net"]))
        for s in S: objs.append((LineString([s["a"], s["b"]]).buffer(s["w"] / 2), s["layer"], f"track {s['net']}", s["net"]))
        for v in V:
            for L in cu["layers"]: objs.append((Point(v["x"], v["y"]).buffer(v["size"] / 2), L, f"via {v['net']}", v["net"]))
    except Exception as ex:
        print(f"(copper not read: {ex!r}; only pads are listed)")
    bylayer = defaultdict(list)
    for o in objs: bylayer[o[1]].append(o)
    trees = {L: STRtree([o[0] for o in v]) for L, v in bylayer.items()}
    nearby_count = Counter()
    for e in edges:
        info = []
        for x in e["ends"]:
            k = (x["ref"], x["num"], x["layer"]); g = pads.get(k)
            if not g: continue
            g = unary_union(g).buffer(near); L = x["layer"]; hits = set()
            if L in trees:
                for i in trees[L].query(g):
                    o = bylayer[L][i]
                    if o[3] == e["net"] or o[2].startswith(f"pad {x['ref']}."): continue      # own net; the part's own pads are always there
                    if o[0].intersects(g): hits.add(o[2])
            for h in hits: nearby_count[h.split(".")[0] if h.startswith("pad") else h] += 1
            info.append(f"{x['ref']}.{x['num']} ({grp(x['ref'])}): " + (", ".join(sorted(hits)) if hits else "nothing within %.2f mm" % near))
        e["near"] = info
        out["blocked"].append(e)
    out["by_ref"] = dict(by_ref.most_common()); out["by_chip"] = dict(by_chip.most_common()); out["by_group"] = dict(by_group.most_common())
    out["near_counts"] = dict(nearby_count.most_common(30))
    # open power pins
    dc = json.load(open(os.path.join(D, "dc.json"))); nets = dc.get("nets", dc)
    for n, v in nets.items():
        if not isinstance(v, dict) or not v.get("open"): continue
        for t in v.get("terminals", []):
            if t.get("open"): out["open"].append(dict(net=n, ref=t["ref"], group=grp(t["ref"]), why=t.get("why", "")))
        for r in v["open"]:
            if not any(o["ref"] == r and o["net"] == n for o in out["open"]): out["open"].append(dict(net=n, ref=r, group=grp(r), why=""))
    # DRC errors
    drc = json.load(open(os.path.join(D, "drc.json")))
    for v in drc["violations"]:
        if v["severity"] != "error": continue
        refs = sorted({r for it in v["items"] for r in re.findall(r" of (\S+)", it["description"])})
        out["drc"].append(dict(type=v["type"], refs=refs, items=[it["description"] for it in v["items"]], at=v["items"][0].get("pos")))
    # print
    print(f"blocked edges: {m.group(1) if m else '?'} of {m.group(2) if m else '?'}" + (" (partial board)" if os.path.exists(os.path.join(D, "constraints_part.json")) else ""))
    print("  by group: " + ", ".join(f"{k} {v}" for k, v in out["by_group"].items()))
    print("  by chip:  " + ", ".join(f"{k} {v}" for k, v in out["by_chip"].items()))
    print("  by ref:   " + ", ".join(f"{k} {v}" for k, v in list(out["by_ref"].items())[:40]))
    print("  what stands next to blocked pads most often: " + ", ".join(f"{k} {v}" for k, v in list(out["near_counts"].items())[:15]))
    for e in out["blocked"]:
        print(f"  {e['net']}: " + " | ".join(e["near"]) + (f"  -> {e['to']}" if e["to"] else ""))
    print(f"open power pins: {len(out['open'])}")
    for o in out["open"]: print(f"  {o['net']} at {o['ref']} ({o['group']}) {o['why']}")
    print(f"DRC errors: {len(out['drc'])}")
    c = Counter((d["type"], r) for d in out["drc"] for r in (d["refs"] or ["(no part)"]))
    for (t, r), k in c.most_common(40): print(f"  {t} {r} ({grp(r)}): {k}")
    json.dump(out, open(opt.get("json") or os.path.join(D, "blame.json"), "w"), indent=1)

if __name__ == "__main__":
    main()
