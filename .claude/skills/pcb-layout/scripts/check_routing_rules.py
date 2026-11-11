"""Check a KiCad board against the routing discipline in references/routing-discipline.md.

    python check_routing_rules.py board.kicad_pcb [--vertical In2.Cu] [--horizontal In3.Cu]
        [--planes In1.Cu,In4.Cu] [--outer-max 15] [--ref-via 1.0] [--fanout 1.5] [--web 0.3]
        [--allow-classes Power,GateDrive,Kelvin] [--allow-nets REGEX] [--ic-prefix U] [--dense-pins 20] [--small-ring 1.0]
        [--pin-net-max 5] [--pin-support] [--max-list 15]

Checks, each printed as a section with a count and the first few offenders (mm, relative to the outline's top-left):
  1. direction    - segments on the vertical layer that aren't vertical, on the horizontal layer that aren't
                    horizontal; arcs on either.
  2. planes       - tracks on a plane layer; zones on a plane layer whose net isn't GND; rows of non-GND vias
                    whose plane antipads leave less than --web of copper between them (a slot), 3+ in a chain.
                    Antipad = hole radius + hole clearance for vias with unconnected inner rings removed, else pad
                    radius + zone clearance.
  3. outer runs   - ADVISORY (length is a goal, not a rule): signal runs on F.Cu/B.Cu longer than --outer-max (power,
                    gate-drive, Kelvin classes and GND are exempt; extend with --allow-classes / --allow-nets).
  4. ref vias     - signal vias that change reference plane (their net leaves on F/--vertical and on
                    --horizontal/B) with no GND via or GND through-hole pad within --ref-via. Vias inside a same-net
                    pour, or on an --allow-classes net, are pour stitching and exempt.
  5. fan-out room - ICs (refs starting with --ic-prefix, default U) with more than --dense-pins pins (default 20)
                    need --fanout (1.5 mm) clear round the courtyard; other ICs with pitch < 0.8 mm need --small-ring
                    (1 mm). Exempt: decoupling only (a cap from one of the IC's nets to GND or to the net of the IC's exposed
                    pad, e.g. a gauge's VSS). Bootstrap,
                    sense-filter and FB parts are not exempt: parked against the pins they block the escapes (the
                    user's rule). --pin-support exempts them anyway (parts on a pin-local net with <= --pin-net-max
                    pads, reached from an IC pin directly or through one other part).
Exit code 0 always; read the counts. Run with KiCad's bundled python (needs pcbnew).
"""
import collections
import math
import re
import sys

import pcbnew

argv = sys.argv[1:]


def opt(name, default):
    if name in argv:
        i = argv.index(name)
        v = argv[i + 1]
        del argv[i:i + 2]
        return v
    return default


VERT = opt("--vertical", "In2.Cu")
HORZ = opt("--horizontal", "In3.Cu")
PLANES = opt("--planes", "In1.Cu,In4.Cu").split(",")
OUTER_MAX = float(opt("--outer-max", "15"))
REF_VIA = float(opt("--ref-via", "1.0"))
FANOUT = float(opt("--fanout", "1.5"))
WEB = float(opt("--web", "0.3"))
ALLOW_CLASSES = set(opt("--allow-classes", "Power,HighCurrent,Pack,GateDrive,Kelvin,SW").split(","))
ALLOW_NETS = re.compile(opt("--allow-nets", r"^$"), re.I)
MAX_LIST = int(opt("--max-list", "15"))
IC_PREFIX = tuple(opt("--ic-prefix", "U").split(","))
DENSE_PINS = int(opt("--dense-pins", "20"))
SMALL_RING = float(opt("--small-ring", "1.0"))
PIN_NET_MAX = int(opt("--pin-net-max", "5"))
PIN_SUPPORT = "--pin-support" in argv           # off by default: only decoupling may sit inside the ring
if PIN_SUPPORT:
    argv.remove("--pin-support")
TOL = 0.001  # mm

board = pcbnew.LoadBoard(argv[0])
bb = board.GetBoardEdgesBoundingBox()
OX, OY = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
lid = {board.GetStandardLayerName(l): l for l in board.GetEnabledLayers().CuStack()}
for name in [VERT, HORZ] + PLANES:
    if name not in lid:
        sys.exit(f"layer {name} not on this board (copper layers: {', '.join(lid)})")
V, H, P = lid[VERT], lid[HORZ], {lid[n] for n in PLANES}
mm = pcbnew.ToMM


