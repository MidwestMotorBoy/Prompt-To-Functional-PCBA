"""stage_copper.py <placed bare board.kicad_pcb> <constraints.json> <out.kicad_pcb>      (KiCad's python: needs pcbnew)
Rule-made power copper for every declared hot loop, so that the loop solver can score a placement before any real
copper design exists. The same rules for every placement, so two placements compare fairly; the absolute numbers are
checked against the hand board's real copper (see README).
Rules, per hot loop (supply net, return net, switch pins, capacitors, from the circuit code's hot_loop()):
  - return net: a solid plane on In1.Cu and In4.Cu over the whole board (once);
  - on the switch part's layer: one pour for the supply net over the convex hull of the loop's supply pads (grown
    0.3 mm), one for the return net over the hull of its return pads; the supply pour has priority;
  - return vias: up to 2 beside each capacitor's return pad and 3 beside the switch's return pads, at the free
    spots nearest the switch, 0.45/0.3 mm, kept 0.2 mm from pads of other nets and 0.6 mm from each other."""
import sys, json, math, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); C = json.load(open(sys.argv[2])); mm = pcbnew.ToMM; FM = pcbnew.FromMM
fps = {f.GetReference(): f for f in b.GetFootprints()}
def netname(short): 
    for n in b.GetNetsByName().keys():
        n = str(n)
        if n == short or n.endswith("/" + short): return n
    raise SystemExit("no net " + short)
def box(p): r = p.GetBoundingBox(); return (mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom()))
def hull(pts):
    pts = sorted(set(pts))
    def half(ps):
        h = []
        for p in ps:
            while len(h) >= 2 and (h[-1][0] - h[-2][0]) * (p[1] - h[-2][1]) - (h[-1][1] - h[-2][1]) * (p[0] - h[-2][0]) <= 0: h.pop()
            h.append(p)
        return h
    return half(pts)[:-1] + half(pts[::-1])[:-1]
def corners(bx, g): return [(bx[0] - g, bx[1] - g), (bx[2] + g, bx[1] - g), (bx[2] + g, bx[3] + g), (bx[0] - g, bx[3] + g)]
def zone(net, layer, pts, prio, name):
    z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNetCode(b.GetNetcodeFromNetname(net)); z.SetZoneName(name); o = z.Outline(); o.NewOutline()
    for x, y in pts: o.Append(FM(x), FM(y))
    z.SetAssignedPriority(prio); z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL); z.SetLocalClearance(FM(0.2)); z.SetMinThickness(FM(0.15)); b.Add(z)
def pinname(fn, num): return fn[:-len(num) - 1] if num and fn.endswith("_" + num) else fn   # KiCad boards from the build name pins "<name>_<pad>"
allpads = [(p, box(p), p.GetNetname()) for f in b.GetFootprints() for p in f.Pads()]
vias = []
def via_ok(x, y, net):
    for p, bx, n in allpads:
        if n == net: continue
        dx = max(bx[0] - x, 0, x - bx[2]); dy = max(bx[1] - y, 0, y - bx[3])
        if math.hypot(dx, dy) < 0.225 + 0.2: return False
    e = b.GetBoardEdgesBoundingBox()
    if not (mm(e.GetLeft()) + 0.6 < x < mm(e.GetRight()) - 0.6 and mm(e.GetTop()) + 0.6 < y < mm(e.GetBottom()) - 0.6): return False
    return all(math.hypot(x - vx, y - vy) >= 0.6 for vx, vy in vias)
