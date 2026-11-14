"""twin_recipe.py <src fragment> <out recipe.json> --map=4->5 --dx=-23.02577 --dy=0.006368 REF [REF ...]
Writes a recipe of explicit `put` steps that copy parts of one port to their twins in the other.

Why not secplace's `translate` step: it copies the turn value, but turns are relative to each part's template
orientation, and some twins sit in the template at another orientation than their Port 1 part (R445/R545, C416/C516,
C415/C515, R428/R528 are 90 degrees apart). The copy then comes out turned. This tool picks, for each twin, the turn
that puts every pad where the shifted source pad is (absolute pad match, worst pad error printed), and the courtyard
differences of 0.01 mm between twins are then handled by `nudge` (a put that is illegal is tried again at small
offsets, up to `--nudge` mm, before giving up)."""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blib

def abs_pads(B, r, v):
    return {p[0]: (p[2] - v[0], p[3] - v[1]) for p in B.pads(r, v) if p[0]}

def main(a):
    opt = dict((x[2:].split("=", 1) + [""])[:2] for x in a if x.startswith("--"))
    pos = [x for x in a if not x.startswith("--")]
    src, out, refs = pos[0], pos[1], pos[2:]
    dx, dy = float(opt.get("dx", -23.02577)), float(opt.get("dy", 0.006368)); m = opt.get("map", "4->5")
    B = blib.Board(); F = blib.load_placement(src); steps = []
    for r0 in refs:
        r = blib.map_ref(r0, m); v0 = F[r0]
        s0 = v0[3] or B.parts[r0]["side"]
        P0 = abs_pads(B, r0, v0)
        best = None
        for q in (0, 90, 180, 270):
            v = [v0[0] + dx, v0[1] + dy, q, s0]
            P = abs_pads(B, r, v)
            # pads with repeated numbers: compare as sorted lists per number
            err = 0.0
            for n in P0:
                a0 = sorted(p for p in [(pp[2] - v0[0], pp[3] - v0[1]) for pp in B.pads(r0, v0) if pp[0] == n])
                a1 = sorted(p for p in [(pp[2] - v[0], pp[3] - v[1]) for pp in B.pads(r, v) if pp[0] == n])
                if len(a0) != len(a1): err = 99; break
                err = max([err] + [math.hypot(u[0] - w[0], u[1] - w[1]) for u, w in zip(a0, a1)])
            if best is None or err < best[0]: best = (err, q, v)
        err, q, v = best
        note = f"twin of {r0}: turn {v0[2]} -> {q} (template orientations {'differ' if q != v0[2] else 'match'}), worst pad error {err:.3f} mm"
        print(f"{r}: {note}")
        steps.append({"put": r, "at": [round(v[0], 6), round(v[1], 6)], "turn": q, "side": s0, "note": note})
    json.dump(steps, open(out, "w"), indent=1)

if __name__ == "__main__":
    main(sys.argv[1:])