def xy(p):
    return (round(mm(p.x) - OX, 2), round(mm(p.y) - OY, 2))


def is_gnd(net):
    return net == "GND" or net.endswith("/GND")


def report(title, items, fmt):
    print(f"\n== {title}: {len(items)}")
    for it in items[:MAX_LIST]:
        print("   " + fmt(it))
    if len(items) > MAX_LIST:
        print(f"   ... {len(items) - MAX_LIST} more")


tracks = list(board.GetTracks())
vias = [t for t in tracks if t.GetClass() == "PCB_VIA"]
segs = [t for t in tracks if t.GetClass() in ("PCB_TRACK", "PCB_ARC")]

# 1. direction
bad_dir = []
for t in segs:
    L = t.GetLayer()
    if L not in (V, H):
        continue
    s, e = t.GetStart(), t.GetEnd()
    dx, dy = abs(mm(e.x - s.x)), abs(mm(e.y - s.y))
    if t.GetClass() == "PCB_ARC":
        bad_dir.append((t, "arc"))
    elif L == V and dx > TOL:
        bad_dir.append((t, "not vertical"))
    elif L == H and dy > TOL:
        bad_dir.append((t, "not horizontal"))
report(f"direction ({VERT} vertical, {HORZ} horizontal)", bad_dir,
       lambda it: f"{board.GetStandardLayerName(it[0].GetLayer())} {it[0].GetNetname()} {xy(it[0].GetStart())}->"
                  f"{xy(it[0].GetEnd())} {it[1]}")

# 2. planes
on_plane = [t for t in segs if t.GetLayer() in P]
report("tracks on plane layers", on_plane,
       lambda t: f"{board.GetStandardLayerName(t.GetLayer())} {t.GetNetname()} {xy(t.GetStart())}->{xy(t.GetEnd())}")
bad_zones = [(z, board.GetStandardLayerName(L)) for z in board.Zones() if not z.GetIsRuleArea()
             for L in P if z.IsOnLayer(L) and not is_gnd(z.GetNetname())]
report("non-GND zones on plane layers", bad_zones,
       lambda it: f"{it[1]} net '{it[0].GetNetname()}' bbox {xy(it[0].GetBoundingBox().GetOrigin())}"
                  f"-{xy(it[0].GetBoundingBox().GetEnd())}")
# antipad rows: approximate each non-GND via's plane antipad as pad radius + zone clearance
zclr = max([mm(z.GetLocalClearance() or 0) for z in board.Zones() if not z.GetIsRuleArea()
            and any(z.IsOnLayer(L) for L in P)] + [0.2])
hole_clr = mm(board.GetDesignSettings().m_HoleClearance)


def antipad(v):
    """Plane antipad radius: from the pad when the via keeps its inner rings, else from the hole."""
    if v.GetRemoveUnconnected():
        return mm(v.GetDrillValue()) / 2 + max(zclr, hole_clr)
    return mm(v.GetWidth(pcbnew.F_Cu)) / 2 + zclr


ap = [(v, antipad(v)) for v in vias if not is_gnd(v.GetNetname())]
parent = list(range(len(ap)))


