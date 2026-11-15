"""eview.py <board.e.json> <out.png> [x0,y0,x1,y1] [px per mm] [--drc=file.drc.json] [--layers=F,In2,In3,B] [--nolabel] [--nets=substr,...]
A picture of a board (edump.py output) for looking at placement and routing: pours (pale, by net), pads (grey, power
pads tinted), tracks by layer colour (F red, In2 blue, In3 green, B purple, In1/In4 orange), vias, part outlines with
references, pad numbers when zoomed in, open connections from a DRC report as thick black-yellow lines."""
import sys, json, zlib, colorsys, re
from PIL import Image, ImageDraw, ImageFont
a = [x for x in sys.argv[1:] if not x.startswith("--")]; O = dict(x[2:].split("=", 1) if "=" in x else (x[2:], "1") for x in sys.argv[1:] if x.startswith("--"))
D = json.load(open(a[0])); out = a[1]
xs = [p[0] for o in D["outline"] for p in o["ring"]]; ys = [p[1] for o in D["outline"] for p in o["ring"]]
x0, y0, x1, y1 = [float(v) for v in a[2].split(",")] if len(a) > 2 and a[2] != "-" else (min(xs) - 0.5, min(ys) - 0.5, max(xs) + 0.5, max(ys) + 0.5)
S = float(a[3]) if len(a) > 3 else 14.0
show = O.get("layers", "F,In2,In3,B").split(",")
W, H = int((x1 - x0) * S) + 1, int((y1 - y0) * S) + 1
im = Image.new("RGB", (W, H), (255, 255, 255)); d = ImageDraw.Draw(im, "RGBA")
P = lambda x, y: ((x - x0) * S, (y - y0) * S)
def fnt(sz):
    try: return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(sz))
    except Exception: return ImageFont.load_default()
def ncol(n, al=255, sat=0.55, val=0.9):
    if n == "GND": return (120, 120, 120, al)
    h = (zlib.crc32(n.encode()) % 360) / 360; r, g, b = colorsys.hsv_to_rgb(h, sat, val); return (int(r * 255), int(g * 255), int(b * 255), al)
