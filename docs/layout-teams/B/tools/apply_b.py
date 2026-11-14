"""apply_b.py <template.kicad_pcb> <out.kicad_pcb> <placement.json> [--partial] [--expect=pads.json]   (KiCad python)
Team B's placement applier: moves, turns and flips footprints of the template to a placement
{ref: [x, y, turn] or [x, y, turn, side]} (turn relative to the template, apply_placement.py convention; a side that
differs from the template side flips the part: local x mirrored first, then turned, as blib.py computes).

How the flip is done in KiCad 10: FOOTPRINT.Flip(position, FLIP_DIRECTION_LEFT_RIGHT), then each of the four
orientations is tried and the one where every pad lands where the formula says is kept (the same search is used for
parts that only turn). Any pad off by more than 0.01 mm stops the run (exit 1).

--partial      footprints that are neither fixed (J, H, TP, SW prefixes and the cup-fixed list) nor in the placement
               are removed from the file text by reference before loading (removing through pcbnew has crashed).
--expect=FILE  pad positions computed by blib.py (python3 blib.py pads placement.json [--partial]); every pad of every
               footprint left on the board is checked against it too, so KiCad and the team placer agree.
Keep-outs that forbid pours but not parts and sit on every copper layer inside one part's courtyard move with that
part (as apply_placement.py). The .kicad_pro and .kicad_dru beside the output are put back after Save."""
import sys, json, os, re

FIXED_EXTRA = {"U301", "L401", "L501", "TH101", "TH104", "TH401", "TH501", "C208", "C209", "C210", "C211", "C212", "C213", "C421", "C456", "C521", "C556"}
def is_fixed(r): return re.match(r"[A-Z]+", r).group() in ("J", "H", "TP", "SW") or r in FIXED_EXTRA
def rot(x, y, q):
    for _ in range(q % 4): x, y = -y, x
    return x, y

def strip_footprints(text, keep):
    """remove (footprint ...) blocks whose reference is not kept; returns (text, removed refs)"""
    out, block, removed = [], None, []
    for line in text.splitlines(keepends=True):
        if block is None:
            if line.startswith("\t(footprint "): block = [line]; continue
            out.append(line); continue
        block.append(line)
        if line.rstrip("\n") == "\t)":
            m = re.search(r'\(property "Reference" "([^"]+)"', "".join(block[:40])) or re.search(r'\(property "Reference" "([^"]+)"', "".join(block))
            ref = m.group(1) if m else None
            if ref is None or ref in keep: out += block
            else: removed.append(ref)
            block = None
    if block: out += block
    return "".join(out), removed

