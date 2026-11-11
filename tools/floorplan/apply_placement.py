"""apply_placement.py <in.kicad_pcb> <out.kicad_pcb> [placement.json] [--strip]      (KiCad's python: needs pcbnew)
Moves footprints to a placement from place_pack.py (x, y, quarter turns relative to the input board) and, with
--strip, removes every track, via and copper pour (keep-out areas stay) so the board is ready for a trial route.
Without a placement file it only strips, which gives the same bare board for a reference placement.
After moving, it checks each pad against the position the placer computed and stops if any is off by over 0.01 mm."""
import sys, json, pcbnew
a = [x for x in sys.argv[1:] if not x.startswith("--")]; strip = "--strip" in sys.argv
b = pcbnew.LoadBoard(a[0]); mm = pcbnew.ToMM; P = json.load(open(a[2])) if len(a) > 2 else {}
if strip:
    for t in list(b.GetTracks()): b.Remove(t)
    for z in list(b.Zones()):
        if not z.GetIsRuleArea(): b.Remove(z)
bad = 0
for f in b.GetFootprints():
    r = f.GetReference()
    if r not in P: continue
    x, y, ang = P[r]; q = int(ang) // 90 % 4; p0 = f.GetPosition()
    want = {}
    for pad in f.Pads():
        lx, ly = mm(pad.GetPosition().x - p0.x), mm(pad.GetPosition().y - p0.y)
        for _ in range(q): lx, ly = -ly, lx
        want.setdefault(pad.GetNumber(), []).append((x + lx, y + ly))
    f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
    if q:
        f.SetOrientationDegrees(f.GetOrientationDegrees() - 90 * q)
        ok = lambda: all(min(abs(mm(pad.GetPosition().x) - wx) + abs(mm(pad.GetPosition().y) - wy) for wx, wy in want[pad.GetNumber()]) < 0.01 for pad in f.Pads())
        if not ok():
            f.SetOrientationDegrees(f.GetOrientationDegrees() + 180 * q)
            if not ok(): bad += 1; print("pad mismatch", r)
if bad: sys.exit(f"{bad} footprints did not land where the placer put them")
b.Save(a[1]); print(f"wrote {a[1]}: {len(P)} footprints moved, stripped={strip}")
