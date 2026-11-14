"""Cheap layout lint on the generated sheets: text over text, text over wires. Run: python3 lint.py out/sheets/x.kicad_sch ..."""
import re, sys

def parse(path):
    s = open(path).read()
    texts, wires = [], []
    for m in re.finditer(r'\(property "(Reference|Value)" "([^"]*)" \(at ([-\d.]+) ([-\d.]+) (\d+)\) \(effects \(font \(size ([\d.]+) [\d.]+\)\) \(justify (\w+)\)( \(hide yes\))?', s):
        kind, t, x, y, a, sz, j, hid = m.groups()
        if hid or t.startswith("#"): continue
        texts.append((t, float(x), float(y), float(sz), "left", "prop", 0))
    for m in re.finditer(r'\(text "((?:[^"\\]|\\.)*)" \(exclude_from_sim no\) \(at ([-\d.]+) ([-\d.]+) 0\) \(effects \(font \(size ([\d.]+)', s):
        texts.append((m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4)), "left bottom", "text", 0))
    for m in re.finditer(r'\((label|global_label) "([^"]*)" (?:\(shape \w+\) )?\(at ([-\d.]+) ([-\d.]+) (\d+)\)', s):
        k, t, x, y, a = m.groups()
        texts.append((t, float(x), float(y), 1.27, "label", k, int(a)))
    for m in re.finditer(r'\(wire \(pts \(xy ([-\d.]+) ([-\d.]+)\) \(xy ([-\d.]+) ([-\d.]+)\)\)', s):
        wires.append(tuple(map(float, m.groups())))
    return texts, wires

def bbox(t):
    s, x, y, sz, j, kind, a = t
    w = len(s) * 1.13 * sz / 1.27 + (3.0 if kind == "global_label" else 0); h = sz
    if kind in ("label", "global_label"):
        if a in (90, 270): return (x - h, y - w if a == 90 else y, x, y if a == 90 else y + w)
        return (x, y - h, x + w, y) if a == 0 else (x - w, y - h, x, y)
    if "right" in j: x0, x1 = x - w, x
    else: x0, x1 = x, x + w
    if "bottom" in j: y0, y1 = y - h, y
    else: y0, y1 = y - h / 2, y + h / 2
    if a == 90: return (x - h / 2, y - w, x + h / 2, y) if "right" not in j else (x - h / 2, y, x + h / 2, y + w)
    return (x0, y0, x1, y1)

def shrink(b, d): return (b[0] + d, b[1] + d, b[2] - d, b[3] - d)
def inter(a, b): return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

def bodies(path):
    import json, os
    f = os.path.dirname(path) + "/../lint/" + os.path.basename(path) + ".json"
    return json.load(open(f)) if os.path.exists(f) else []

def main(paths):
    n = 0
    for p in paths:
        texts, wires = parse(p)
        bs = [(t, shrink(bbox(t), 0.25)) for t in texts]
        for t, b in bs:
            if t[5] == "prop" and False: continue
            for (ref, x0, y0, x1, y1) in bodies(p):
                if inter(b, shrink((x0, y0, x1, y1), 0.3)) and not (t[5] == "prop" and t[0] == ref):
                    n += 1; print(f"{p.split('/')[-1]}: text/symbol '{t[0]}' ({t[1]:.0f},{t[2]:.0f}) over {ref}")
        for i in range(len(bs)):
            for j in range(i + 1, len(bs)):
                if inter(bs[i][1], bs[j][1]):
                    n += 1; print(f"{p.split('/')[-1]}: text/text '{bs[i][0][0]}' ({bs[i][0][1]:.0f},{bs[i][0][2]:.0f}) x '{bs[j][0][0]}' ({bs[j][0][1]:.0f},{bs[j][0][2]:.0f})")
            t, b = bs[i]
            for w in wires:
                wb = (min(w[0], w[2]) - 0.05, min(w[1], w[3]) - 0.05, max(w[0], w[2]) + 0.05, max(w[1], w[3]) + 0.05)
                if inter(b, wb):
                    n += 1; print(f"{p.split('/')[-1]}: text/wire '{t[0]}' ({t[1]:.0f},{t[2]:.0f})"); break
    print(n, "findings")

if __name__ == "__main__": main(sys.argv[1:])
