"""Reads KiCad .kicad_sym libraries: pins for checking, and flattened symbol bodies for drawing."""
import os, copy
from sx import parse, find, first, get, val

_cache = {}
def _lib(lib):
    if lib not in _cache:
        for d in os.environ["SYMBOL_DIRS"].split(os.pathsep):
            p = os.path.join(d, lib + ".kicad_sym")
            if os.path.exists(p):
                t = parse(open(p).read())
                _cache[lib] = {val(s[1]): s for s in find(t, "symbol")}
                break
            p = os.path.join(d, lib + ".kicad_symdir")      # KiCad 10 one-file-per-symbol libraries
            if os.path.isdir(p):
                d2 = {}
                for f in os.listdir(p):
                    if f.endswith(".kicad_sym"):
                        for s in find(parse(open(os.path.join(p, f)).read()), "symbol"):
                            d2[val(s[1])] = s
                _cache[lib] = d2
                break
        else:
            raise KeyError(f"symbol library '{lib}' not found in SYMBOL_DIRS")
    return _cache[lib]

def _is_hidden(p):
    return any(c == "hide" or (isinstance(c, list) and c[0] == "hide" and (len(c) < 2 or c[1] == "yes")) for c in p[1:])

def _stack(s):
    """Shown pins of one unit that stand on one point and have the same name (the four GND pins of a connector chip, say) become
    one KiCad stacked pin "[8,13,18,21]": KiCad then prints one number block instead of the numbers on top of each other. The netlist
    has the same pads."""
    for u in find(s, "symbol"):
        groups = {}
        for p in find(u, "pin"):
            at = first(p, "at")
            if _is_hidden(p) or at is None: continue
            groups.setdefault((at[1], at[2], at[3] if len(at) > 3 else "0"), []).append(p)
        for g in groups.values():
            nums = [get(p, "number") for p in g]
            if len(g) < 2 or len({get(p, "name") for p in g}) != 1 or any(n.startswith("[") for n in nums): continue
            first(g[0], "number")[1] = ("s", "[" + ",".join(nums) + "]")
            for p in g[1:]: u.remove(p)
    return s

def flat(lib, name, plan=None):
    """Symbol node with 'extends' resolved, as KiCad stores it inside a schematic. A plan ((((x, y), new_y), ...), (top, bottom))
    moves pins that stand at the old points to their new y and sets the two ends of the body rectangle (the pins of an IC
    drawn with room for the parts on its lanes)."""
    s = _stack(_flat(lib, name))
    if plan: _restretch(s, plan)
    return s

def _num(v):
    v = round(v, 4)
    return "0" if abs(v) < 1e-9 else ("%.4f" % v).rstrip("0").rstrip(".")

def _restretch(s, plan):
    pins, (top, bot) = dict(plan[0]), plan[1]
    for u in find(s, "symbol"):
        for p in find(u, "pin"):
            at = first(p, "at")
            if at is None: continue
            k = (round(float(at[1]), 3), round(float(at[2]), 3))
            if k in pins: at[2] = _num(pins[k])
        for g in find(u, "rectangle"):
            a, b = first(g, "start"), first(g, "end")
            if float(a[2]) >= float(b[2]): a[2], b[2] = _num(top), _num(bot)
            else: a[2], b[2] = _num(bot), _num(top)

def plain_body(lib, name):
    """True when the symbol is one unit of pins around a single rectangle: nothing else to move when its pins are spread."""
    s = flat(lib, name)
    n_rect, units = 0, set()
    for u in find(s, "symbol"):
        unit, style = (int(v) for v in val(u[1]).rsplit("_", 2)[-2:])
        if style > 1: return False
        if find(u, "pin"): units.add(unit)
        for g in u[2:]:
            if isinstance(g, list) and g and g[0] in ("polyline", "arc", "circle", "bezier", "text"): return False
        n_rect += len(find(u, "rectangle"))
    return n_rect == 1 and len(units) == 1

def _flat(lib, name):
    syms = _lib(lib)
    if name not in syms:
        import difflib
        near = difflib.get_close_matches(name, syms, 4)
        raise KeyError(f"no symbol '{name}' in library '{lib}'. Close names: {near}")
    s = syms[name]
    ext = get(s, "extends")
    if not ext:
        return copy.deepcopy(s)
    base = _flat(lib, ext)
    out = [base[0], ("s", name)]
    props = {val(p[1]): p for p in find(s, "property")}
    for c in base[2:]:
        if isinstance(c, list) and c[0] == "property":
            out.append(copy.deepcopy(props.pop(val(c[1]), c)))
        elif isinstance(c, list) and c[0] == "symbol":
            c = copy.deepcopy(c)
            c[1] = ("s", name + val(c[1])[len(ext):])
            out.append(c)
        else:
            out.append(c)
    out.extend(copy.deepcopy(p) for p in props.values())
    return out

def pins(lib, name, plan=None):
    """[{num,name,type,x,y,angle,length,unit}] in symbol coordinates (y up)."""
    out = []
    s = flat(lib, name, plan)
    for u in find(s, "symbol"):
        unit, style = (int(v) for v in val(u[1]).rsplit("_", 2)[-2:])
        if style > 1:
            continue                      # alternate (De Morgan) body style
        for p in find(u, "pin"):
            at = first(p, "at")
            num = get(p, "number")
            # KiCad stacked-pin notation "[11,12,14]" or "[1-4]": one drawn pin, several pads
            nums = [num]
            if num.startswith("[") and num.endswith("]"):
                nums = []
                for tok in num[1:-1].split(","):
                    if "-" in tok and all(t.strip().isdigit() for t in tok.split("-")):
                        a, b = (int(t) for t in tok.split("-")); nums += [str(i) for i in range(a, b + 1)]
                    else:
                        nums.append(tok.strip())
            for num_i in nums:
              out.append(dict(num=num_i, drawn=num, name=get(p, "name"), type=p[1], x=float(at[1]), y=float(at[2]),
                            angle=int(float(at[3])) if len(at) > 3 else 0, length=float(get(p, "length", 0)),
                            unit=unit, hidden=any(c == "hide" or (isinstance(c, list) and c[0] == "hide" and (len(c)<2 or c[1] == "yes")) for c in p[1:])))
    return out
