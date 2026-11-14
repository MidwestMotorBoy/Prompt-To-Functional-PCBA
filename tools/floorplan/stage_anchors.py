"""stage_anchors.py <board_dump.json> <clusters.json, built without anchors> <constraints.json> <anchors REF,REF,...> <out dump.json>
When a person anchors a hot-loop switch part (anchors.py), its hot-loop capacitors must come with it in the pose
the stage template gives them, or the placer scatters them: the first anchored Monolith trial put C430 9 to 12 mm
from Q401 and three of six loops read open in the loop solver.

Takes each anchored switch part's capacitors' pose relative to the switch from a clusters.json built by
place_sections.py WITHOUT the anchors (there the stage is built switch first, capacitors at its pins), puts them
round the anchored switch where the person placed it, and writes a dump with them there. Prints the capacitors to
add to the anchor list, and writes <out>_poses.json: their x, y and turn against the input board, to put into the
placer's output (place_pack.py writes a fixed part at turn 0). A capacitor the person anchored themselves is left where they put it."""
import sys, json

def turn(v, q):
    x, y = v
    for _ in range(q % 4): x, y = -y, x
    return x, y

def main(dumpf, clf, consf, anchors, outf):
    D = json.load(open(dumpf)); CL = json.load(open(clf)); C = json.load(open(consf)); anc = set(anchors.split(","))
    local = {r: v for parts in CL.values() for r, v in parts.items()}
    fp = {f["ref"]: f for f in D["fps"]}; moved = []; poses = {}; skipped = []
    for hl in C.get("hot_loops", {}).values():
        sw = hl["switch_pins"][0].split(".")[0]
        if sw not in anc or sw not in local: continue
        xs, ys, a_s = local[sw]; qs = int(a_s) // 90
        for c in hl["caps"][:1]:      # the first (high-frequency) capacitor only: bulk ones are placed by the placer, pulled by their near statements
            if c in anc or c in moved or c not in local or c not in fp: continue
            xc, yc, ac = local[c]
            v = turn((xc - xs, yc - ys), -qs); q = (int(ac) // 90 - qs) % 4        # in the switch's own frame, as the dump has it
            nx, ny = fp[sw]["x"] + v[0], fp[sw]["y"] + v[1]; f = fp[c]; ox, oy = f["x"], f["y"]
            def mv(x, y): d = turn((x - ox, y - oy), q); return nx + d[0], ny + d[1]
            if "court" in f:
                b = f["court"]; a_, b_ = mv(b[0], b[1]), mv(b[2], b[3]); court = [min(a_[0], b_[0]), min(a_[1], b_[1]), max(a_[0], b_[0]), max(a_[1], b_[1])]
            else: court = None
            old = f.get("court"); f["court"] = court
            if court and any(not (court[2] <= g["court"][0] or g["court"][2] <= court[0] or court[3] <= g["court"][1] or g["court"][3] <= court[1])
                   for g in D["fps"] if g["ref"] != c and "court" in g and g.get("side") == f.get("side") and (g["ref"] in anc or g["ref"] in moved or g["ref"].rstrip("0123456789") in ("J", "H", "TP", "SW"))):
                f["court"] = old; skipped.append(c); continue      # would sit on another anchor: the person's placement and the template disagree
            for p in D["pads"]:
                if p["ref"] != c: continue
                p["x"], p["y"] = mv(p["x"], p["y"]); b = p["box"]; a_, b_ = mv(b[0], b[1]), mv(b[2], b[3])
                p["box"] = [min(a_[0], b_[0]), min(a_[1], b_[1]), max(a_[0], b_[0]), max(a_[1], b_[1])]
            f["x"], f["y"] = nx, ny; f["rot"] = (f.get("rot", 0) + 90 * q) % 360; moved.append(c); poses[c] = [round(nx, 3), round(ny, 3), 90 * q]
    json.dump(D, open(outf, "w")); json.dump(poses, open(outf.replace(".json", "_poses.json"), "w")); print(",".join(moved))
    if skipped: print("left to the placer (template pose sits on another anchor):", ",".join(skipped), file=sys.stderr)

if __name__ == "__main__":
    main(*sys.argv[1:6])
