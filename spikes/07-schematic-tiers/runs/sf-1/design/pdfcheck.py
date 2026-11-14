"""Measured text-overlap check: reads word boxes from the rendered PDF (what KiCad really drew). Run after make.sh:
python3 design/pdfcheck.py out/render/sheets.pdf   Prints overlapping word pairs per page and a count."""
import subprocess, sys, re
pdf = sys.argv[1] if len(sys.argv) > 1 else "out/render/sheets.pdf"
txt = subprocess.run(["pdftotext", "-bbox", pdf, "-"], capture_output=True, text=True).stdout
pages = txt.split("<page ")[1:]
tot = 0
for i, pg in enumerate(pages, 1):
    ws = [(float(a), float(b), float(c), float(d), w) for a, b, c, d, w in
          re.findall(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', pg)]
    ws = [(x0, y0 + 2.5, x1, y1 - 2.5, w) for x0, y0, x1, y1, w in ws]
    n = 0
    for a in range(len(ws)):
        for b in range(a + 1, len(ws)):
            p, q = ws[a], ws[b]
            if p[0] < q[2] - 0.5 and q[0] < p[2] - 0.5 and p[1] < q[3] - 0.3 and q[1] < p[3] - 0.3:
                n += 1; print(f"page {i}: '{p[4]}' x '{q[4]}' at {p[0]*0.3528:.0f},{p[1]*0.3528:.0f} mm")
    print(f"page {i}: {n} text overlaps"); tot += n
print("total", tot)
