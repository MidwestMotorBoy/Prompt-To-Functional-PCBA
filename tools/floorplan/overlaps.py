"""overlaps.py <board dump.json> [placement.json]: lists courtyard overlaps, keep-out hits and parts off the board."""
import json, sys
d = json.load(open(sys.argv[1])); P = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else {}
B = {}
for f in d["fps"]:
    if "court" not in f: continue
    c = [f["court"][0] - f["x"], f["court"][1] - f["y"], f["court"][2] - f["x"], f["court"][3] - f["y"]]; x, y, a = P.get(f["ref"], [f["x"], f["y"], 0])
    q = [(c[0], c[1]), (c[2], c[3])]
    for _ in range(int(a) // 90 % 4): q = [(-v, u) for u, v in q]
    B[f["ref"]] = (x + min(q[0][0], q[1][0]), y + min(q[0][1], q[1][1]), x + max(q[0][0], q[1][0]), y + max(q[0][1], q[1][1]), f["side"])
rs = sorted(B); tot = 0
for i, a in enumerate(rs):
    for b in rs[i + 1:]:
        A, C = B[a], B[b]
        if A[4] != C[4]: continue
        ox = min(A[2], C[2]) - max(A[0], C[0]); oy = min(A[3], C[3]) - max(A[1], C[1])
        if ox > 0.01 and oy > 0.01: tot += ox * oy; print(f"overlap {a} / {b}: {ox:.2f} x {oy:.2f} mm")
for k in d.get("keepouts", []):
    if not k.get("no_footprints"): continue
    for r, A in B.items():
        if A[4] in k["layers"]:
            ox = min(A[2], k["box"][2]) - max(A[0], k["box"][0]); oy = min(A[3], k["box"][3]) - max(A[1], k["box"][1])
            if ox > 0.01 and oy > 0.01: tot += ox * oy; print(f"keep-out {k['name']}: {r} {ox:.2f} x {oy:.2f} mm")
bx = d["box"]
for r, A in B.items():
    if A[0] < bx[0] or A[1] < bx[1] or A[2] > bx[2] or A[3] > bx[3]: print(f"off board: {r}")
print(f"total {tot:.2f} mm2")
