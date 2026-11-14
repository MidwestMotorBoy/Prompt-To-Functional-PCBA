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

def _flat(lib, name):
    """Symbol node with 'extends' resolved, as KiCad stores it inside a schematic."""
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

def _tr(node, f):
    """Apply f to every coordinate pair under xy / center / start / end of a symbol node."""
    if isinstance(node, list):
        if node and node[0] in ("xy", "center", "start", "end") and len(node) >= 3:
            x, y = f(float(node[1]), float(node[2]))
            node[1], node[2] = f"{x:g}", f"{y:g}"
        else:
            for c in node: _tr(c, f)

def _horizontal_mosfet(name, g, s_nums, d_nums):
    """The vertical N-MOSFET symbol drawn on its side for a power path read left to right: source left, drain right,
    gate below. Only the picture changes: pin numbers and names are those of the real part."""
    sym = _flat("Transistor_FET", "Q_NMOS_GSD")
    sym[1] = ("s", name)
    for c in sym:
        if isinstance(c, list) and c[0] == "symbol":
            c[1] = ("s", name + val(c[1])[len("Q_NMOS_GSD"):])
    for u in find(sym, "symbol"):
        if val(u[1]).endswith("_0_1"):
            _tr(u, lambda x, y: (y, x))
        else:
            pins_ = find(u, "pin")
            gp = [p for p in pins_ if get(p, "name") == "G"][0]
            sp = [p for p in pins_ if get(p, "name") == "S"][0]
            dp = [p for p in pins_ if get(p, "name") == "D"][0]
            for p in pins_: u.remove(p)
            def mk(p, num, at, hide):
                p = copy.deepcopy(p)
                first(p, "at")[1:] = at
                first(p, "number")[1] = ("s", num)
                if hide: p.append(["hide", "yes"]) if False else p.insert(4, ["hide", "yes"])
                return p
            u.append(mk(gp, g, ["0", "-5.08", "90"], False))
            for i, n in enumerate(s_nums): u.append(mk(sp, n, ["-5.08", "2.54", "0"], i > 0))
            for i, n in enumerate(d_nums): u.append(mk(dp, n, ["5.08", "2.54", "180"], i > 0))
    return sym

_OVERRIDE = {("MonolithDev", "AGM404AP1"): lambda: _horizontal_mosfet("AGM404AP1", "4", "123", "5678")}

def flat(lib, name):
    """Symbol node with 'extends' resolved, as KiCad stores it inside a schematic. A few symbols are redrawn on their side."""
    if (lib, name) in _OVERRIDE: return _OVERRIDE[(lib, name)]()
    return _flat(lib, name)

def pins(lib, name):
    """[{num,name,type,x,y,angle,length,unit}] in symbol coordinates (y up)."""
    out = []
    s = flat(lib, name)
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
