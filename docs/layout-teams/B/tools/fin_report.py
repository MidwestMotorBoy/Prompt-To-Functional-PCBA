"""fin_report.py <drc.json> <isl_edges.json> <out drc.json> [--nets=PACK_P,3V3]
(team B, finishing pass, phase 2 round 2) The report the accept-or-revert continuation (router_b.py --aor) starts from:
KiCad's DRC json of the board with the unconnected items of the power nets replaced by the edges of isl.py
(tools/battery-bank/groundup/isl.py, one 'PlanePiece <layer> #<k> [net]' or 'Pad ...' to 'Zone main' per cut-off piece).
KiCad pairs the nearest items of two pieces (often 'Zone | Zone', which the router never routes); isl.py names the piece,
and router_b.py --pieces=<isl_pieces.json> starts the route anywhere on that piece and ends it on the net's main body."""
import sys, json, re
A = [a for a in sys.argv[1:] if not a.startswith("--")]
O = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
NETS = set(O.get("nets", "PACK_P,3V3").split(","))
d = json.load(open(A[0])); e = json.load(open(A[1]))["unconnected_items"]
nm = lambda u: (re.search(r"\[(.*?)\]", u["items"][0]["description"]) or [0, None])[1]
keep = [u for u in d.get("unconnected_items", []) if nm(u) not in NETS]
d["unconnected_items"] = keep + e
json.dump(d, open(A[2], "w"), indent=1)
n0 = sum(1 for u in json.load(open(A[0]))["unconnected_items"] if nm(u) in NETS)
print("fin_report: %d unconnected items kept, %d power items replaced by %d piece edges" % (len(keep), n0, len(e)))