def find(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


grid = collections.defaultdict(list)
for i, (v, r) in enumerate(ap):
    p = v.GetPosition()
    grid[(int(mm(p.x) // 2), int(mm(p.y) // 2))].append(i)
for i, (v, r) in enumerate(ap):
    p = v.GetPosition()
    gx, gy = int(mm(p.x) // 2), int(mm(p.y) // 2)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for j in grid[(gx + dx, gy + dy)]:
                if j <= i:
                    continue
                q, rj = ap[j][0].GetPosition(), ap[j][1]
                if math.hypot(mm(p.x - q.x), mm(p.y - q.y)) - r - rj < WEB:
                    parent[find(i)] = find(j)
chains = collections.defaultdict(list)
for i in range(len(ap)):
    chains[find(i)].append(ap[i][0])
slots = [c for c in chains.values() if len(c) >= 3]
report(f"via rows slotting the planes (antipad web < {WEB} mm, 3+ vias)", slots,
       lambda c: f"{len(c)} vias, nets {sorted({v.GetNetname() for v in c})[:3]}, from {xy(c[0].GetPosition())}")

# 3. outer runs
def exempt(net):
    if not net or is_gnd(net) or ALLOW_NETS.search(net):
        return True
    ni = board.FindNet(net)
    return ni is not None and ni.GetNetClassName() in ALLOW_CLASSES


runs = []
for L in (pcbnew.F_Cu, pcbnew.B_Cu):
    by_net = collections.defaultdict(list)
    for t in segs:
        if t.GetLayer() == L and not exempt(t.GetNetname()):
            by_net[t.GetNetname()].append(t)
    for net, ts in by_net.items():
        idx = {}
        par = list(range(len(ts)))

        def f(i):
            while par[i] != i:
                par[i] = par[par[i]]
                i = par[i]
            return i

        for i, t in enumerate(ts):
            for p in (t.GetStart(), t.GetEnd()):
                k = (p.x // 1000, p.y // 1000)
                if k in idx:
                    par[f(i)] = f(idx[k])
                else:
                    idx[k] = i
        tot = collections.Counter()
        for i, t in enumerate(ts):
            tot[f(i)] += mm(t.GetLength())
        for root, length in tot.items():
            if length > OUTER_MAX:
                runs.append((net, board.GetStandardLayerName(L), length, ts[root]))
runs.sort(key=lambda r: -r[2])
report(f"advisory: long signal runs on outer layers (> {OUTER_MAX} mm)", runs,
       lambda r: f"{r[1]} {r[0]} {r[2]:.1f} mm near {xy(r[3].GetStart())}")

# 4. reference vias
gnd_pts = [v.GetPosition() for v in vias if is_gnd(v.GetNetname())]
gnd_pts += [p.GetPosition() for fp in board.GetFootprints() for p in fp.Pads()
            if p.HasHole() and is_gnd(p.GetNetname())]
gg = collections.defaultdict(list)
for q in gnd_pts:
    gg[(int(mm(q.x) // 2), int(mm(q.y) // 2))].append(q)
def pour_stitch(v):
    """A via inside a same-net copper zone (pour stitching, DC current) is not a signal changing reference."""
    if v.GetNetname() and board.FindNet(v.GetNetname()).GetNetClassName() in ALLOW_CLASSES:
        return True
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetCode() != v.GetNetCode():
            continue
        for L in (pcbnew.F_Cu, pcbnew.B_Cu):
            if z.IsOnLayer(L) and z.HasFilledPolysForLayer(L) and z.GetFilledPolysList(L).Contains(v.GetPosition()):
                return True
    return False


# a via changes reference plane when its net leaves it on both sides of the stack: F/<vertical layer> reference the
# upper plane, <horizontal layer>/B the lower one (6-layer default). SMD pads at the via count as their layer.
UPPER = {pcbnew.F_Cu, V}
LOWER = {H, pcbnew.B_Cu}
ends = collections.defaultdict(set)
for t in segs:
    for p in (t.GetStart(), t.GetEnd()):
        ends[(t.GetNetCode(), p.x // 2000, p.y // 2000)].add(t.GetLayer())
smd = [(p, p.GetNetCode()) for f in board.GetFootprints() for p in f.Pads() if not p.HasHole()]


def via_layers(v):
    q = v.GetPosition()
    out = set()
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            out |= ends.get((v.GetNetCode(), q.x // 2000 + dx, q.y // 2000 + dy), set())
    for p, nc in smd:
        if nc == v.GetNetCode() and p.HitTest(q):
            out.add(p.GetLayer())
    return out


def changes_reference(v):
    L = via_layers(v)
    return bool(L & UPPER) and bool(L & LOWER)


lonely = []
for v in vias:
    if is_gnd(v.GetNetname()) or pour_stitch(v) or not changes_reference(v):
        continue
    p = v.GetPosition()
    gx, gy = int(mm(p.x) // 2), int(mm(p.y) // 2)
    near = any(math.hypot(mm(p.x - q.x), mm(p.y - q.y)) <= REF_VIA
               for dx in (-1, 0, 1) for dy in (-1, 0, 1) for q in gg[(gx + dx, gy + dy)])
    if not near:
        lonely.append(v)
report(f"signal vias without a GND via within {REF_VIA} mm", lonely,
       lambda v: f"{v.GetNetname()} at {xy(v.GetPosition())}")

# 5. fan-out room
def courtyard_box(fp):
    c = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd)
    return c.BBox() if c.OutlineCount() else fp.GetBoundingBox(False)


def pitch_of(fp):
    """Smallest centre distance between pads with different pin numbers (thermal-via pads share a number)."""
    pads = [p for p in fp.Pads() if p.GetNumber()]
    pts = [(p.GetNumber(), mm(p.GetPosition().x), mm(p.GetPosition().y)) for p in pads]
    return min((math.hypot(a[1] - b[1], a[2] - b[2]) for i, a in enumerate(pts) for b in pts[i + 1:]
                if a[0] != b[0]), default=99)


def ring_for(fp):
    """Clear ring (mm) this IC needs: FANOUT for > DENSE_PINS pins, SMALL_RING for other fine-pitch parts."""
    pads = [p for p in fp.Pads() if p.GetNumber()]
    areas = sorted(p.GetSizeX() * p.GetSizeY() for p in pads)
    med = areas[len(areas) // 2] if areas else 0
    # pins = numbered pads that aren't an exposed/thermal pad (much larger than the typical pad)
    big = {p.GetNumber() for p in pads if p.GetSizeX() * p.GetSizeY() > 4 * med}
    nums = {p.GetNumber() for p in pads} - big
    if len(nums) > DENSE_PINS:
        return FANOUT
    if len(nums) >= 6 and pitch_of(fp) < 0.8:
        return SMALL_RING
    return None


net_pads = collections.Counter(p.GetNetname() for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetname())
fps = list(board.GetFootprints())
crowd = []
for ic in fps:
    if not ic.GetReference().startswith(IC_PREFIX) or ic.IsDNP():
        continue
    ring = ring_for(ic)
    if ring is None or ring <= 0:
        continue
    box = courtyard_box(ic)
    zone = pcbnew.BOX2I(box.GetOrigin(), box.GetSize())
    zone.Inflate(pcbnew.FromMM(ring))
    ic_nets = {p.GetNetname() for p in ic.Pads() if p.GetNetname()}
    # the IC's ground: GND, or whatever net its exposed pad is on (a gauge's VSS on cell minus, say)
    _pads = [p for p in ic.Pads() if p.GetNumber()]
    _areas = sorted(p.GetSizeX() * p.GetSizeY() for p in _pads)
    _med = _areas[len(_areas) // 2] if _areas else 0
    _big = max(_pads, key=lambda p: p.GetSizeX() * p.GetSizeY()) if _pads else None
    ic_gnd = {_big.GetNetname()} if _big and _big.GetSizeX() * _big.GetSizeY() > 4 * _med and _big.GetNetname() else set()

    def is_ref(n):
        return is_gnd(n) or n in ic_gnd

    def local(n):
        return n and net_pads[n] <= PIN_NET_MAX and not is_gnd(n)

    # pin-local nets: on an IC pin, or one part away from one
    attached = {n for n in ic_nets if local(n)}
    for f in fps:
        fn = {p.GetNetname() for p in f.Pads()}
        if f is not ic and fn & attached:
            attached |= {n for n in fn if local(n)}
    for o in fps:
        if o is ic or o.IsFlipped() != ic.IsFlipped():
            continue
        ob = courtyard_box(o)
        if not zone.Intersects(ob):
            continue
        onets = {p.GetNetname() for p in o.Pads()}
        shared = onets & ic_nets
        decoup = o.GetReference().startswith("C") and bool(shared - ic_gnd - {"GND"}) and any(is_ref(n) for n in onets)
        # pin support: a part on one of the IC's pin-local nets (bootstrap, sense filter, FB divider...)
        pin_support = PIN_SUPPORT and bool(onets & attached)
        if not (decoup or pin_support):
            gap = max(mm(max(box.GetLeft() - ob.GetRight(), ob.GetLeft() - box.GetRight(), 0)),
                      mm(max(box.GetTop() - ob.GetBottom(), ob.GetTop() - box.GetBottom(), 0)))
            crowd.append((ic.GetReference(), o.GetReference(), gap, ring))
crowd.sort(key=lambda c: (c[0], c[2]))
report(f"parts inside the fan-out ring of dense ICs ({FANOUT} mm for >{DENSE_PINS} pins, {SMALL_RING} mm for "
       f"smaller fine-pitch ICs)", crowd, lambda c: f"{c[0]} (ring {c[3]} mm): {c[1]} at {c[2]:.2f} mm")

print("\nsummary: direction %d, plane tracks %d, plane zones %d, plane slots %d, outer runs (advisory) %d, ref vias %d, "
      "fan-out %d" % (len(bad_dir), len(on_plane), len(bad_zones), len(slots), len(runs), len(lonely), len(crowd)))
