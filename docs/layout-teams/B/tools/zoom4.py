"""zoom4.py <board.kicad_pcb> <cu.json of its placement> <out.png> <x0,y0,x1,y1> [px per mm, default 50] [layers, default F.Cu,B.Cu,In2.Cu,In3.Cu]
Team B, phase 2 round 3 (lead). Four zoom.py pictures of one window of ANY board (routed boards too) side by side, each
with a 1 mm grid and the mm coordinates on the edges, so that tracks.json coordinates for tools/handroute.py can be
read off the picture. Colours as zoom.py (net colour by name; GND grey)."""
import sys, os, subprocess, tempfile, shutil
from PIL import Image, ImageDraw
T = os.path.dirname(os.path.abspath(__file__))
b, cu, out, win = sys.argv[1:5]; S = float(sys.argv[5]) if len(sys.argv) > 5 else 50.0
Ls = (sys.argv[6] if len(sys.argv) > 6 else "F.Cu,B.Cu,In2.Cu,In3.Cu").split(",")
x0, y0, x1, y1 = [float(v) for v in win.split(",")]
tmp = tempfile.mkdtemp(prefix="z4_")
try:
    shutil.copy(b, tmp + "/cu.kicad_pcb"); shutil.copy(cu, tmp + "/cu.json"); open(tmp + "/ghost.log", "w").close()
    ims = []
    for L in Ls:
        subprocess.run([sys.executable, T + "/zoom.py", tmp, tmp + "/z.png", win, L, str(S)], check=True, capture_output=True)
        im = Image.open(tmp + "/z.png").convert("RGB"); d = ImageDraw.Draw(im, "RGBA")
        x = int(x0) + 1
        while x < x1:
            d.line([((x - x0) * S, 0), ((x - x0) * S, im.size[1])], fill=(0, 0, 0, 40 if x % 5 else 90)); d.text(((x - x0) * S + 2, 2), str(x), fill=(0, 0, 0)); x += 1
        y = int(y0) + 1
        while y < y1:
            d.line([(0, (y - y0) * S), (im.size[0], (y - y0) * S)], fill=(0, 0, 0, 40 if y % 5 else 90)); d.text((2, (y - y0) * S + 2), str(y), fill=(0, 0, 0)); y += 1
        d.text((im.size[0] / 2 - 15, im.size[1] - 14), L, fill=(200, 0, 0)); ims.append(im)
    w, h = ims[0].size; cols = 2 if len(ims) > 1 else 1; rows = (len(ims) + cols - 1) // cols
    o = Image.new("RGB", (cols * w + (cols - 1) * 8, rows * h + (rows - 1) * 8), "white")
    for i, im in enumerate(ims): o.paste(im, ((i % cols) * (w + 8), (i // cols) * (h + 8)))
    o.save(out); print(out, o.size)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
