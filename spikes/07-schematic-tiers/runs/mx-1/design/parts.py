"""Placing parts: small two-pin parts upright or lying down with their text beside them, pads, ground and supply symbols,
and the end of a wire (label, ground or supply)."""
from sch import *
import symlib

class PartMixin:
    # ------------------------------------------------------------------ geometry of a small part
    def _geo(self, r):
        lib, name = self.comps[r]["lib"].split(":")
        return geo(lib, name, 1, self.plans.get(r))

    def padnets(self, r):
        return {p["num"]: self.pinnet.get((r, p["num"])) for p in self._geo(r)["pins"]}

    def _pose(self, r, want, net):
        """Rotation that puts the pin on `net` above ('U') or left ('L') of the other pin of a two-pin part."""
        g = self._geo(r)
        pos = {}
        for p in g["pins"]: pos.setdefault((round(p["x"], 3), round(p["y"], 3)), p)
        if len(pos) == 1: return self._pose1(r, "U")
        nets = {k: self.pinnet.get((r, p["num"])) for k, p in pos.items()}
        k0, k1 = list(pos)[:2]
        for ang in (0, 90, 180, 270):
            o0, o1 = xf(k0[0], k0[1], ang), xf(k1[0], k1[1], ang)
            if want == "U":
                if abs(o0[0]) > 0.01 or abs(o1[0]) > 0.01: continue
                first = k0 if o0[1] < o1[1] else k1
            else:
                if abs(o0[1]) > 0.01 or abs(o1[1]) > 0.01: continue
                first = k0 if o0[0] < o1[0] else k1
            second = k1 if first == k0 else k0
            if nets[first] == net or nets[second] != net: return ang
        return 0

    def _pose1(self, r, want):
        """One-pin part: rotation that makes the body lie in direction `want` from the pin end."""
        g = self._geo(r)
        p = g["pins"][0]
        for ang in (0, 90, 180, 270):
            dx, dy = pin_dir(p, ang)
            if (dx, dy) == {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}[want]: return ang
        return 0

    def plen(self, r):
        """Pin-to-pin length of a small part, and the box around its body."""
        g = self._geo(r)
        ys = [p["y"] for p in g["pins"]]; xs = [p["x"] for p in g["pins"]]
        return max(max(ys) - min(ys), max(xs) - min(xs))

    # ------------------------------------------------------------------ texts
    def body_half(self, r, ang):
        """Half width and half height of the body of a small part as it stands at angle ang."""
        b = self._geo(r)["body"] or (-2.54, -2.54, 2.54, 2.54)
        c = [xf(b[0], b[1], ang), xf(b[2], b[3], ang), xf(b[0], b[3], ang), xf(b[2], b[1], ang)]
        return max(abs(a[0]) for a in c), max(abs(a[1]) for a in c)

    def body_x(self, r, ang, mirror=False):
        """How far the body of a two-pin part reaches left and right of its pin axis when placed at angle ang."""
        g = self._geo(r)
        b = g["body"] or (-2.03, -2.03, 2.03, 2.03)
        c = [xf(b[0], b[1], ang, mirror), xf(b[2], b[3], ang, mirror), xf(b[0], b[3], ang, mirror), xf(b[2], b[1], ang, mirror)]
        ax = xf(g["pins"][0]["x"], g["pins"][0]["y"], ang, mirror)[0]
        return ax - min(a[0] for a in c), max(a[0] for a in c) - ax

    def pext(self, r):
        """(light, heavy): how far the body of an upright two-pin part reaches to the lighter and to the heavier side of its
        pin axis. A lopsided part is mirrored so that its light side faces its texts."""
        g = self._geo(r)
        if len({(round(p["x"], 3), round(p["y"], 3)) for p in g["pins"]}) < 2: return 2.03, 2.03
        l, r_ = self.body_x(r, self._pose(r, "U", None))
        return min(l, r_), max(l, r_)

    def vtext(self, r, x, yc, side, vert=False, hw=2.03, dy=0.0):
        hw = max(2.03, hw)
        if vert:           # two vertical lines of text beside the part, for banks of parts side by side
            ln = max(tw(r), tw(self.comps[r]["value"]))
            if ln / 2 <= 3.4: dy = 0.0                    # a long text moves off the wire it hangs from
            return dict(ref_at=(x + (hw + 1.3) * side, yc + dy), val_at=(x + (hw + 3.84) * side, yc + dy), vert=True)
        off = max(2.54, hw + 0.7)
        if side > 0: return dict(ref_at=(x + off, yc - 1.27), val_at=(x + off, yc + 1.27), ref_j="left", val_j="left")
        return dict(ref_at=(x - off, yc - 1.27), val_at=(x - off, yc + 1.27), ref_j="right", val_j="right")

    def vw(self, r):
        """Width a vertical part with its text needs, along a rail."""
        c = self.comps[r]
        return max(tw(r), tw(c["value"])) + 6.6

    def put(self, S, r, x, y, ang, unit=1, **kw):
        c = self.comps[r]
        return S.symbol(*c["lib"].split(":"), r, c["value"], x, y, ang, footprint=c["footprint"], fields=c["fields"],
                        nets=self.padnets(r), unit=unit, plan=self.plans.get(r), **kw)

    # ------------------------------------------------------------------ small parts
    def vpart(self, S, r, x, y, top_net, side=1, at="top", text=True, vert=False):
        """A two-pin part upright with `top_net` on its upper pin. `at` says what y means: 'top' pin end, 'bottom' pin end
        or 'center'. Returns (upper pin end, lower pin end)."""
        ang = self._pose(r, "U", top_net)
        g = self._geo(r)
        ys = []
        for p in g["pins"]:
            ox, oy = xf(p["x"], p["y"], ang)
            ys.append(oy)
        lo, hi = min(ys), max(ys)
        x = snap(x)                                          # texts are placed from the grid point the part really stands on
        yc = snap({"top": y - lo, "bottom": y - hi, "center": y - (lo + hi) / 2}[at])
        mir, (bl, br) = False, self.body_x(r, ang)
        if ang in (0, 180) and len(ys) > 1:                  # a lopsided body keeps its light side toward the texts
            ml, mr = self.body_x(r, ang, True)
            if (mr if side > 0 else ml) < (br if side > 0 else bl) - 0.1: mir, (bl, br) = True, (ml, mr)
        hw = br if side > 0 else bl
        dy = {"top": 1.27, "bottom": -1.27}.get(at, 0.0)
        pl = self.put(S, r, x, yc, ang, mirror=mir, **(self.vtext(r, x, yc, side, vert, hw, dy) if text else dict(hide_ref=True, hide_val=True)))
        ends = sorted(set(pl.pin.values()), key=lambda p: p[1])
        return ends[0], ends[-1]

    def hpart(self, S, r, x, y, left_net, text="above", at="center", tx=None, tj="left"):
        """A two-pin part lying down with `left_net` on its left pin. Returns (left pin end, right pin end). Text 'line': the
        reference and the value on one line above the part, starting at tx (tj 'left') or ending there (tj 'right')."""
        ang = self._pose(r, "L", left_net)
        g = self._geo(r)
        xs = []
        for p in g["pins"]:
            ox, oy = xf(p["x"], p["y"], ang)
            xs.append(ox)
        lo, hi = min(xs), max(xs)
        xc = snap({"left": x - lo, "right": x - hi, "center": x - (lo + hi) / 2}[at])
        y = snap(y)
        c = self.comps[r]
        hh = max(1.4, self.body_half(r, ang)[1])
        if text == "above":
            kw = dict(ref_at=(xc, y - max(3.0, hh + 1.6)), val_at=(xc, y + max(3.0, hh + 1.6)), ref_j="center", val_j="center")
        elif text == "line":
            yy = y - hh - 2.2
            v = c["value"]
            up, dn = (lambda a: math.ceil(a / G - 1e-6) * G), (lambda a: math.floor(a / G + 1e-6) * G)     # text anchors snap to the grid: keep the gap
            if tj == "left":
                xr = up(tx); kw = dict(ref_at=(xr, yy), val_at=(up(xr + tw(r) + PAD_GAP), yy), ref_j="left", val_j="left")
            else:
                xv = dn(tx); kw = dict(ref_at=(dn(xv - tw(v) - PAD_GAP), yy), val_at=(xv, yy), ref_j="right", val_j="right")
        elif text == "below":
            kw = dict(ref_at=(xc, y + hh + 1.0), val_at=(xc, y + hh + 3.54), ref_j="center", val_j="center")
        else:
            kw = dict(hide_ref=True, hide_val=True)
        pl = self.put(S, r, xc, y, ang, **kw)
        ends = sorted(set(pl.pin.values()), key=lambda p: p[0])
        return ends[0], ends[-1]

    def pad(self, S, r, x, y, body, text=True, side=1, clear=0.0, one=False, vert=False):
        """A one-pin part (test point, wire pad) with its pin end at (x, y) and its body toward `body` ('U','D','L','R'),
        its reference and value beside the body (to the right, or to the left when side < 0, `clear` further out).
        Returns the placed symbol."""
        ang = self._pose1(r, body)
        g = self._geo(r)
        p = g["pins"][0]
        dx, dy = xf(p["x"], p["y"], ang)
        ox, oy = snap(x - dx), snap(y - dy)
        if not text: return self.put(S, r, ox, oy, ang, hide_ref=True, hide_val=True)
        b = g["body"] or (0, 0, 0, 0)
        c = [xf(b[0], b[1], ang), xf(b[2], b[3], ang), xf(b[0], b[3], ang), xf(b[2], b[1], ang)]
        ym = oy + (min(a[1] for a in c) + max(a[1] for a in c)) / 2
        if vert:                                     # two vertical lines of text beside the stub and the pad, for a staircase of parts
            ln = max(tw(r), tw(self.comps[r]["value"]))
            hw = max(abs(a[0]) for a in c)
            yc = snap(y - 2.54 + 1.27 + ln / 2)
            return self.put(S, r, ox, oy, ang, ref_at=(x + (hw + 1.3) * side, yc), val_at=(x + (hw + 3.84) * side, yc), vert=True)
        if one:                                      # reference and value on one line: the pad takes little height
            wr, wv = tw(r), tw(self.comps[r]["value"])
            if side < 0:
                bx0 = min(ox + min(a[0] for a in c), x)
                tx = bx0 - 1.9 - clear
                return self.put(S, r, ox, oy, ang, ref_at=(tx - wv - PAD_GAP, ym), val_at=(tx, ym), ref_j="right", val_j="right")
            bx1 = max(ox + max(a[0] for a in c), x)
            tx = bx1 + 1.9 + clear
            return self.put(S, r, ox, oy, ang, ref_at=(tx, ym), val_at=(tx + wr + PAD_GAP, ym), ref_j="left", val_j="left")
        if side < 0:
            bx0 = min(ox + min(a[0] for a in c), x)
            tx = bx0 - 1.9 - clear
            return self.put(S, r, ox, oy, ang, ref_at=(tx, ym - 1.27), val_at=(tx, ym + 1.27), ref_j="right", val_j="right")
        bx1 = max(ox + max(a[0] for a in c), x)
        tx = bx1 + 1.9 + clear
        return self.put(S, r, ox, oy, ang, ref_at=(tx, ym - 1.27), val_at=(tx, ym + 1.27), ref_j="left", val_j="left")

    # ------------------------------------------------------------------ power symbols and wire ends
    def power(self, S, net, x, y, kind):
        """kind: 'gnd' (hangs below the point), 'up' (stands above it)."""
        S.npwr += 1
        ref = f"#PWR{self.idx:02d}{S.npwr:03d}"
        if kind == "gnd":
            nm = self.ground_like.get(net, "GND")
            show = net != "GND"
            S.symbol("power", nm, ref, self.short(net), x, y, 0, hide_ref=True, hide_val=not show, key=f"pwr{S.npwr}",
                     val_at=(x, y + (3.81 if nm.startswith("GNDREF") else 3.81)), val_j="center", power=True, nets={"1": net})
        else:
            S.symbol("power", "+3V3", ref, self.short(net), x, y, 0, hide_ref=True, key=f"pwr{S.npwr}",
                     val_at=(x, y - 3.56), val_j="center", power=True, nets={"1": net})

    def is_global_rail(self, net):
        return net in self.glob and self.role(net) == "up"

    def end(self, S, net, x, y, dirn, wire_net=None):
        """The wire arrives at (x, y) heading `dirn` (+1 right, -1 left): finish it with a ground symbol, a supply symbol,
        or a label."""
        role = self.role(net)
        if role == "down":
            self.power(S, net, x, y, "gnd"); return
        if role == "up" and self.is_global_rail(net):
            self.power(S, net, x, y, "up"); return
        S.label(self.short(net), x, y, 0 if dirn > 0 else 180, net in self.glob, net=net)

    def end_extent(self, net, dirn):
        """How far past the wire end the symbol or label reaches, along the wire direction."""
        role = self.role(net)
        if role == "down": return 1.5 if net == "GND" else max(1.5, tw(self.short(net)) / 2 + 0.3)
        if role == "up" and self.is_global_rail(net): return max(1.5, tw(self.short(net)) / 2 + 0.3)
        return tw(self.short(net)) + (1.6 if net in self.glob else 0.6)

    def end_tail(self, part, net, base=2.54):
        """Wire between the end of a part lying down and the supply or ground symbol that ends its wire: long enough that the
        name of that symbol stands clear of the text of the part (the reference above it, the value below it)."""
        role = self.role(net)
        if role == "down" and net != "GND": above = False
        elif role == "up" and self.is_global_rail(net): above = True
        else: return base
        tp = tw(part) if above else tw(self.comps[part]["value"])
        return max(base, math.ceil(((tp + tw(self.short(net))) / 2 + 1.0 - self.plen(part) / 2) / G - 1e-6) * G)

    def stub_len(self, net):
        """Length of the wire from a fan-out column to a ground or supply symbol that shows its name centred on itself:
        long enough that the name stays clear of the columns on its inner side."""
        role = self.role(net)
        if not ((role == "down" and net != "GND") or (role == "up" and self.is_global_rail(net))): return 2.54
        return max(2.54, math.ceil((tw(self.short(net)) / 2 + 1.0) / G - 1e-6) * G)

    def stub_end(self, S, net, x, y, dirn, length=2.54):
        """A pin end at (x, y): short wire, then the end. Returns the x where the wire ends."""
        xe = x + dirn * length
        S.wire(x, y, xe, y, net)
        self.end(S, net, xe, y, dirn)
        return xe
