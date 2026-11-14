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

def flat(lib, name):
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
    base = flat(lib, ext)
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
