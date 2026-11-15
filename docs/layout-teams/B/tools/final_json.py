"""final_json.py <source run dir> <final_route out dir> <route minutes> <straps 0|1>
Called by final_route.sh: gathers the numbers of the routed-board check into <out dir>/final.json and prints them.
Fields (all from files of this run; null when a step did not run):
  straps            what straps.py laid per net (groups, tied, untied, length, length across the signal lanes)
  drc_errors        KiCad DRC errors of the copper board before routing (must be 0)
  blocked_edges     ghost screen of the copper board: "N of M" edges with no path even on an empty board
  route             full trial route: routed, failed, edges, timed_out, the router's own text
  pre_route         loss_W and power_open of the copper board (dc_score.py on cu.kicad_pcb)
  routed            loss_W, power_open, loose pads and KiCad DRC (errors, unconnected items, those of PACK_P/3V3/GND)
                    of the routed board
  hot_routed        hot loops of the routed board: pass count, sum, each loop's total nH and tier 1
  hot_pre_source    the same from the source run (before routing, without straps), when it has hot_gate.json
"""
import sys, os, json, re
src, out, rmin, straps = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "1"
J = lambda *p: json.load(open(os.path.join(*p))) if os.path.exists(os.path.join(*p)) else None
def dc_sum(d):
    if d is None: return None
    nets = d.get("nets", d)
    return dict(loss_W=round(sum(v.get("loss_W", 0) for v in nets.values() if isinstance(v, dict)), 3),
                power_open={k: v["open"] for k, v in nets.items() if isinstance(v, dict) and v.get("open")})
def gate(path):
    g = J(path)
    if g is None: return None
    return dict(pass_count=f"{sum(1 for r in g if r['tier1'].startswith('pass'))} of {len(g)}",
                sum_nH=round(sum(r.get("loop_total_nH", 0) for r in g), 2),
                loops={r["loop"]: dict(total_nH=r.get("loop_total_nH"), tier1=r["tier1"]) for r in g})
F = {"source_run": os.path.abspath(src), "straps": None, "route_minutes": int(rmin)}
sp = J(out, "split", "spec.json")
if straps and sp: F["straps"] = sp.get("straps", [])
sc = J(out, "score.json") or {}
F["drc_errors"] = sc.get("drc_errors"); F["blocked_edges"] = sc.get("blocked_edges")
F["route"] = None
if rmin != "0" and os.path.exists(os.path.join(out, "route.log")):
    r = open(os.path.join(out, "route.log")).read()
    e = re.search(r"edges to route: (\d+)", r); m = re.search(r"^routed (\d+) edges, (\d+) failed", r, re.M)
    if m: F["route"] = dict(routed=int(m.group(1)), failed=int(m.group(2)), edges=int(e.group(1)) if e else None, timed_out=False)
    else:
        p = re.findall(r"routed (\d+), failing (\d+)", r)
        F["route"] = dict(routed=int(p[-1][0]) if p else None, failed=int(p[-1][1]) if p else None, edges=int(e.group(1)) if e else None, timed_out=True)
    u = re.search(r"unconnected after fill: (\d+)", r)
    F["route"]["unconnected_after_fill"] = int(u.group(1)) if u else None
    F["route"]["text"] = sc.get("route")
F["scored_board"] = "finished.kicad_pcb (after --post)" if os.path.exists(os.path.join(out, "finished.kicad_pcb")) else "routed.kicad_pcb"
F["filters"] = sorted(f for f in os.listdir(os.path.join(out, "split")) if f.startswith("filter_")) if os.path.isdir(os.path.join(out, "split")) else []
F["pre_route"] = dc_sum(J(out, "dc.json"))
F["routed"] = dc_sum(J(out, "routed", "dc.json"))
if F["routed"] is not None:
    lo = os.path.join(out, "routed", "loose.log")
    F["routed"]["loose"] = [l.strip() for l in open(lo) if "pads not joined" in l] if os.path.exists(lo) else None
    d = J(out, "routed", "drc.json")
    if d:
        pw = []
        for u in d.get("unconnected_items", []):
            s = " | ".join(i["description"] for i in u["items"])
            if any(f"[{n}]" in s for n in ("PACK_P", "3V3", "GND")): pw.append(s)
        F["routed"]["drc_errors"] = sum(1 for v in d["violations"] if v["severity"] == "error")
        F["routed"]["drc_error_types"] = sorted({v["type"] for v in d["violations"] if v["severity"] == "error"})
        F["routed"]["unconnected_items"] = len(d.get("unconnected_items", []))
        F["routed"]["unconnected_power"] = pw
F["hot_routed"] = gate(os.path.join(out, "routed", "hot_gate.json"))
F["hot_pre_source"] = gate(os.path.join(src, "hot_gate.json"))
json.dump(F, open(os.path.join(out, "final.json"), "w"), indent=1)
print("FINAL", json.dumps(F))
