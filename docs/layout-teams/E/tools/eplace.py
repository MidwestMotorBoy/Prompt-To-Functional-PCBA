"""eplace.py <base.e.json (hand board dump)> <moves.txt> <placement.json>
Hand placement as a list of moves on the hand board. One move per line ('#' starts a comment):
    REF x y [rN]         put the part's origin at x, y; rN = turn it N degrees (90, 180, 270) from the hand board
    REF +dx -dy [rN]     shift from where the hand board has it (a sign on both numbers)
    REF1,REF2,... +dx +dy   shift a group
    REF @OTHER +dx +dy [rN]  put it at OTHER's (final) origin plus an offset
Writes the placement file for apply_placement.py (only the moved parts) and prints every courtyard box overlap among
parts on the same side, plus parts whose courtyard leaves the board box."""
import sys, json, re
D = json.load(open(sys.argv[1])); F = {f["ref"]: f for f in D["fps"]}
pos = {r: [f["x"], f["y"], 0] for r, f in F.items()}
for ln, line in enumerate(open(sys.argv[2]), 1):
    line = line.split("#")[0].split()
    if not line: continue
    refs = line[0].split(","); rest = line[1:]; rot = None; at = None
    if rest and rest[-1].startswith("r"): rot = int(rest[-1][1:]); rest = rest[:-1]
    if rest and rest[0].startswith("@"): at = rest[0][1:]; rest = rest[1:]
    for r in refs:
        if r not in F: sys.exit("line %d: no part %s" % (ln, r))
        if at:
            dx, dy = (float(rest[0]), float(rest[1])) if rest else (0.0, 0.0)
            pos[r][0], pos[r][1] = round(pos[at][0] + dx, 4), round(pos[at][1] + dy, 4)
        elif rest:
            rel = rest[0][0] in "+-" and rest[1][0] in "+-"
            if rel: pos[r][0] = round(F[r]["x"] + float(rest[0]), 4); pos[r][1] = round(F[r]["y"] + float(rest[1]), 4)
            else: pos[r][0], pos[r][1] = float(rest[0]), float(rest[1])
        if rot is not None: pos[r][2] = rot % 360
def court(r):
    f = F[r]; x, y, a = pos[r]; l, t, rr, b = f["court"]; pts = [(l - f["x"], t - f["y"]), (rr - f["x"], b - f["y"])]
    for _ in range(a // 90): pts = [(-py, px) for px, py in pts]
    xs = [x + p[0] for p in pts]; ys = [y + p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)
P = {r: p for r, p in pos.items() if p != [F[r]["x"], F[r]["y"], 0]}
json.dump(P, open(sys.argv[3], "w"), indent=0)
C = {r: court(r) for r in F}; bad = 0
xs = [p[0] for o in D["outline"] for p in o["ring"]]; ys = [p[1] for o in D["outline"] for p in o["ring"]]
refs = sorted(F)
for i, a in enumerate(refs):
    ca = C[a]
    if a in P and (ca[0] < min(xs) or ca[1] < min(ys) or ca[2] > max(xs) or ca[3] > max(ys)): print("OFF BOARD", a, [round(v, 2) for v in ca]); bad += 1
    for b in refs[i + 1:]:
        if a not in P and b not in P: continue
        if F[a]["layer"] != F[b]["layer"]: continue
        cb = C[b]; ox = min(ca[2], cb[2]) - max(ca[0], cb[0]); oy = min(ca[3], cb[3]) - max(ca[1], cb[1])
        if ox > 0.06 and oy > 0.06:      # courtyard boxes include the 0.05 mm line print("OVERLAP %s %s by %.2f x %.2f mm" % (a, b, ox, oy)); bad += 1
print("%d parts moved, %d problems" % (len(P), bad))
