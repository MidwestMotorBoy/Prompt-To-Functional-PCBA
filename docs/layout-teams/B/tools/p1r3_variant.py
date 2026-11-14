"""p1r3_variant.py <out dir> '<json overrides>'   (round-3 Port 1 helper)
Writes 03-buck5v.json, 04-pd.json, 05-protect.json, 06-9v.json into <out dir>, copied from recipes/port1/try/r3/ with
the overrides applied. Overrides: {"put": {ref: [x, y, turn]}, "ring_allow": {chip: [refs]}, "box": {reserve name: box}, "drop": [refs], "reserve": [steps], "step": {ref: {key: value}} (merged into the step that places ref)}.
"put" replaces the step that places ref (put or at_pin) by an explicit put at that spot, in the same place in the
recipe order; "drop" removes a reserve step by name; "reserve" steps are added to 05-protect.json first."""
import sys, json, os, shutil
here = os.path.dirname(os.path.abspath(__file__)); B = os.path.dirname(here)
src = os.path.join(B, "recipes/port1/try/r3"); out = sys.argv[1]; ov = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
os.makedirs(out, exist_ok=True)
for f in ("03-buck5v.json", "04-pd.json", "05-protect.json", "06-9v.json"):
    R = json.load(open(os.path.join(src, f))); o = []
    if f == "05-protect.json": o += ov.get("reserve", [])
    for s in R:
        ref = s.get("put") or s.get("at_pin")
        if ref and ref in ov.get("put", {}):
            x, y, t = ov["put"][ref]; o.append({"put": ref, "at": [x, y], "turn": t, "side": "F", "note": s.get("note", "")}); continue
        if s.get("reserve") in ov.get("drop", []): continue
        if ref and ref in ov.get("step", {}): s = dict(s, **ov["step"][ref])
        if s.get("ring") in ov.get("ring_allow", {}): s = dict(s, allow=ov["ring_allow"][s["ring"]])
        if s.get("reserve") in ov.get("box", {}): s = dict(s, box=ov["box"][s["reserve"]])
        o.append(s)
    json.dump(o, open(os.path.join(out, f), "w"), indent=1)
print(" ".join(os.path.join(out, f) for f in ("03-buck5v.json", "04-pd.json", "05-protect.json", "06-9v.json")))
