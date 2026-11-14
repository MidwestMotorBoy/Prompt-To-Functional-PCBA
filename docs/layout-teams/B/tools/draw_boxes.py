"""draw_boxes.py <board_dump.json> <boxes.json> <out.png> [placement.json]
Picture for planning: section boxes (floorplan json with "blocks": {"<section> | <side>": [x0,y0,x1,y1]}) over the
fixed parts and no-footprint keep-outs of the board dump, top side left, bottom side right (seen from the top).
Fixed = prefixes J, H, TP, SW plus the cup-fixed parts (FIXED_EXTRA below). With a placement, every part's courtyard
is drawn at its placed position ({ref: [x, y, quarter-turn degrees relative to the dump, optional side]})."""
import sys, json, re
from PIL import Image, ImageDraw, ImageFont
FIXED_EXTRA = {"U301", "L401", "L501", "TH101", "TH104", "TH401", "TH501", "C208", "C209", "C210", "C211", "C212", "C213", "C421", "C456", "C521", "C556"}
def is_fixed(r): return re.match(r"[A-Z]+", r).group() in ("J", "H", "TP", "SW") or r in FIXED_EXTRA
def main(dumpf, boxf, out, plf=None):
    d = json.load(open(dumpf)); B = json.load(open(boxf))["blocks"]; P = json.load(open(plf)) if plf else {}
    bx = d["box"]; S = 14; W = int((bx[2] - bx[0]) * S) + 40; H = int((bx[3] - bx[1]) * S) + 40
    im = Image.new("RGB", (2 * W, H), "white"); dr = ImageDraw.Draw(im)
    try: fo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    except Exception: fo = ImageFont.load_default()
    def px(x, y, s): return (20 + (x - bx[0]) * S + (W if s else 0), 20 + (y - bx[1]) * S)
    def rect(b, s, **k): dr.rectangle([px(b[0], b[1], s), px(b[2], b[3], s)], **k)
    for s in (0, 1):
        rect(bx, s, outline="black", width=2)
        for x in range(80, 122, 5): dr.text(px(x, bx[1] - 1.2, s), str(x), fill="gray", font=fo); dr.line([px(x, bx[1], s), px(x, bx[3], s)], fill=(235, 235, 235))
        for y in range(65, 138, 5): dr.text(px(bx[0] - 1.3, y, s), str(y), fill="gray", font=fo); dr.line([px(bx[0], y, s), px(bx[2], y, s)], fill=(235, 235, 235))
    for k in d["keepouts"]:
        if not k.get("no_footprints"): continue
        for s, L in ((0, "F.Cu"), (1, "B.Cu")):
            if L in k["layers"]: rect(k["box"], s, fill=(225, 225, 225))
    cols = {"USB Port 1": (150, 110, 230), "USB Port 2": (240, 120, 170), "Cells and Gauge": (90, 200, 150), "MCU": (90, 170, 230), "3V3 Rail": (240, 170, 60)}
    for name, b in B.items():
        s = 1 if name.endswith("B.Cu") else 0; c = cols.get(name.split(" / ")[0], (150, 150, 150))
        rect(b, s, outline=c, width=3); dr.text((px(b[0], b[1], s)[0] + 4, px(b[0], b[1], s)[1] + 3), name.split(" / ")[0].replace("USB Port ", "P").replace("Cells and Gauge", "CG") + ": " + name.split(" / ")[1][:26], fill=c, font=fo)
    for f in d["fps"]:
        r = f["ref"]; c = f["court"]; s = 1 if f["side"] == "B.Cu" else 0
        if r in P and not is_fixed(r):
            x, y, a = P[r][:3]; q = int(a) // 90 % 4; lx0, ly0, lx1, ly1 = c[0] - f["x"], c[1] - f["y"], c[2] - f["x"], c[3] - f["y"]
            if len(P[r]) > 3 and P[r][3] in ("B", "B.Cu", "F", "F.Cu"):
                ns = 1 if P[r][3][0] == "B" else 0
                if ns != s: lx0, lx1 = -lx1, -lx0; s = ns
            for _ in range(q): lx0, ly0, lx1, ly1 = -ly1, lx0, -ly0, lx1
            c = [x + lx0, y + ly0, x + lx1, y + ly1]
        elif not is_fixed(r) and not P: continue
        elif not is_fixed(r): continue
        rect(c, s, fill=(120, 120, 120) if is_fixed(r) else None, outline="black")
        dr.text((px(c[0], c[1], s)[0] + 2, px(c[0], c[1], s)[1] + 1), r, fill="white" if is_fixed(r) else "black", font=fo)
    im.save(out)
if __name__ == "__main__": main(*sys.argv[1:])
