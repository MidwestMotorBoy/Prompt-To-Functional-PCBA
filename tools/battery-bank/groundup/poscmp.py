import sys, json, pcbnew
M = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); pl = json.load(open(sys.argv[2])); n = 0
for f in b.GetFootprints():
    r = f.GetReference(); p = f.GetPosition()
    if r in pl:
        q = pl[r]
        if abs(M(p.x) - q[0]) > 0.002 or abs(M(p.y) - q[1]) > 0.002 or abs((f.GetOrientationDegrees() - q[2] + 180) % 360 - 180) > 0.1:
            n += 1; print(r, 'board %.4f,%.4f,%.0f' % (M(p.x), M(p.y), f.GetOrientationDegrees()), 'json', q)
    if r in sys.argv[3:]: bb = f.GetBoundingBox(False); print(r, f.GetValue(), 'at %.3f,%.3f rot %.0f' % (M(p.x), M(p.y), f.GetOrientationDegrees()), 'bbox x %.2f..%.2f y %.2f..%.2f' % (M(bb.GetLeft()), M(bb.GetRight()), M(bb.GetTop()), M(bb.GetBottom())), 'flipped' if f.IsFlipped() else '')
print('differences', n, 'of', len(pl))
