"""Silkscreen tidy for the ground-up layout (run with KiCad's python): silk.py in.kicad_pcb out.kicad_pcb
  - every visible reference designator is moved to the first spot beside its part where it covers no pad, hole,
    other text or board edge (1.0 mm text, as on the current board); if there is none it is hidden;
  - the WAKE label follows the pad on the WAKE net; the title block moves to free board area;
  - footprint silkscreen graphics are left alone."""
import sys, math
import pcbnew
mm, MM = pcbnew.FromMM, pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1])
outline = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(outline, False)
inside = pcbnew.SHAPE_POLY_SET(outline); inside.Deflate(mm(0.35), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.01))
def box(bb, g=0.0): return (MM(bb.GetLeft()) - g, MM(bb.GetTop()) - g, MM(bb.GetRight()) + g, MM(bb.GetBottom()) + g)
def hit(a, c): return a[0] < c[2] and c[0] < a[2] and a[1] < c[3] and c[1] < a[3]
def in_board(r):
    return all(inside.Contains(pcbnew.VECTOR2I(mm(x), mm(y))) for x in (r[0], (r[0] + r[2]) / 2, r[2]) for y in (r[1], (r[1] + r[3]) / 2, r[3]))
PADS = {True: [], False: []}        # front?: pad boxes (+0.12)
COURT = {True: [], False: []}
for f in b.GetFootprints():
    fr = f.GetLayer() == pcbnew.F_Cu
    cy = f.GetCourtyard(pcbnew.F_CrtYd if fr else pcbnew.B_CrtYd)
    if cy.OutlineCount(): COURT[fr].append((f.GetReference(), box(cy.BBox())))
    for p in f.Pads():
        r = box(p.GetBoundingBox(), 0.12)
        if p.HasHole() or p.IsOnLayer(pcbnew.F_Cu): PADS[True].append(r)
        if p.HasHole() or p.IsOnLayer(pcbnew.B_Cu): PADS[False].append(r)
TEXTS = {True: [], False: []}       # placed text boxes
fixed = []
for d in b.GetDrawings():
    if d.GetClass() == 'PCB_TEXT' and 'Silk' in d.GetLayerName():
        fixed.append(d)
for f in b.GetFootprints():                 # labels drawn inside footprints (wire-pad names) are handled like board texts
    for g in f.GraphicalItems():
        if g.GetClass() == 'PCB_TEXT' and 'Silk' in g.GetLayerName() and g.IsVisible():
            fixed.append(g)
def free(r, fr, own=None, courts=False):
    if not in_board(r): return False
    if any(hit(r, p) for p in PADS[fr]) or any(hit(r, t) for t in TEXTS[fr]): return False
    if courts and any(hit(r, c) for ref, c in COURT[fr] if ref != own): return False
    return True
