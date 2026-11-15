"""recipe_put.py <recipe.json> REF=x,y,turn[,side] ... [--allow=CHIP:REF,REF] [--note=REF:text]
Edits the explicit "put" steps of a recipe in place (a put step for REF must exist), for quick placement trials.
--allow adds refs to the allow list of the ring step of CHIP. --note replaces the note of REF's put step."""
import sys, json
a = [x for x in sys.argv[1:] if not x.startswith("--")]; opt = [x for x in sys.argv[1:] if x.startswith("--")]
path = a[0]; R = json.load(open(path))
for m in a[1:]:
    ref, v = m.split("="); f = v.split(","); hit = False
    for s in R:
        if s.get("put") == ref:
            s["at"] = [float(f[0]), float(f[1])]; s["turn"] = int(f[2])
            if len(f) > 3: s["side"] = f[3]
            hit = True
    if not hit: sys.exit(f"no put step for {ref}")
for o in opt:
    k, v = o[2:].split("=", 1)
    if k == "allow":
        chip, refs = v.split(":")
        for s in R:
            if s.get("ring") == chip:
                s["allow"] = s.get("allow", []) + [r for r in refs.split(",") if r not in s.get("allow", [])]
    if k == "note":
        ref, t = v.split(":", 1)
        for s in R:
            if s.get("put") == ref: s["note"] = t
json.dump(R, open(path, "w"), indent=1); print("edited", path)