def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]; opt = dict((x[2:].split("=", 1) + [""])[:2] for x in sys.argv[1:] if x.startswith("--"))
    src, dst, plf = a[0], a[1], a[2]
    P = {r: v for r, v in json.load(open(plf)).items() if not r.startswith("_")}
    exp = json.load(open(opt["expect"])) if opt.get("expect") else None
    base = dst[:-10]; keepf = {}
    for e in ("kicad_pro", "kicad_dru"):
        for cand in (base + "." + e, src[:-10] + "." + e):
            if os.path.exists(cand): keepf[e] = open(cand, "rb").read(); break
    text = open(src, encoding="utf-8").read(); removed = []
    if "partial" in opt:
        refs = set(re.findall(r'\(property "Reference" "([^"]+)"', text))
        keep = {r for r in refs if is_fixed(r) or r in P}
        text, removed = strip_footprints(text, keep)
    tmp = base + "_in.kicad_pcb"; open(tmp, "w", encoding="utf-8").write(text)
    import pcbnew
    mm = pcbnew.ToMM; b = pcbnew.LoadBoard(tmp); os.remove(tmp)
    ncu = b.GetCopperLayerCount(); own = {}
    for z in b.Zones():
        if not z.GetIsRuleArea() or z.GetDoNotAllowFootprints() or not z.GetDoNotAllowZoneFills(): continue
        if len([l for l in z.GetLayerSet().Seq() if pcbnew.IsCopperLayer(l)]) < ncu: continue
        c = z.GetBoundingBox().Centre(); inside = [(f.GetBoundingBox(False).GetArea(), f) for f in b.GetFootprints() if f.GetBoundingBox(False).Contains(c)]
        if inside: own.setdefault(min(inside, key=lambda t: t[0])[1].GetReference(), []).append(z)
    bad = []; flipped = []; moved = 0; fps = {f.GetReference(): f for f in b.GetFootprints()}
    missing = [r for r in P if r not in fps]
    if missing: sys.exit(f"placement refs not on the board: {missing}")
    for r, v in P.items():
        f = fps[r]; x, y = float(v[0]), float(v[1]); q = int(round(float(v[2]))) // 90 % 4
        cur = "B" if f.GetLayer() == pcbnew.B_Cu else "F"
        side = (str(v[3])[:1] if len(v) > 3 and v[3] else cur); flip = side != cur
        p0 = f.GetPosition(); want = {}
        for pad in f.Pads():
            lx, ly = mm(pad.GetPosition().x - p0.x), mm(pad.GetPosition().y - p0.y)
            if flip: lx = -lx
            lx, ly = rot(lx, ly, q); want.setdefault(pad.GetNumber(), []).append((x + lx, y + ly))
        zl = []
        for z in own.get(r, []):
            o = z.Outline(); pts = []
            for i in range(o.TotalVertices()):
                vv = o.CVertex(i); lx, ly = mm(vv.x - p0.x), mm(vv.y - p0.y)
                if flip: lx = -lx
                lx, ly = rot(lx, ly, q); pts.append((x + lx, y + ly))
            zl.append((z, pts))
        f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
        if flip: f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT); flipped.append(r)
        ok = lambda: all(min(abs(mm(pad.GetPosition().x) - wx) + abs(mm(pad.GetPosition().y) - wy) for wx, wy in want[pad.GetNumber()]) < 0.01 for pad in f.Pads())
        o0 = f.GetOrientationDegrees(); hit = False
        for k in (0, -1, 1, 2, -2, 3, -3):
            f.SetOrientationDegrees(o0 + 90 * k)
            if ok(): hit = True; break
        if not hit: bad.append(r); print("pad mismatch", r, flush=True)
        if flip and (f.GetLayer() == pcbnew.B_Cu) != (side == "B"): bad.append(r); print("side wrong after flip", r)
        for z, pts in zl:
            o = z.Outline()
            for i, (px, py) in enumerate(pts): o.SetVertex(i, pcbnew.VECTOR2I(pcbnew.FromMM(px), pcbnew.FromMM(py)))
            z.UnHatchBorder(); z.HatchBorder()
        moved += 1
    nexp = 0
    if exp is not None:
        for f in b.GetFootprints():
            r = f.GetReference(); e = exp.get(r)
            if e is None: bad.append(r); print("not in the expected pads", r); continue
            for pad in f.Pads():
                if not pad.IsOnCopperLayer(): continue        # paste-only apertures (blib drops them too)
                pts = e.get(pad.GetNumber())
                if not pts or min(abs(mm(pad.GetPosition().x) - wx) + abs(mm(pad.GetPosition().y) - wy) for wx, wy in pts) >= 0.01:
                    bad.append(r); print("pad differs from blib", r, pad.GetNumber(), mm(pad.GetPosition().x), mm(pad.GetPosition().y), pts); break
                nexp += 1
    if bad: sys.exit(f"{len(set(bad))} footprints did not land where the placer put them: {sorted(set(bad))}")
    b.Save(dst)
    for e, data in keepf.items(): open(base + "." + e, "wb").write(data)
    print(f"wrote {dst}: {moved} footprints placed, flipped {len(flipped)} {flipped[:20]}, removed {len(removed)} (partial), "
          f"footprints on board {len(list(b.GetFootprints()))}, pads checked against blib {nexp}, keep-outs moved with their part: "
          f"{sum(len(v) for k, v in own.items() if k in P)}")

if __name__ == "__main__":
    main()
