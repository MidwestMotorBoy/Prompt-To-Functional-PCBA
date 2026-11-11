"""Compare two netlists on the parts they share: same pins grouped into the same nets, same values and footprints.

usage: compare.py A.json B.json [--refs-from A]   (A, B: netlist.json from build(), or truth.json from KiCad)
Net names are not compared, only which pins are joined, so a renamed local net is not a difference.
"""
import json, sys
def load(p):
    d = json.load(open(p))
    nets = {n: [(x[0], x[1]) for x in nodes] for n, nodes in d["nets"].items()}
    return d["comps"], nets
def partition(nets, refs):
    out = {}
    for n, nodes in nets.items():
        g = frozenset(x for x in nodes if x[0] in refs)
        if g: out[g] = n
    return out
def main(a, b):
    ca, na = load(a); cb, nb = load(b)
    refs = set(ca) & set(cb)
    diffs = []
    for r in sorted(set(ca) - set(cb)): diffs.append(f"part {r} only in A")
    for r in sorted(refs):
        for k in ("value", "footprint", "lib"):
            if ca[r][k] != cb[r][k]: diffs.append(f"{r} {k}: A='{ca[r][k]}' B='{cb[r][k]}'")
        fa, fb = ca[r].get("fields", {}), cb[r].get("fields", {})
        for k in ("LCSC", "MPN"):
            if fa.get(k, "") != fb.get(k, ""): diffs.append(f"{r} field {k}: A='{fa.get(k,'')}' B='{fb.get(k,'')}'")
    pa, pb = partition(na, refs), partition(nb, refs)
    # single-pin groups in B that are KiCad 'unconnected-' nets count as not connected
    pa = {g: n for g, n in pa.items() if not (len(g) == 1 and n.startswith("unconnected-"))}
    pb = {g: n for g, n in pb.items() if not (len(g) == 1 and n.startswith("unconnected-"))}
    pin_a = {x: (g, n) for g, n in pa.items() for x in g}
    pin_b = {x: (g, n) for g, n in pb.items() for x in g}
    seen = set()
    for x in sorted(set(pin_a) | set(pin_b)):
        ga, gb = pin_a.get(x), pin_b.get(x)
        if ga and gb and ga[0] == gb[0]: continue
        key = (ga[1] if ga else None, gb[1] if gb else None)
        if key in seen: continue
        seen.add(key)
        sa = ga[0] if ga else frozenset(); sb = gb[0] if gb else frozenset()
        fmt = lambda s: " ".join(sorted(f"{r}.{p}" for r, p in s)[:12])
        diffs.append(f"net A:'{key[0]}' vs B:'{key[1]}': only in A [{fmt(sa - sb)}] only in B [{fmt(sb - sa)}]")
    print(f"{len(refs)} shared parts, {len(pa)} nets in A, {len(pb)} in B, {len(diffs)} differences")
    for d in diffs[:60]: print("  " + d)
    return len(diffs)
if __name__ == "__main__":
    sys.exit(1 if main(sys.argv[1], sys.argv[2]) else 0)
