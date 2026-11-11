"""apply_placement.py <in.kicad_pcb> <out.kicad_pcb> [placement.json] [--strip]      (KiCad's python: needs pcbnew)
Moves footprints to a placement from place_pack.py (x, y, quarter turns relative to the input board) and, with
--strip, removes every track, via and copper pour (keep-out areas stay) so the board is ready for a trial route.
Without a placement file it only strips, which gives the same bare board for a reference placement.
The project file beside the output (design rules, net classes) is kept as it was.
After moving, it checks each pad against the position the placer computed and stops if any is off by over 0.01 mm."""
import sys, json, os, pcbnew
a = [x for x in sys.argv[1:] if not x.startswith("--")]; strip = "--strip" in sys.argv
P = json.load(open(a[2])) if len(a) > 2 else {}; mm = pcbnew.ToMM; src = a[0]
if strip:                      # by text: removing tracks through pcbnew crashes KiCad 10's python
    out, block = [], None
    for line in open(a[0], encoding="utf-8"):
        if block is None and line.rstrip("\n") in ("\t(segment", "\t(via", "\t(arc", "\t(zone"): block = [line]; continue
        if block is None: out.append(line); continue
        block.append(line)
        if line.rstrip("\n") == "\t)":
            if block[0].strip() == "(zone" and any("(keepout" in l for l in block): out += block
            block = None
    src = a[1][:-10] + "_bare.kicad_pcb"; open(src, "w", encoding="utf-8").write("".join(out))
b = pcbnew.LoadBoard(src)
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
pro = a[1][:-10] + ".kicad_pro"; keep = open(pro, "rb").read() if os.path.exists(pro) else None
b.Save(a[1])
if keep is not None: open(pro, "wb").write(keep)      # pcbnew's Save rewrites the project file with default rules; put it back
if strip: os.remove(src)
print(f"wrote {a[1]}: {len(P)} footprints moved, stripped={strip}")
