"""fillnear.py <board.kicad_pcb> <net substring> <layer> x0,y0,x1,y1 : the saved zone outlines and fills of that net
on that layer that reach into the box (text parse of the board file, no KiCad needed)."""
import sys, re
from shapely.geometry import Polygon, box
t = open(sys.argv[1]).read(); net, layer = sys.argv[2], sys.argv[3]; B = box(*[float(v) for v in sys.argv[4].split(",")])
for zm in re.finditer(r'\n\t\(zone\n', t):
    j = t.find('\n\t)\n', zm.start() + 1); z = t[zm.start():j]
    n = re.search(r'\(net "([^"]*)"\)', z); L = re.search(r'\(layers? "([^"]*)"', z)
    if not n or net not in n.group(1) or not L or L.group(1) != layer: continue
    for kind in ("polygon", "filled_polygon"):
        for pm in re.finditer(r'\(' + kind + r'\b(.*?)\(pts(.*?)\)\s*\)', z, re.S):
            pts = [(float(a), float(b)) for a, b in re.findall(r'\(xy ([-\d.]+) ([-\d.]+)\)', pm.group(2))]
            if len(pts) < 3: continue
            P = Polygon(pts).buffer(0)
            if P.intersects(B): print(n.group(1), kind, "piece bounds", [round(v, 2) for v in P.bounds], "area in box", round(P.intersection(B).area, 3))
