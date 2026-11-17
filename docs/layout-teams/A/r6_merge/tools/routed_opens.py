#!/usr/bin/env python3
"""routed_opens.py <scorecard outdir> : team A r6_merge. The router's "N failed" is NOT the number of open connections
(router.py counts an edge as routed when an escape stub touches own-net copper, skips 'Zone | Zone' items, and turns a
'Zone | Pad' item of a non-plane net into a zero-length route). The judge is KiCad's DRC on the routed board: this adds
to score.json  routed_unconnected_by_net {net: count}  and  routed_unconnected_items [text], and prints them."""
import json, re, sys, collections, os
o = sys.argv[1]; d = json.load(open(os.path.join(o, "drc_routed.json")))
cnt = collections.Counter(); items = []
for u in d.get("unconnected_items", []):
    s = " | ".join(i["description"] for i in u["items"]); n = re.search(r"\[(.*?)\]", s)
    cnt[n.group(1) if n else "?"] += 1
    items.append(s + " @ " + " -> ".join("%.2f,%.2f" % (i["pos"]["x"], i["pos"]["y"]) for i in u["items"]))
p = os.path.join(o, "score.json"); s = json.load(open(p))
s["routed_unconnected_by_net"] = dict(cnt); s["routed_unconnected_items"] = items
json.dump(s, open(p, "w"), indent=1)
print(json.dumps(dict(cnt))); print("\n".join(items))
