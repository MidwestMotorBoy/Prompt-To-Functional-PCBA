"""fin_trim.py <board in> <drc.json of board in> <board out> [--margin=0.03]     (team B, finishing pass; KiCad's python)
Cures clearance errors between two pad stubs of neighbouring pins (r4: CELL_1N against TS1 / BTP_INT / SMBD at U101,
0.4 mm pitch, rule 'HighCurrent copper to small signals' 0.25 mm). The router starts every fan-out stub at the pad
centre, so two stubs of neighbouring pins that leave in opposite directions run side by side inside the pads at
pitch - widths/2 (0.4 - 0.075 - 0.1 = 0.225 mm). The DRC rule excepts pads, not the tracks on them.
For every track named in a clearance error: an end that lies inside a pad of its own net and that no other track or via
shares is moved along the track, towards its other end, as far as it stays inside the pad by --margin mm (the stub
still starts on the pad, so the connection is kept). Then the zones are refilled. finish.sh runs DRC again after it.
Prints 'trimmed <n> stub ends (<m> errors looked at)'."""
import sys, json
import pcbnew

A = [a for a in sys.argv[1:] if not a.startswith("--")]
O = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
pin, drc, pout = A[:3]
MARGIN = pcbnew.FromMM(float(O.get("margin", 0.03)))
b = pcbnew.LoadBoard(pin)
dj = json.load(open(drc))
errs = [v for v in dj["violations"] if v["severity"] == "error" and v["type"] == "clearance"]
want = {i["uuid"] for v in errs for i in v["items"]}
tracks = {t.m_Uuid.AsString(): t for t in b.GetTracks()}
pads = list(b.GetPads())


def ends_at(net, pt, me):
    """another track / via of the net that touches pt"""
    mu = me.m_Uuid.AsString()
    for t in b.GetTracks():
        if t.m_Uuid.AsString() == mu or t.GetNetCode() != net:
            continue
        if t.GetClass() == "PCB_VIA":
            if (t.GetPosition() - pt).EuclideanNorm() <= t.GetWidth(pcbnew.F_Cu) // 2:
                return True
        elif (t.GetStart() - pt).EuclideanNorm() < 1000 or (t.GetEnd() - pt).EuclideanNorm() < 1000:
            return True
    return False


def inside(pad, layer, pt, margin):
    poly = pad.GetEffectivePolygon(layer, pcbnew.ERROR_INSIDE)
    if not poly.Contains(pt):
        return False
    # margin: the four points around pt must be inside as well
    return all(poly.Contains(pt + pcbnew.VECTOR2I(dx, dy)) for dx, dy in ((margin, 0), (-margin, 0), (0, margin), (0, -margin)))


n = 0
for u in want:
    t = tracks.get(u)
    if t is None or t.GetClass() != "PCB_TRACK":
        continue
    L, net = t.GetLayer(), t.GetNetCode()
    for which in ("start", "end"):
        p = pcbnew.VECTOR2I(t.GetStart() if which == "start" else t.GetEnd())
        q = pcbnew.VECTOR2I(t.GetEnd() if which == "start" else t.GetStart())
        pd = [x for x in pads if x.GetNetCode() == net and x.IsOnLayer(L) and inside(x, L, p, 0)]
        if not pd or ends_at(net, p, t):
            continue
        pad = pd[0]
        d = q - p
        ln = d.EuclideanNorm()
        if ln == 0:
            continue
        lo, hi = 0.0, 1.0            # largest fraction f of the track such that p + f*d stays inside the pad by MARGIN
        if inside(pad, L, q, MARGIN):
            continue                 # the whole track lies on the pad: leave it
        for _ in range(30):
            m = (lo + hi) / 2
            pt = pcbnew.VECTOR2I(int(p.x + d.x * m), int(p.y + d.y * m))
            if inside(pad, L, pt, MARGIN):
                lo = m
            else:
                hi = m
        if lo * ln < pcbnew.FromMM(0.02):
            continue
        np_ = pcbnew.VECTOR2I(int(p.x + d.x * lo), int(p.y + d.y * lo))
        (t.SetStart if which == "start" else t.SetEnd)(np_)
        n += 1
        print("  %s %s %s %.3f,%.3f -> %.3f,%.3f (pad %s.%s)" % (t.GetNetname(), b.GetLayerName(L), which, pcbnew.ToMM(p.x), pcbnew.ToMM(p.y),
              pcbnew.ToMM(np_.x), pcbnew.ToMM(np_.y), pad.GetParentFootprint().GetReference(), pad.GetNumber()))
b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.BuildConnectivity()
b.Save(pout)
print("trimmed %d stub ends (%d errors looked at)" % (n, len(errs)))
