"""stitch.py <fragment.json ...> --out=<placement.json> [--allow-overlaps] [--allow-missing]
Merges group fragments into one placement {ref: [x, y, turn, side]}. The group of a fragment is its file name
(port1.json, port2.json, pack.json). Refuses (exit 1, nothing written) when:
  - a ref is missing (any of the 245 movable refs of plan/clusters_movable.json not in any fragment), unless --allow-missing
  - a ref is in two fragments, or in a fragment of the wrong group, or is not a movable ref (fixed or unknown)
  - two courtyards on one side overlap by more than 0.05 mm both ways (fixed parts included), unless --allow-overlaps
    (the hand placement has 34 such overlaps, so its round trip needs the flag)
Lists claims that clash: two claims (fragments/claims.json and the fragments' meta files) for one ref, or claim boxes of
different groups that overlap on the same side.
Also writes <placement>.3.json ({ref: [x, y, turn]}, the shared scorecard's format) when no part changes side."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blib
from blib import Board, Layout, GROUPS, overlap_xy, inter, load_placement

def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]; opt = dict((x[2:].split("=", 1) + [""])[:2] for x in sys.argv[1:] if x.startswith("--"))
    if not a or "out" not in opt: print(__doc__); sys.exit(2)
    B = Board(); P = {}; src = {}; errs = []; claims = []
    for f in a:
        g = os.path.basename(f)[:-5]
        if g not in GROUPS: errs.append(f"{f}: file name must be one of {GROUPS}.json"); continue
        for r, v in load_placement(f).items():
            if r not in B.parts: errs.append(f"{r} ({g}): unknown ref"); continue
            if r in B.fixed: errs.append(f"{r} ({g}): fixed part, may not be placed"); continue
            if B.group_of.get(r) != g: errs.append(f"{r}: in {g}.json but belongs to {B.group_of.get(r)}"); continue
            if r in P: errs.append(f"{r}: in {src[r]} and {g}"); continue
            P[r] = v; src[r] = g
        m = blib.load_meta(f[:-5] + ".meta.json")
        claims += [dict(c, group=c.get("group", g)) for c in m.get("claims", [])]
    cf = os.path.join(os.path.dirname(os.path.abspath(a[0])), "claims.json")
    if os.path.exists(cf): claims += json.load(open(cf))
    missing = sorted(B.movable - set(P))
    if missing and "allow-missing" not in opt: errs.append(f"missing {len(missing)} refs: {missing[:40]}{' ...' if len(missing) > 40 else ''}")
    L = Layout(B, P); ov = []
    rs = sorted(L.P)
    for i, r1 in enumerate(rs):
        c1, s1, _ = L.geom(r1)
        for r2 in rs[i + 1:]:
            if r1 in B.fixed and r2 in B.fixed: continue
            c2, s2, _ = L.geom(r2)
            if s1 != s2: continue
            ox, oy = overlap_xy(c1, c2)
            if ox > 0.05 and oy > 0.05: ov.append(f"{r1}/{r2} {ox:.2f}x{oy:.2f}")
    if ov:
        msg = f"{len(ov)} courtyard overlaps: {'; '.join(ov[:30])}{' ...' if len(ov) > 30 else ''}"
        if "allow-overlaps" in opt: print("warning (allowed):", msg)
        else: errs.append(msg)
    clash = []; seen = {}
    for c in claims:
        if c["ref"] in seen and tuple(seen[c["ref"]]["box"]) != tuple(c["box"]): clash.append(f"{c['ref']} claimed twice: {seen[c['ref']]['box']} ({seen[c['ref']].get('group')}) and {c['box']} ({c.get('group')})")
        seen.setdefault(c["ref"], c)
    cl = list(seen.values())
    for i, c1 in enumerate(cl):
        for c2 in cl[i + 1:]:
            if c1.get("group") != c2.get("group") and inter(tuple(c1["box"]), tuple(c2["box"])):
                s1 = L.geom(c1["ref"])[1] if c1["ref"] in L.P else "F"; s2 = L.geom(c2["ref"])[1] if c2["ref"] in L.P else "F"
                if s1 == s2: clash.append(f"claim boxes overlap: {c1['ref']} ({c1.get('group')}) {c1['box']} and {c2['ref']} ({c2.get('group')}) {c2['box']}")
    for c in clash: print("claim clash:", c)
    if errs:
        for e in errs: print("REFUSED:", e)
        sys.exit(1)
    out = opt["out"]; json.dump({r: P[r][:3] + [P[r][3] or B.parts[r]["side"]] for r in sorted(P)}, open(out, "w"), indent=0)
    flips = [r for r in P if (P[r][3] or B.parts[r]["side"]) != B.parts[r]["side"]]
    if not flips:
        json.dump({r: P[r][:3] for r in sorted(P)}, open(out[:-5] + ".3.json", "w"), indent=0)
    print(f"wrote {out}: {len(P)} parts from {len(a)} fragments, flipped {len(flips)} {sorted(flips)[:20]}"
          + ("" if flips else f", and {out[:-5]}.3.json for the shared scorecard") + f"; claim clashes {len(clash)}; hpwl {blib.hpwl(B, P):.0f} mm")

if __name__ == "__main__":
    main()
