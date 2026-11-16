#!/usr/bin/env python3
"""plan_summary.py <outdir>: which copper rules ran and what the selective ones picked (from spec.json's report)."""
import sys, json, os
f = os.path.join(sys.argv[1], "spec.json")
if not os.path.exists(f): sys.exit(0)
R = json.load(open(f)).get("report", {}); ru = R.get("rules", {})
pe = ru.get("pinesc", {})
print("CHECK " + json.dumps({"rules_on": R.get("rules_on"), "pinesc_select": pe.get("select"),
                             "pinesc_ics": sorted({k.split(".")[0] for k in pe.get("pins", [])}),
                             "left_to_router": {n: r.get("left_to_router") for n, r in R.get("nets", {}).items() if r.get("left_to_router")}}))
