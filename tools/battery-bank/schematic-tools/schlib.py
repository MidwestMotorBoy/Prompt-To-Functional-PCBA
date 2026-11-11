"""Small KiCad 10 schematic text helpers: top-level blocks, symbol pins in sheet coordinates, connection points."""
import math
import re
import uuid

BS = chr(92)


def block_end(s, i):
    """Index just past the ')' closing the '(' at s[i]."""
    d = 0
    k = i
    while True:
        c = s[k]
        if c == '"':
            k += 1
            while s[k] != '"':
                k += 2 if s[k] == BS else 1
        elif c == "(":
            d += 1
        elif c == ")":
            d -= 1
            if d == 0:
                return k + 1
        k += 1


def top_blocks(s, head):
    """(start, end) of each depth-1 block '(head ...' ; start is at the '('."""
    out = []
    for m in re.finditer(r"\n\t\(" + re.escape(head) + r"[\s)]", s):
        a = m.start() + 2
        out.append((a, block_end(s, a)))
    return out


def lib_pins(s):
    """{lib_id: [(unit, number, x, y)]} from the sheet's embedded lib_symbols."""
    a = s.index("\n\t(lib_symbols") + 2
    e = block_end(s, a)
    lib = s[a:e]
    out = {}
    for m in re.finditer(r'\n\t\t\(symbol "([^"]+)"', lib):
        sa = m.start() + 3
        se = block_end(lib, sa)
        blk = lib[sa:se]
        name = m.group(1)
        short = name.split(":")[-1]
        pins = []
        for sm in re.finditer(r'\(symbol "' + re.escape(short) + r'_(\d+)_(\d+)"', blk):
            ua = sm.start()
            ue = block_end(blk, ua)
            unit = int(sm.group(1))
            for pm in re.finditer(r"\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) [-\d.]+\)", blk[ua:ue]):
                pe = block_end(blk, ua + pm.start())
                num = re.search(r'\(number "([^"]*)"', blk[ua + pm.start():pe]).group(1)
                pins.append((unit, num, float(pm.group(1)), float(pm.group(2))))
        out[name] = pins
    return out


def r2(v):
    return round(v + 0.0, 2)


def symbols(s):
    """List of dicts for placed symbols."""
    libs = lib_pins(s)
    out = []
    for a, b in top_blocks(s, "symbol"):
        blk = s[a:b]
        lid = re.search(r'\(lib_id "([^"]+)"', blk).group(1)
        at = re.search(r"\n\t\t\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)", blk)
        X, Y, rot = float(at.group(1)), float(at.group(2)), float(at.group(3))
        mir = re.search(r"\n\t\t\(mirror (\w)\)", blk)
        mir = mir.group(1) if mir else ""
        unit = int(re.search(r"\n\t\t\(unit (\d+)\)", blk).group(1))
        ref = re.search(r'\(property "Reference" "([^"]+)"', blk).group(1)
        pins = {}
        for u, num, px, py in libs.get(lid, []):
            if u not in (0, unit):
                continue
            x, y = px, -py
            if mir == "x":
                y = -y
            elif mir == "y":
                x = -x
            t = math.radians(rot)
            xr = x * math.cos(t) + y * math.sin(t)
            yr = -x * math.sin(t) + y * math.cos(t)
            pins[num] = (r2(X + xr), r2(Y + yr))
        out.append(dict(a=a, b=b, ref=ref, lib=lid, at=(X, Y, rot), pins=pins, power=lid.startswith("power:")))
    return out


def wires(s):
    out = []
    for a, b in top_blocks(s, "wire"):
        m = re.search(r"\(xy ([-\d.]+) ([-\d.]+)\) \(xy ([-\d.]+) ([-\d.]+)\)", s[a:b])
        x0, y0, x1, y1 = map(float, m.groups())
        out.append(dict(a=a, b=b, p=((r2(x0), r2(y0)), (r2(x1), r2(y1)))))
    return out


def anchors(s, head):
    out = []
    for a, b in top_blocks(s, head):
        m = re.search(r"\(at ([-\d.]+) ([-\d.]+)", s[a:b])
        n = re.match(r'\(\w+ "([^"]*)"', s[a:b])
        out.append(dict(a=a, b=b, p=(r2(float(m.group(1))), r2(float(m.group(2)))), name=n.group(1) if n else None))
    return out


def sheet_pins(s):
    out = []
    for a, b in top_blocks(s, "sheet"):
        for m in re.finditer(r'\(pin "([^"]+)" \w+\s*\(at ([-\d.]+) ([-\d.]+)', s[a:b]):
            out.append((r2(float(m.group(2))), r2(float(m.group(3)))))
    return out


def on_segment(p, seg):
    (x0, y0), (x1, y1) = seg
    x, y = p
    if (x, y) in seg:
        return False
    if abs((x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)) > 1e-3:
        return False
    return min(x0, x1) - 1e-3 <= x <= max(x0, x1) + 1e-3 and min(y0, y1) - 1e-3 <= y <= max(y0, y1) + 1e-3


def new_uuids(blk):
    return re.sub(r'\(uuid "[0-9a-f-]+"\)', lambda m: '(uuid "%s")' % uuid.uuid4(), blk)
