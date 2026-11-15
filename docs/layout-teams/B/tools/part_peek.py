"""part_peek.py <frag.json ...> [--set=REF:x,y,turn[,side] ...] REF [REF ...]
Prints courtyard box, pads (net, box) and legality faults (courtyard, ring, reserved, region) of the named parts in the
placement made of the given fragments (later files win), after the --set overrides. Rings and reserved boxes come from
the fragments' meta files, as in check.py. A quick look before writing a put step."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check
files, sets, refs = [], {}, []
for a in sys.argv[1:]:
    if a.startswith("--set="):
        r, v = a[6:].split(":"); v = v.split(",")
        sets[r] = [float(v[0]), float(v[1]), int(v[2])] + ([v[3]] if len(v) > 3 else [])
    elif a.endswith(".json"): files.append(a)
    else: refs.append(a)
B, L, P = check.load_all(files)
for r, v in sets.items():
    if len(v) == 3: v.append(B.parts[r]["side"] if r not in P else P[r][3] if len(P[r]) > 3 else B.parts[r]["side"])
    L.put(r, v)
for r in refs:
    c, s, pads = L.geom(r)
    print("%s %s court %.2f-%.2f, %.2f-%.2f  faults %s" % (r, L.val(r), c[0], c[2], c[1], c[3], L.faults(r)))
    for p in pads:
        print("   pad %s %-22s %.2f-%.2f, %.2f-%.2f" % (p[0], (p[1] or "").split("/")[-1][:22], p[4][0], p[4][2], p[4][1], p[4][3]))
