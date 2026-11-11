"""score_task.py <candidate netlist> <original netlist (.json or .net)> <original constraints.json> <limits dir> <limitsmap.json> <design dir>
Machine score for the spike 5 task (task.md). The candidate is a netlist.json from the new pipeline or a KiCad
`.net` export from the old way. Prints one JSON line:
  targets_met    of the 6 new targets (3 per port), how many are inside tolerance
  others_held    of the expectations that were not to change, how many still hold
  wiring_changed pins whose net membership differs from the original (should be 0)
  parts_changed  parts whose value changed; stale_fields = changed value but the MPN or LCSC field left as it was
  new_findings   intent-gate findings the original did not have (ratings, pin rules), apart from expectations"""
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here + "/../02-seeded-faults"); sys.path.insert(0, here + "/../01-blocks-as-code/tools"); sys.path.insert(0, sys.argv[6])
import intent_check, netlist_truth, symlib
NEW = {"battery regulation": 16.4, "charge current limit": 3.0, "input current limit": 3.25}
cand = netlist_truth.load(sys.argv[1]) if sys.argv[1].endswith(".net") else json.load(open(sys.argv[1]))
cand["nets"] = {n: [[x[0], x[1]] for x in v] for n, v in cand["nets"].items()}
orig = netlist_truth.load(sys.argv[2]) if sys.argv[2].endswith(".net") else json.load(open(sys.argv[2]))
orig["nets"] = {n: [[x[0], x[1]] for x in v] for n, v in orig["nets"].items()}; cons = json.load(open(sys.argv[3]))
limits = intent_check.load_limits(sys.argv[4]); kbmap = json.load(open(sys.argv[5]))
cand["comps"] = {r: c for r, c in cand["comps"].items() if r in orig["comps"]} | {r: c for r, c in cand["comps"].items() if r not in orig["comps"] and any(x[0] == r for v in cand["nets"].values() for x in v)}
want = json.loads(json.dumps(cons))
for k, e in want["expect"].items():
    if k.split("/")[-1] in NEW: e["target"] = NEW[k.split("/")[-1]]
base = intent_check.check(orig, cons, limits, kbmap, symlib)
f = intent_check.check({**cand, "nets": {n: [x for x in v if x[0] in orig["comps"]] for n, v in cand["nets"].items()}}, want, limits, kbmap, symlib)
bad = {k for k in want["expect"] if any(x.startswith(f"expect: {k} ") or x.startswith(f"expect: {k}:") for x in f)}
tgt = [k for k in want["expect"] if k.split("/")[-1] in NEW]; oth = [k for k in want["expect"] if k not in tgt]
def part(d):
    refs = set(orig["comps"]); return {frozenset((r, p) for r, p in v if r in refs) for v in d["nets"].values()} - {frozenset()}
pa, pb = part(orig), part(cand); wiring = sorted({x for g in pa ^ pb for x in g})
changed = sorted(r for r, c in orig["comps"].items() if r in cand["comps"] and c["value"] != cand["comps"][r]["value"])
stale = [r for r in changed if any(orig["comps"][r].get("fields", {}).get(k) and orig["comps"][r]["fields"][k] == cand["comps"][r].get("fields", {}).get(k) for k in ("MPN", "LCSC"))]
print(json.dumps(dict(targets_met=f"{len([k for k in tgt if k not in bad])}/{len(tgt)}", others_held=f"{len([k for k in oth if k not in bad])}/{len(oth)}",
    wiring_changed=len(wiring), parts_missing=sorted(set(orig["comps"]) - set(cand["comps"])), parts_added=sorted(set(cand["comps"]) - set(orig["comps"])),
    parts_changed={r: [orig["comps"][r]["value"], cand["comps"][r]["value"]] for r in changed}, stale_fields=stale,
    new_findings=sorted(x for x in f - base if not x.startswith("expect:")), failed=sorted(x for x in f if x.startswith("expect:")))))
