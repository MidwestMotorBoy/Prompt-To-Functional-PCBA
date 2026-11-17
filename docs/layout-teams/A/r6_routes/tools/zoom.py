#!/usr/bin/env python3
"""zoom.py <board.kicad_pcb> <cu_dump.json> <out.png> <x0,y0,x1,y1> [px/mm=40] [layers=F.Cu,In2.Cu,In3.Cu,B.Cu]
One picture with the router layers side by side for a window, pads labelled ref.pad (small), tracks coloured by net,
plus a legend of the signal nets with tracks in the window."""
import sys, os, json, colorsys, zlib
from PIL import Image, ImageDraw
sys.path.insert(0, "/home/claude/repo/tools/copper")
from dc_score import load_copper
pcb, dump, out, win = sys.argv[1:5]
S = float(sys.argv[5]) if len(sys.argv) > 5 else 40
Ls = sys.argv[6].split(",") if len(sys.argv) > 6 else ["F.Cu", "In2.Cu", "In3.Cu", "B.Cu"]
x0, y0, x1, y1 = map(float, win.split(","))
D = json.load(open(dump)); Z, T, V = load_copper(pcb)
W, H = int((x1 - x0) * S), int((y1 - y0) * S)
def col(n, a=200):
    if n == "GND": return (90, 90, 90, a)
    h = (zlib.crc32(n.encode()) % 360) / 360; r, g, b = colorsys.hsv_to_rgb(h, 0.75, 0.8); return (int(r * 255), int(g * 255), int(b * 255), a)
P = lambda x, y: ((x - x0) * S, (y - y0) * S)
inwin = lambda x, y: x0 - 1 < x < x1 + 1 and y0 - 1 < y < y1 + 1
panels = []; nets = set()
for L in Ls:
    im = Image.new("RGB", (W, H), (250, 250, 248)); d = ImageDraw.Draw(im, "RGBA")
    for z in Z:
        if z["layer"] == L and len(z["pts"]) > 2:
            d.polygon([P(*q) for q in z["pts"]], fill=col(z["net"], 70))
    for p in D["pads"]:
        for r in p["shapes"].get(L, []):
            d.polygon([P(*q) for q in r["ring"]], fill=(210, 210, 210, 200), outline=(60, 60, 60, 255))
    for t in T:
        if t["layer"] == L and (inwin(*t["a"]) or inwin(*t["b"])):
            d.line([P(*t["a"]), P(*t["b"])], fill=col(t["net"], 230), width=max(1, int(t["w"] * S)))
            if t["net"] not in ("GND",): nets.add(t["net"])
    for v in V:
        if inwin(v["x"], v["y"]):
            c = P(v["x"], v["y"]); r = v["size"] / 2 * S
            d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=col(v["net"], 255), outline=(0, 0, 0))
    if L == "F.Cu":
        for p in D["pads"]:
            if "F.Cu" in p["shapes"] and inwin(p["x"], p["y"]) and p["num"]:
                d.text(P(p["x"] - 0.15, p["y"] - 0.1), "%s.%s" % (p["ref"], p["num"]), fill=(0, 0, 0, 255))
    d.text((4, 4), L, fill=(255, 0, 0))
    panels.append(im)
leg = sorted(nets); LH = 12 * (len(leg) // 3 + 2)
out_im = Image.new("RGB", (W * 2 + 8, H * ((len(Ls) + 1) // 2) + 8 * ((len(Ls) + 1) // 2) + LH), "white")
for i, im in enumerate(panels):
    out_im.paste(im, ((i % 2) * (W + 8), (i // 2) * (H + 8)))
d = ImageDraw.Draw(out_im); yb = H * ((len(Ls) + 1) // 2) + 8 * ((len(Ls) + 1) // 2)
for i, n in enumerate(leg):
    d.rectangle([(i % 3) * (W * 2 // 3) + 4, yb + (i // 3) * 12 + 2, (i % 3) * (W * 2 // 3) + 14, yb + (i // 3) * 12 + 10], fill=col(n)[:3])
    d.text(((i % 3) * (W * 2 // 3) + 18, yb + (i // 3) * 12), n.replace("/USB Port ", "P"), fill=(0, 0, 0))
out_im.save(out); print(out, out_im.size)