LC = {"F.Cu": (200, 30, 30), "In1.Cu": (230, 140, 0), "In2.Cu": (30, 80, 220), "In3.Cu": (20, 150, 60), "In4.Cu": (230, 140, 0), "B.Cu": (150, 40, 190)}
inwin = lambda bx: bx[2] >= x0 and bx[0] <= x1 and bx[3] >= y0 and bx[1] <= y1
for g in range(int(x0 // 5 * 5), int(x1) + 1, 5):
    d.line([P(g, y0), P(g, y1)], fill=(0, 0, 0, 25)); d.text((P(g, y0)[0] + 2, 1), str(g), fill=(110, 110, 110), font=fnt(10))
for g in range(int(y0 // 5 * 5), int(y1) + 1, 5):
    d.line([P(x0, g), P(x1, g)], fill=(0, 0, 0, 25)); d.text((1, P(x0, g)[1] + 1), str(g), fill=(110, 110, 110), font=fnt(10))
for o in D["outline"]: d.line([P(*q) for q in o["ring"] + o["ring"][:1]], fill=(0, 0, 0), width=2)
# pours
for z in D["zones"]:
    L = z["layer"].split(".")[0]
    if L not in show or (z["net"] in ("GND", "PACK_P", "3V3") and L not in ("F", "B")): continue
    if z["net"] == "GND" and z["prio"] == 0: continue
    for pl in z["fill"]:
        if len(pl["ring"]) > 2:
            if L == "F": d.polygon([P(*q) for q in pl["ring"]], fill=ncol(z["net"], 70))
            else: d.line([P(*q) for q in pl["ring"] + pl["ring"][:1]], fill=LC[z["layer"]] + (110,), width=1)
# part outlines
for f in D["fps"]:
    c = f["court"]
    if not inwin(c): continue
    back = f["layer"] == "B.Cu"
    if back and "B" not in show: continue
    d.rectangle([P(c[0], c[1]), P(c[2], c[3])], outline=(150, 40, 190, 120) if back else (0, 0, 0, 90), width=1)
# pads
for p in D["pads"]:
    if not inwin(p["box"]): continue
    for ln, recs in p["shapes"].items():
        L = ln.split(".")[0]
        if L == "B" and "B" in show and max(p["drill"]) == 0:
            for r in recs: d.polygon([P(*q) for q in r["ring"]], outline=(150, 40, 190, 200))
        if L != "F": continue
        for r in recs:
            cl = (150, 150, 150, 230) if p["net"] not in D["netclass"] or D["netclass"].get(p["net"], "") in ("Default", "Kelvin", "GateDrive") else ncol(p["net"], 230, 0.5, 0.75)
            if p["net"] == "GND": cl = (90, 90, 90, 230)
            d.polygon([P(*q) for q in r["ring"]], fill=cl)
    if max(p["drill"]) > 0:
        c = P(p["x"], p["y"]); r = min(p["drill"]) / 2 * S; d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=(255, 255, 255), outline=(0, 0, 0))
# tracks
order = ["B.Cu", "In4.Cu", "In3.Cu", "In2.Cu", "In1.Cu", "F.Cu"]
for ln in order:
    if ln.split(".")[0] not in show: continue
    for t in D["tracks"]:
        if t["layer"] != ln: continue
        if not inwin([min(t["a"][0], t["b"][0]), min(t["a"][1], t["b"][1]), max(t["a"][0], t["b"][0]), max(t["a"][1], t["b"][1])]): continue
        d.line([P(*t["a"]), P(*t["b"])], fill=LC[ln] + (255 if ln == "F.Cu" else 190,), width=max(1, int(t["w"] * S)))
for v in D["vias"]:
    if not (x0 <= v["x"] <= x1 and y0 <= v["y"] <= y1): continue
    c = P(v["x"], v["y"]); r = v["size"] / 2 * S; d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], outline=(0, 0, 0, 255), fill=(250, 220, 60, 200) if v["net"] != "GND" else (200, 200, 200, 200))
# labels
if "nolabel" not in O:
    f1 = fnt(max(8, S * 0.55))
    for f in D["fps"]:
        c = f["court"]
        if not inwin(c) or f["layer"] == "B.Cu": continue
        if S >= 9 or (c[2] - c[0]) * (c[3] - c[1]) > 6:
            d.text(P((c[0] + c[2]) / 2 - len(f["ref"]) * 0.17 * max(8, S * 0.55) / S, (c[1] + c[3]) / 2 - 0.3 * max(8, S * 0.55) / S), f["ref"], fill=(0, 0, 0), font=f1)
    if S >= 30:
        f2 = fnt(S * 0.22)
        for p in D["pads"]:
            if not inwin(p["box"]) or "F.Cu" not in p["shapes"]: continue
            b = p["box"]
            d.text(P(b[0] + 0.02, b[1]), p["num"], fill=(255, 255, 0), font=f2)
            if S >= 45 and p["net"]:
                d.text(P(b[0] + 0.02, b[1] + 0.22), p["net"].split("/")[-1][:9], fill=(0, 60, 160), font=f2)
if "drc" in O:
    R = json.load(open(O["drc"])); want = O.get("nets", "").split(",") if "nets" in O else None
    for u in R.get("unconnected_items", []):
        it = u["items"]
        if len(it) < 2: continue
        nm = re.search(r"\[(.*?)\]", it[0]["description"]).group(1)
        if want and not any(w_ in nm for w_ in want): continue
        A = (it[0]["pos"]["x"], it[0]["pos"]["y"]); B = (it[1]["pos"]["x"], it[1]["pos"]["y"])
        if nm in ("GND", "PACK_P", "3V3"):
            c = P(*A); d.ellipse([c[0] - 5, c[1] - 5, c[0] + 5, c[1] + 5], outline=(255, 0, 255), width=2); continue
        d.line([P(*A), P(*B)], fill=(0, 0, 0, 255), width=3); d.line([P(*A), P(*B)], fill=(255, 230, 0, 255), width=1)
    for v in R.get("violations", []):
        if v["severity"] != "error": continue
        q = v["items"][0]["pos"]; c = P(q["x"], q["y"]); d.rectangle([c[0] - 7, c[1] - 7, c[0] + 7, c[1] + 7], outline=(255, 0, 0), width=3)
im.save(out); print(out, im.size)
