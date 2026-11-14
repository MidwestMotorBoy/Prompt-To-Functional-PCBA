"""The drawing context of one block (one sheet): what is in it, which nets are rails, which small parts belong to which IC,
and the helpers that place parts and end a wire in a label, a ground or a supply symbol."""
import symlib
from sch import *

SUPPLY_SYM = ("power", "+3V3")

class Dp:
    """One drawn pin: the pads that sit at one place on the symbol."""
    __slots__ = ("x", "y", "unit", "nums", "name", "net", "angle", "type", "hidden", "nc", "length", "nvis")

class Ctx:
    def __init__(self, block, comps, nets, nc, cons, order):
        self.block, self.comps, self.cons = block, comps, cons
        self.refs = [r for r in order if comps[r]["block"] == block]
        self.refset = set(self.refs)
        self.pinnet = {(r, p): n for n, nodes in nets.items() for r, p in nodes}
        self.ncset = {(r, p) for r, p in nc}
        self.nets = nets
        # a net is global when it leaves the block
        self.glob = {n for n, nodes in nets.items()
                     if any(r not in self.refset for r, _ in nodes) and any(r in self.refset for r, _ in nodes)}
        dr = cons.get("drawing", {})
        self.ground_like = dict(dr.get("ground", {}))           # net -> symbol name
        self.supply = set(dr.get("supply", []))
        self.alias = dict(dr.get("alias", {}))
        for n, d in cons["nets"].items():
            if d.get("kind") == "power" and n not in self.ground_like: self.supply.add(n)
        self.dp = {r: self._drawn(r) for r in self.refs}
        self.small = [r for r in self.refs if len([d for d in self.dp[r] if not d.hidden]) <= 2 and len(self.dp[r]) <= 2]   # in sheet order, so a drawing is the same every run
        self.anchors = [r for r in self.refs if r not in self.small]
        self.on = {}                                              # net -> small parts touching it
        for r in self.small:
            for d in self.dp[r]:
                if d.net and r not in self.on.setdefault(d.net, []): self.on[d.net].append(r)
        self.pins_on = {}                                         # net -> [(anchor, Dp)]
        for a in self.anchors:
            for d in self.dp[a]:
                if d.net: self.pins_on.setdefault(d.net, []).append((a, d))
        self.owner = {}
        self._owners()

    # ------------------------------------------------------------------ names and roles
    def short(self, n):
        if n in self.alias: return self.alias[n]
        s = n.lstrip("/") if n in self.glob else n.split("/")[-1]
        if s.startswith("Net-(") and s.endswith(")"): s = s[5:-1].replace("-", ".").replace("Pad", "")
        return s

    def role(self, n):
        if n is None: return None
        if n == "GND" or n in self.ground_like: return "down"
        if n in self.supply: return "up"
        return None

    def _drawn(self, r):
        lib, name = self.comps[r]["lib"].split(":")
        pos = {}
        for p in symlib.pins(lib, name):
            pos.setdefault((p["unit"], round(p["x"], 3), round(p["y"], 3)), []).append(p)
        out = []
        for (u, x, y), lst in sorted(pos.items(), key=lambda kv: (kv[0][0], -kv[0][2], kv[0][1])):
            d = Dp()
            d.x, d.y, d.unit = x, y, u
            vis = [p for p in lst if not p["hidden"]] or lst
            d.name, d.angle, d.type, d.length = vis[0]["name"], vis[0]["angle"], vis[0]["type"], vis[0]["length"]
            d.nums = sorted((p["num"] for p in lst), key=lambda s: (len(s), s))
            d.nvis = len({p["num"] for p in vis})                # the numbers printed at this pin (the hidden pads print nothing)
            d.net = next((self.pinnet.get((r, p["num"])) for p in lst if self.pinnet.get((r, p["num"]))), None)
            d.nc = d.net is None
            d.hidden = all(p["hidden"] for p in lst)
            out.append(d)
        return [d for d in out if not (d.hidden and d.net is None)]

    def nets_of(self, r):
        """The two nets of a small part (None for a one-pin part's missing end), in pad order."""
        ds = self.dp[r]
        return [d.net for d in ds]

    def other(self, r, net):
        ns = [d.net for d in self.dp[r]]
        if len(ns) == 1: return None
        o = [n for n in ns if n != net]
        return o[0] if o else net

    # ------------------------------------------------------------------ which small part belongs to which IC
    def _owners(self):
        cons, comps = self.cons, self.comps
        sec = lambda r: comps[r].get("section", "")
        own = self.owner
        # 1. templates and explicit hints
        for a, t in cons.get("draw", {}).items():
            if a not in self.refset: continue
            for k, v in t.items():
                if k in ("kind", "ic"): continue
                for r in (v if isinstance(v, list) else [v]):
                    if isinstance(r, str) and r in self.small: own[r] = a
        for r, tgt in cons.get("drawing", {}).get("near", {}).items():
            if r in self.small and tgt.split(".")[0] in self.refset: own[r] = tgt.split(".")[0]
        for r, tgt in cons.get("serves", {}).items():
            if r in self.small and r not in own:
                t = tgt.split(".")[0]
                if t in self.anchors: own[r] = t
        # 2. neighbours of a part: anchors touching its non-rail nets
        def adj(r):
            c = []
            for d in self.dp[r]:
                n = d.net
                if n and self.role(n) is None:
                    c += [a for a, _ in self.pins_on.get(n, [])]
            return c
        for r in self.small:
            if r in own: continue
            c = adj(r)
            if not c: continue
            same = [a for a in c if sec(a) == sec(r)]
            pick = same or c
            own[r] = max(set(pick), key=lambda a: (pick.count(a), -self.refs.index(a)))
        # 3. chains: a part between two small parts follows them
        for _ in range(4):
            for r in self.small:
                if r in own: continue
                for d in self.dp[r]:
                    n = d.net
                    if not n or self.role(n) is not None: continue
                    nb = [x for x in self.on.get(n, []) if x != r and x in own]
                    if nb: own[r] = own[nb[0]]; break
        # 4. serves a small part: follow it
        for r, tgt in cons.get("serves", {}).items():
            if r in self.small and r not in own:
                t = tgt.split(".")[0]
                if t in own: own[r] = own[t]
        # 5. a rail-only part (decoupling a rail with no local IC pin) in the same section as an anchor
        for r in self.small:
            if r in own: continue
            same = [a for a in self.anchors if sec(a) == sec(r)]
            if same: own[r] = same[0]

    def claimed(self, a):
        return [r for r in self.refs if self.owner.get(r) == a and r in self.small]

    def private(self, net, ok):
        """True when every pin on this net belongs to the given set of refs (nothing else needs a label here)."""
        if net in self.glob or self.role(net) is not None: return False
        return all(r in ok for r, _ in self.nets[net])
