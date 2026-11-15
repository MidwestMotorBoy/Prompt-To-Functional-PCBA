"""xings.py <corridors dbg.json> ...: crossings between corridor strips of different nets on the same side (ccorr's CORR_DEBUG output)."""
import sys, json
def cr(ux, uy, vx, vy): return ux * vy - uy * vx
for f in sys.argv[1:]:
    st = [s for s in json.load(open(f))["shapes"] if s["kind"] == "strip"]; out = []
    for i in range(len(st)):
        for j in range(i + 1, len(st)):
            a, b = st[i], st[j]
            if a["net"] == b["net"] or not set(a["sides"]) & set(b["sides"]): continue
            ax, ay, bx, by = a["g"][:4]; px, py, qx, qy = b["g"][:4]
            if (cr(bx - ax, by - ay, px - ax, py - ay) * cr(bx - ax, by - ay, qx - ax, qy - ay) < 0 and
                    cr(qx - px, qy - py, ax - px, ay - py) * cr(qx - px, qy - py, bx - px, by - py) < 0):
                out.append(a["net"].split("/")[-2][-6:] + ":" + a["net"].split("/")[-1] + " x " + b["net"].split("/")[-2][-6:] + ":" + b["net"].split("/")[-1])
    print(f, len(out), out)
