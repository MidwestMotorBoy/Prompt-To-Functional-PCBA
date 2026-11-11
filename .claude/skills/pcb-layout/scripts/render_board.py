"""Render a KiCad board to PNG for review: courtyards, pads coloured by net, refdes, zones, tracks and vias.

    python render_board.py board.kicad_pcb out.png [x0 y0 x1 y1] [px_per_mm] [--layers F.Cu,In1.Cu,B.Cu]

Coordinates are mm relative to the top-left of the board outline (Edge.Cuts). Default region: the whole board plus
a small margin; default scale 8 px/mm. Tracks, vias and zone fills are drawn for the listed copper layers
(default: all copper layers, lighter for inner ones). GND pads are dark green, unconnected pads grey, every other
net gets a stable colour from its name. Rule areas (keep-outs) are outlined red, footprint keep-outs magenta,
back-side courtyards blue, DNP parts drawn faint with a '*' after the refdes.

Run with KiCad's bundled python (it has pcbnew and PIL), e.g.
    "C:/Program Files/KiCad/10.0/bin/python.exe" -I render_board.py ...
"""
import sys
import zlib

import pcbnew
from PIL import Image, ImageDraw, ImageFont

args = [a for a in sys.argv[1:] if not a.startswith("--")]
opts = dict(a[2:].split("=", 1) if "=" in a else (a[2:], "") for a in sys.argv[1:] if a.startswith("--"))
if "layers" in opts and not opts["layers"]:
    i = sys.argv.index("--layers")
    opts["layers"] = sys.argv[i + 1]
    args = [a for a in args if a != opts["layers"]]
board = pcbnew.LoadBoard(args[0])
out = args[1]
bb = board.GetBoardEdgesBoundingBox()
OX, OY = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
W, H = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())
x0, y0, x1, y1 = (map(float, args[2:6]) if len(args) >= 6 else (-2, -2, W + 2, H + 2))
S = float(args[6]) if len(args) >= 7 else 8.0

copper = [l for l in board.GetEnabledLayers().CuStack()]
if "layers" in opts:
    want = set(opts["layers"].split(","))
    copper = [l for l in copper if board.GetStandardLayerName(l) in want or board.GetLayerName(l) in want]

img = Image.new("RGB", (max(1, int((x1 - x0) * S)), max(1, int((y1 - y0) * S))), (18, 18, 24))
d = ImageDraw.Draw(img, "RGBA")
try:
    font = ImageFont.truetype("arial.ttf", max(9, int(S * 0.9)))
    fsm = ImageFont.truetype("arial.ttf", max(8, int(S * 0.55)))
except OSError:
    font = fsm = ImageFont.load_default()


def P(v):
    return ((pcbnew.ToMM(v.x) - OX - x0) * S, (pcbnew.ToMM(v.y) - OY - y0) * S)


def col(net):
    if net == "GND":
        return (40, 140, 60)
    if not net or net.startswith("unconnected"):
        return (110, 110, 110)
    h = zlib.crc32(net.encode())
    return (90 + h % 160, 90 + (h >> 8) % 160, 90 + (h >> 16) % 160)


def layer_alpha(layer):
    return 200 if layer in (pcbnew.F_Cu, pcbnew.B_Cu) else 110


def poly(ps, fill, outline=None):
    for i in range(ps.OutlineCount()):
        ch = ps.Outline(i)
        pts = [P(ch.CPoint(j)) for j in range(ch.PointCount())]
        if len(pts) > 2:
            d.polygon(pts, fill=fill, outline=outline)


# zone fills (copper layers chosen), then rule areas
for z in board.Zones():
    if z.GetIsRuleArea():
        continue
    for layer in copper:
        if z.IsOnLayer(layer) and z.HasFilledPolysForLayer(layer):
            poly(z.GetFilledPolysList(layer), col(z.GetNetname()) + (60,))
# tracks and vias
for t in board.GetTracks():
    if t.GetClass() == "PCB_VIA":
        r = pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2 * S
        q = P(t.GetPosition())
        d.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], fill=col(t.GetNetname()) + (230,), outline=(0, 0, 0))
    elif t.GetLayer() in copper:
        w = max(1, int(pcbnew.ToMM(t.GetWidth()) * S))
        d.line([P(t.GetStart()), P(t.GetEnd())], fill=col(t.GetNetname()) + (layer_alpha(t.GetLayer()),), width=w)
# outline
for g in board.GetDrawings():
    if g.GetLayer() == pcbnew.Edge_Cuts:
        shp = g.GetShape()
        if shp == pcbnew.SHAPE_T_RECT:
            a, c = P(g.GetStart()), P(g.GetEnd())
            d.rectangle([min(a[0], c[0]), min(a[1], c[1]), max(a[0], c[0]), max(a[1], c[1])], outline=(230, 230, 80), width=2)
        elif shp == pcbnew.SHAPE_T_ARC:
            d.line([P(g.GetStart()), P(g.GetArcMid()), P(g.GetEnd())], fill=(230, 230, 80), width=2)
        else:
            d.line([P(g.GetStart()), P(g.GetEnd())], fill=(230, 230, 80), width=2)
for z in board.Zones():
    if z.GetIsRuleArea():
        poly(z.Outline(), (220, 60, 60, 40), (220, 60, 60, 255))
# footprints
for fp in board.GetFootprints():
    for z in fp.Zones():
        poly(z.Outline(), (230, 90, 200, 40), (230, 90, 200, 255))
    back = fp.IsFlipped()
    c = fp.GetCourtyard(pcbnew.B_CrtYd if back else pcbnew.F_CrtYd)
    if c.OutlineCount():
        cb = c.BBox()
        d.rectangle([P(cb.GetOrigin()), P(cb.GetEnd())], outline=(80, 160, 255) if back else (200, 200, 200), width=1)
    dnp = fp.IsDNP()
    for p in fp.Pads():
        poly(p.GetEffectivePolygon(pcbnew.B_Cu if back else pcbnew.F_Cu, pcbnew.ERROR_INSIDE),
             col(p.GetNetname()) + ((90,) if dnp else (230,)))
        if p.HasHole():
            r = pcbnew.ToMM(p.GetDrillSize().x) / 2 * S
            q = P(p.GetPosition())
            d.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], fill=(0, 0, 0))
    if c.OutlineCount():
        q = P(cb.GetCenter())
        t = fp.GetReference() + ("*" if dnp else "")
        f = font if max(cb.GetWidth(), cb.GetHeight()) > pcbnew.FromMM(3) else fsm
        w = d.textlength(t, font=f)
        d.text((q[0] - w / 2, q[1] - S * 0.45), t, fill=(255, 255, 255), font=f, stroke_width=1, stroke_fill=(0, 0, 0))
img.save(out)
print(out, img.size)
