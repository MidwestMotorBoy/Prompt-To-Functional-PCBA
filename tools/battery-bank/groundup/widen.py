"""Widen routed tracks toward their net-class width where there is room (run with KiCad's python).
  widen.py in.kicad_pcb out.kicad_pcb plan.json [drc.json]
plan.json: {uuid: index into STEPS}; created on the first call (every router-laid track of a GateDrive / Power class
net starts at the class width). With a DRC report, every planned track named in a clearance / short / hole violation
drops one step. Zones are refilled before saving. Repeat with a fresh DRC until no planned track is flagged."""
import sys, json, os
import pcbnew
mm, MM = pcbnew.FromMM, pcbnew.ToMM
src, dst, planf = sys.argv[1:4]
drc = json.load(open(sys.argv[4])) if len(sys.argv) > 4 else None
TARGET = {"GateDrive": 0.4, "Power": 0.8}
STEPS = [0.8, 0.6, 0.5, 0.4, 0.3, 0.25, None]            # None = back to the routed width
b = pcbnew.LoadBoard(src)
tr = {t.m_Uuid.AsString(): t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"}
if os.path.exists(planf):
    plan = json.load(open(planf))
    # pcbnew re-nets a track / via that a too-wide track of another net overlapped (net propagation on load): put it back,
    # so the short shows up in the next DRC and the wide track is lowered instead
    fixed = 0
    for t in b.GetTracks():
        want = plan["nets"].get(t.m_Uuid.AsString())
        if want is not None and t.GetNetname() != want:
            t.SetNet(b.FindNet(want)); fixed += 1
    if fixed:
        print("nets restored", fixed)
else:
    plan = {"orig": {}, "step": {}, "nets": {t.m_Uuid.AsString(): t.GetNetname() for t in b.GetTracks()}}
    for u, t in tr.items():
        w = MM(t.GetWidth())
        cls = [c for c in TARGET if c in t.GetNetClassName()]
        if not cls or w > 0.21:
            continue                                      # hand-drawn copper keeps its width
        tgt = max(TARGET[c] for c in cls)
        plan["orig"][u] = w
        plan["step"][u] = next(i for i, s in enumerate(STEPS) if s is not None and s <= tgt + 1e-9)
flag = set()
if drc:
    for v in drc.get("violations", []):
        if v["type"] in ("clearance", "shorting_items", "hole_clearance", "tracks_crossing", "copper_edge_clearance", "solder_mask_bridge"):
            for it in v["items"]:
                if it["uuid"] in plan["step"]:
                    flag.add(it["uuid"])
    for un in drc.get("unconnected_items", []):           # a widened track pinched a pour neck: lower the widened tracks near it
        for it in un["items"]:
            if it["description"].startswith("Zone"):
                continue
            px, py = it["pos"]["x"], it["pos"]["y"]
            for u, i in plan["step"].items():
                if u in tr and STEPS[i] is not None and STEPS[i] > plan["orig"][u] + 1e-9:
                    t = tr[u]
                    if min(abs(MM(p.x) - px) + abs(MM(p.y) - py) for p in (t.GetStart(), t.GetEnd(), t.GetPosition())) < 2.0:
                        flag.add(u)
    for u in flag:
        plan["step"][u] = len(STEPS) - 1 if os.environ.get("WIDEN_LAST") else min(plan["step"][u] + 1, len(STEPS) - 1)
hist = {}
for u, i in plan["step"].items():
    if u not in tr:
        continue
    w = STEPS[i] if STEPS[i] is not None else plan["orig"][u]
    w = max(w, plan["orig"][u])
    tr[u].SetWidth(mm(w)); hist[w] = hist.get(w, 0) + 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(dst)
json.dump(plan, open(planf, "w"))
print("planned tracks %d, lowered this round %d, widths %s" % (len(plan["step"]), len(flag), sorted(hist.items())))