# --- board texts: the wire-pad labels stay; WAKE and the title are re-homed
wake = next((p for f in b.GetFootprints() for p in f.Pads() if p.GetNetname().endswith('/WAKE') and f.GetReference().startswith(('TP', 'J'))), None)
for d in fixed:
    fr = d.GetLayerName().startswith('F')
    t = d.GetText()
    if not t.startswith('Monolith'):
        # labels stay where they are when that spot is still clear; otherwise the nearest clear spot (WAKE: nearest to its pad)
        c = wake.GetPosition() if (t == 'WAKE' and wake is not None) else d.GetPosition()
        a0 = d.GetTextAngle().AsDegrees()
        if t == 'WAKE' or not free(box(d.GetBoundingBox(), 0.05), fr, courts=False):
            best = None
            for ang in (a0, 90.0 if abs(a0) < 1 else 0.0):
                d.SetTextAngle(pcbnew.EDA_ANGLE(ang, pcbnew.DEGREES_T))
                for i in range(-20, 21):
                    for j in range(-20, 21):
                        dx, dy = i * 0.25, j * 0.25
                        r2 = dx * dx + dy * dy + (0.0 if ang == a0 else 4.0)
                        if best is not None and r2 >= best[0]: continue
                        d.SetPosition(pcbnew.VECTOR2I(c.x + mm(dx), c.y + mm(dy)))
                        if free(box(d.GetBoundingBox(), 0.08), fr, courts=False): best = (r2, dx, dy, ang)
            if best:
                d.SetTextAngle(pcbnew.EDA_ANGLE(best[3], pcbnew.DEGREES_T)); d.SetPosition(pcbnew.VECTOR2I(c.x + mm(best[1]), c.y + mm(best[2])))
            else:
                d.SetTextAngle(pcbnew.EDA_ANGLE(a0, pcbnew.DEGREES_T)); d.SetPosition(c)
            print('label', t, 'moved %.2f mm' % (best[0] ** 0.5) if best else 'NOT placed')
    elif t.startswith('Monolith'):
        best = None
        for ang in (90, 0):
            d.SetTextAngle(pcbnew.EDA_ANGLE(ang, pcbnew.DEGREES_T))
            for yy in [y / 2 for y in range(2 * 64, 2 * 137)]:
                for xx in [x / 2 for x in range(2 * 79, 2 * 122)]:
                    d.SetPosition(pcbnew.VECTOR2I(mm(xx), mm(yy)))
                    r = box(d.GetBoundingBox(), 0.2)
                    if free(r, fr, courts=True):
                        best = (xx, yy, ang); break
                if best: break
            if best: break
        if best:
            d.SetTextAngle(pcbnew.EDA_ANGLE(best[2], pcbnew.DEGREES_T)); d.SetPosition(pcbnew.VECTOR2I(mm(best[0]), mm(best[1])))
        print('title', best)
    TEXTS[fr].append(box(d.GetBoundingBox(), 0.1))
# --- reference designators
moved = hidden = 0
for f in sorted(b.GetFootprints(), key=lambda f: f.GetReference()):
    ref = f.Reference()
    if not ref.IsVisible(): continue
    fr = f.GetLayer() == pcbnew.F_Cu
    cy = f.GetCourtyard(pcbnew.F_CrtYd if fr else pcbnew.B_CrtYd)
    cb = box(cy.BBox()) if cy.OutlineCount() else box(f.GetBoundingBox(False))
    cx, cyy = (cb[0] + cb[2]) / 2, (cb[1] + cb[3]) / 2
    ref.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER); ref.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    placed = False
    for size, courts in ((1.0, True), (0.8, True), (0.8, False)):
        ref.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size))); ref.SetTextThickness(mm(0.15))
        for ang in (0, 90):
            ref.SetTextAngle(pcbnew.EDA_ANGLE(ang, pcbnew.DEGREES_T)); ref.SetPosition(pcbnew.VECTOR2I(mm(cx), mm(cyy)))
            tb = box(ref.GetBoundingBox()); tw, th = (tb[2] - tb[0]) / 2, (tb[3] - tb[1]) / 2
            cands = []
            for ex in (0.15, 0.6, 1.1, 1.8, 2.6, 3.5, 4.5):
                cands += [(cx, cb[1] - th - ex), (cx, cb[3] + th + ex), (cb[0] - tw - ex, cyy), (cb[2] + tw + ex, cyy),
                          (cb[0] + tw, cb[1] - th - ex), (cb[2] - tw, cb[1] - th - ex), (cb[0] + tw, cb[3] + th + ex), (cb[2] - tw, cb[3] + th + ex),
                          (cb[0] - tw - ex, cb[1] + th), (cb[0] - tw - ex, cb[3] - th), (cb[2] + tw + ex, cb[1] + th), (cb[2] + tw + ex, cb[3] - th)]
            for x, y in cands:
                ref.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
                r = box(ref.GetBoundingBox(), 0.05)
                if free(r, fr, own=f.GetReference(), courts=courts):
                    TEXTS[fr].append(r); placed = True; break
            if placed: break
        if placed: break
    if placed: moved += 1
    else:
        ref.SetVisible(False); hidden += 1; print('hidden', f.GetReference())
print('references placed %d, hidden %d' % (moved, hidden))
b.Save(sys.argv[2])