def add_vias(pad, net, toward, count):
    bx = box(pad); cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2; cand = []
    for d in (0.45, 0.9, 1.4):   # rings further out only when the nearer one is blocked
        ring = []
        for t in (-0.5, -0.25, 0.0, 0.25, 0.5):
            ring += [(bx[0] - d, cy + t * (bx[3] - bx[1])), (bx[2] + d, cy + t * (bx[3] - bx[1])), (cx + t * (bx[2] - bx[0]), bx[1] - d), (cx + t * (bx[2] - bx[0]), bx[3] + d)]
        cand.append(ring)
    n = 0
    for ring in cand:
        for x, y in sorted(ring, key=lambda q: math.hypot(q[0] - toward[0], q[1] - toward[1])):
            if n >= count: break
            if not via_ok(x, y, net): continue
            v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(FM(x), FM(y))); v.SetDrill(FM(0.3)); v.SetNetCode(b.GetNetcodeFromNetname(net)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            try: v.SetWidth(pcbnew.F_Cu, FM(0.45))
            except TypeError: v.SetWidth(FM(0.45))
            b.Add(v); vias.append((x, y)); n += 1
    return n
e = b.GetBoardEdgesBoundingBox(); whole = corners((mm(e.GetLeft()), mm(e.GetTop()), mm(e.GetRight()), mm(e.GetBottom())), -0.3); rets = set(); report = {}
for name, hl in sorted(C["hot_loops"].items()):
    P, G = netname(hl["supply"]), netname(hl["ret"]); dev = hl["switch_pins"][0].split(".")[0]; f = fps[dev]; layer = f.GetLayer()
    if G not in rets:
        rets.add(G)
        for L in (pcbnew.In1_Cu, pcbnew.In4_Cu): zone(G, L, whole, 0, "plane_" + G)
    fns = {s.split(".")[1] for s in hl["switch_pins"]}; nums = {n for t in hl["switch_pins"] for n in C.get("pin_pads", {}).get(t, [])}
    sw = [p for p in f.Pads() if (p.GetNumber() in nums if nums else pinname(p.GetPinFunction(), p.GetNumber()) in fns)]; members = [fps[c] for c in hl["caps"]]
    pp = [p for p in sw if p.GetNetname() == P] + [p for m in members for p in m.Pads() if p.GetNetname() == P]
    gp_sw = [p for p in sw if p.GetNetname() == G]; gp_c = [p for m in members for p in m.Pads() if p.GetNetname() == G]
    if not pp or not gp_sw: raise SystemExit(f"{name}: switch pins {hl['switch_pins']} not found on {P} / {G}")
    v0 = len(vias); bridges = 0; ctr = (sum((box(p)[0] + box(p)[2]) / 2 for p in gp_sw) / len(gp_sw), sum((box(p)[1] + box(p)[3]) / 2 for p in gp_sw) / len(gp_sw))
    nv = sum(add_vias(p, G, ctr, 2) for p in gp_c); left = 3
    for p in gp_sw:
        k = add_vias(p, G, ctr, left); left -= k; nv += k
        if k == 0 and gp_c:   # a return pin with no room for a via (fine-pitch IC): strip of return copper straight to the nearest capacitor return pad, over the supply pour
            c = lambda q: ((box(q)[0] + box(q)[2]) / 2, (box(q)[1] + box(q)[3]) / 2)
            near = min(gp_c, key=lambda q: math.hypot(c(q)[0] - c(p)[0], c(q)[1] - c(p)[1]))
            zone(G, layer, hull(corners(box(p), 0.0) + corners(box(near), 0.0)), 30, "hl_" + name + "_return_strip"); bridges += 1
        if left <= 0: break
    # bulk capacitors (all but the first) and the switch's supply pads also get vias to a supply pour on In2, next to the
    # ground plane: a bulk capacitor seldom has a clear path on the part layer once the first capacitor sits at the pins
    v1 = len(vias); pc = lambda p: ((box(p)[0] + box(p)[2]) / 2, (box(p)[1] + box(p)[3]) / 2); sup_sw = [p for p in sw if p.GetNetname() == P]
    pctr = (sum(pc(p)[0] for p in sup_sw) / len(sup_sw), sum(pc(p)[1] for p in sup_sw) / len(sup_sw))
    bulk = [p for m in members[1:] for p in m.Pads() if p.GetNetname() == P]; nsv = sum(add_vias(p, P, pctr, 2) for p in bulk) if bulk else 0
    if nsv:
        left = 3
        for p in sup_sw:
            kq = add_vias(p, P, ctr, left); left -= kq; nsv += kq
            if left <= 0: break
        if left == 3:     # no room at the switch's supply pads (fine-pitch part): the inner pour joins at the first capacitor instead
            nsv += sum(add_vias(p, P, pctr, 2) for p in members[0].Pads() if p.GetNetname() == P)
        zone(P, pcbnew.In2_Cu, hull([q for p in pp for q in corners(box(p), 0.5)] + [q for v in vias[v1:] for q in corners((v[0], v[1], v[0], v[1]), 0.5)]), 20, "hl_" + name + "_supply_inner")
    zone(P, layer, hull([q for p in pp for q in corners(box(p), 0.3)] + [q for v in vias[v1:] for q in corners((v[0], v[1], v[0], v[1]), 0.45)]), 20, "hl_" + name + "_supply")
    zone(G, layer, hull([q for p in gp_sw + gp_c for q in corners(box(p), 0.3)] + [q for v in vias[v0:] for q in corners((v[0], v[1], v[0], v[1]), 0.45)]), 10, "hl_" + name + "_return")
    report[name] = dict(supply_pads=len(pp), return_pads=len(gp_sw) + len(gp_c), return_vias=nv, return_strips=bridges, supply_vias=nsv)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pro = sys.argv[3][:-10] + ".kicad_pro"; import os; keep = open(pro, "rb").read() if os.path.exists(pro) else None
b.Save(sys.argv[3])
if keep is not None: open(pro, "wb").write(keep)
print(json.dumps(report))
