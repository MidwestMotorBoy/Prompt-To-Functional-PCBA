"""The lane engine: an IC with the small parts that belong to its pins, drawn the way a person draws them.

Every pin that has parts of its own gets a *lane*, a horizontal wire running out from the pin. Along the lane, in order:
  - parts that hang off the lane to ground (decoupling, pull-downs) or up to a supply (pull-ups): shunts;
  - parts that join the lane to the lane next to it (the capacitors of a cell-voltage filter, the low side of a divider),
    stacked in one column so they read as a ladder or a divider;
  - parts in series (a resistor, a diode), one behind the other;
  - the end: a label, a ground or a supply symbol, or a wire back to the neighbouring pin (a loop such as a pi match).
Pins without parts get a short wire and a label. Neighbouring pins on one net share a bus wire. Lanes keep to the pin
side: nothing is placed in columns reserved by other lanes, so a pin with nothing on it costs no width.
"""
import os
from sch import *

LANE_GAP = 1.27
TAIL = 2.54                                         # wire between the last part of a lane and its label
L_STAIR = 27.0                                      # a lane this short may stand beside the shunt of its neighbour
N_STAIR = 4                                         # rows one shunt may stand beside (a staircase of shunts)
PIN_MIN = 5.0                                       # a row that only ends in a label or a ground stays on its pin when it would be pushed this far
PIN_MAXSHIFT = 6                                    # columns by which passing wires may be moved out to clear such labels
SUPPLY_W = 4.0                                      # weights when rows are fitted to their pins: a supply pin
DECOUPLE_W = 2.0                                    # a lane that is only the decoupling of its pin
STAIR_VERT = 3                                      # a staircase of this many shunts or more has vertical texts
STAIR_CLEAR = 3.81                                  # from the end of a lane to the axis of a shunt that stands beyond it (body half width + air)
STRETCH_MIN = float(os.environ.get("STRETCH_MIN", 1.0))                                  # a side of an IC whose lanes stand this far from their pins gets its pins moved to the lanes
JOIN_MAX = 15.0                                     # a lane wired back to the pin beside it this far off that pin gets a label at both ends instead


class Att:
    def __init__(self, kind, part, far=None, other=None):
        self.kind, self.part, self.far, self.other = kind, part, far, other      # kind: dn up rung tap hang tag
        self.u = 0.0
        self.vert = False         # texts set vertically: a bank of parts side by side
        self.one = False          # a pad whose reference and value stand on one line (it hangs on a lane that has other parts)
        self.rail = None          # a hanging part goes down to a rail at this y and joins it by wire, not by a label
        self.twin = None          # an upward diode shares its cathode node with this second diode (a diode OR)


class Node:
    def __init__(self, net):
        self.net, self.atts, self.series, self.far = net, [], None, None
        self.u = 0.0


class Lane:
    def __init__(self, row):
        self.row, self.nodes, self.term = row, [], None
        self.need = False         # the end net is used outside this circuit: a joined lane still needs its label


class Row:
    """One pin position on one side of an IC, or several neighbouring pins on the same net."""
    def __init__(self, side, dps, ox, oy):
        self.side, self.dps = side, list(dps)
        self.net = dps[0].net
        self.pts = [(ox + d.x, oy - d.y) for d in dps]
        self.lane = None
        self.kind = "pin"
        self.col = 0
        self.pinned = False       # stays on its pin: a stub to a label or a symbol, nothing passes between
        self.y = None
        self.i = 0
        self.px = self.pts[0][0]
        self.join = None          # the row this lane ends in (a loop back to the neighbouring pin)
        self.joined = None        # the lane that ends in this row
        self.jx = None            # two neighbouring lanes that end on the same net meet at this distance from the pin
        self.jup = None           # on the lower of the two: the upper one
        self.jdown = None         # on the upper of the two: the lower one
        self.jearly = False       # the join stands right behind the last series part; the parts of the end net stand beyond it
        self.jowner = False       # this lane carries those parts (and the end symbol)
        self.u_ser = 0.0          # where its last series part ends


def pava(t, s, w=None):
    """Positions y with y[k+1] - y[k] >= s[k], as close as possible to the targets t (weighted least squares), on the grid."""
    n = len(t)
    w = w or [1.0] * n
    S = [0.0] * n
    for k in range(1, n): S[k] = S[k - 1] + s[k - 1]
    z = [t[k] - S[k] for k in range(n)]
    blocks = []
    for k, v in enumerate(z):
        blocks.append([v, w[k], 1])
        while len(blocks) > 1 and blocks[-2][0] > blocks[-1][0]:
            b = blocks.pop(); a = blocks.pop()
            blocks.append([(a[0] * a[1] + b[0] * b[1]) / (a[1] + b[1]), a[1] + b[1], a[2] + b[2]])
    out = []
    for m, wt, c in blocks:
        out += [round(m / G) * G] * c
    return [out[k] + S[k] for k in range(n)]


class LaneMixin:
    _vlog = None                                             # when a dict: vertical() records the rows of each side in it (see plan_stretch)

    # ------------------------------------------------------------------ rows and planning
    def mkrows(self, a, side, ox=0, oy=0):
        ang = {"L": 0, "R": 180, "U": 270, "D": 90}[side]
        ds = [d for d in self.dp[a] if d.angle == ang]
        ds.sort(key=(lambda d: -d.y) if side in "LR" else (lambda d: d.x))
        rows = []
        for d in ds:
            if rows and d.net and rows[-1].net == d.net and rows[-1].kind != "nc" and self._adjacent(rows[-1].dps[-1], d, side):
                rows[-1].dps.append(d); rows[-1].pts.append((ox + d.x, oy - d.y))
                continue
            r = Row(side, [d], ox, oy)
            if d.net is None: r.kind = "nc"
            rows.append(r)
        for i, r in enumerate(rows): r.i = i
        return rows

    @staticmethod
    def _adjacent(d1, d2, side):
        gap = abs(d1.y - d2.y) if side in "LR" else abs(d1.x - d2.x)
        return gap < 5.2

    def n_anchor_pins(self, a, net):
        return sum(1 for aa, d in self.pins_on.get(net, []) if aa == a)

    def rung_ok(self, p, n1, n2, ok):
        """A part between the lanes of two pins may stand between them (a ladder or a divider) when it is a capacitor, or
        when both nets belong to this circuit alone; a resistor to a shared net runs along its lane instead."""
        kind = self.comps[p]["lib"].split(":")[1]
        if kind in ("C", "C_Polarized"): return True
        return self.private(n1, ok) and self.private(n2, ok)

    def plan_lane(self, a, row, cl, used, rowof):
        net = row.net
        if net is None or self.role(net) == "down": return None
        ok = set(cl) | {a}
        lane = Lane(row)
        cur, via, j = net, None, 0
        while True:
            node = Node(cur); lane.nodes.append(node)
            ups, sers = [], []
            for p in self.on.get(cur, []):
                if p not in cl or p in used or p == via: continue
                o = self.other(p, cur)
                if o is None:
                    node.atts.append(Att("tap", p)); used.add(p); continue
                rr = rowof.get(o) if (j == 0 and self.role(o) is None) else None
                if rr is not None and rr is not row and self.rung_ok(p, cur, o, ok):
                    node.atts.append(Att("rung", p, o, other=rr)); continue
                rl = self.role(o)
                if rl == "down": node.atts.append(Att("dn", p, o)); used.add(p)
                elif rl == "up": ups.append((p, o))
                else: sers.append((p, o, self.private(o, ok) and self.n_anchor_pins(a, o) == 0))
            priv = [(p, o) for p, o, pv in sers if pv]
            nonpriv = sorted([(p, o) for p, o, pv in sers if not pv], key=lambda t: len(self.nets[t[1]]))   # the signal first, then the rails
            cont, rail_end, extras = None, False, []
            if priv: cont, extras = priv[0], priv[1:] + nonpriv
            elif nonpriv: cont, extras = nonpriv[0], nonpriv[1:]
            needs = (not self.private(cur, ok)) or self.n_anchor_pins(a, cur) > 1
            if ups:
                if not needs and cont is None:
                    cont, rail_end = ups[0], True; ups = ups[1:]
                for p, o in ups:
                    att = Att("up", p, o); node.atts.append(att); used.add(p)
                    att.twin = self.find_twin(p, o, cl, used)
            for p, o in extras: node.atts.append(Att("hang", p, o)); used.add(p)
            if cont:
                p, o = cont; used.add(p); node.series = p; node.far = o
                if needs: node.atts.append(Att("tag", None, cur))          # this net leaves the circuit here too
                if rail_end or not priv or cont != priv[0]:
                    lane.term = o
                    self.terminal_node(lane, o, p, cl, used)
                    break
                via, cur, j = p, o, j + 1
                if j > 6: break
                continue
            lane.term = cur if needs else None
            break
        if lane.term: lane.need = not self.private(lane.term, ok)
        return lane

    def is_diode(self, p, k_net):
        """A two-pin diode with its cathode on k_net and its anode on a net that ends in a label here."""
        ds = self.dp[p]
        nm = {d.name: d.net for d in ds}
        a = nm.get("A")
        return len(ds) == 2 and nm.get("K") == k_net and a not in (None, k_net) and self.role(a) != "down" and not self.is_global_rail(a)

    def find_twin(self, p, far, cl, used):
        """A diode OR: a second diode into the cathode net of this one stands beside it and shares the node of the cathodes."""
        if self.is_global_rail(far) or not self.is_diode(p, far): return None
        for q in self.on.get(far, []):
            if q != p and q in cl and q not in used and self.is_diode(q, far):
                used.add(q)
                return q
        return None

    def terminal_node(self, lane, o, via, cl, used):
        """The capacitors to ground that this IC still has on the net where a lane ends (the output capacitors behind an
        inductor) hang on that end."""
        if self.role(o) == "down": return
        atts = []
        for p in self.on.get(o, []):
            if p not in cl or p in used or p == via: continue
            oth = self.other(p, o)
            if oth is not None and self.role(oth) == "down": atts.append(Att("dn", p, oth))
            elif oth is None: atts.append(Att("tap", p))
        if atts:
            node = Node(o)
            for att in atts: node.atts.append(att); used.add(att.part)
            lane.nodes.append(node)

    def mark_stairs(self, rows, chains):
        """Three or more neighbouring rows that each carry one shunt and nothing else (resistors to ground on adjacent pins,
        thermistor inputs) form a staircase. Its parts get vertical texts, so the steps stay narrow."""
        inchain = {r.i for ch in chains for r in ch["rows"]}
        def simple(r):
            if r.lane is None or r.i in inchain or r.join is not None or r.joined is not None: return False
            n = r.lane.nodes
            return len(n) == 1 and not n[0].series and len(n[0].atts) == 1 and n[0].atts[0].kind in ("dn", "hang", "tap", "up")
        run = []
        for r in list(rows) + [None]:
            if r is not None and simple(r):
                run.append(r); continue
            if len(run) >= STAIR_VERT:
                for q in run: q.lane.nodes[0].atts[0].vert = True
            run = []

    def valid_rungs(self, rows, used):
        """Rungs between lanes that are next to each other stay (one entry each); the rest become hanging parts."""
        found = {}
        for r in rows:
            if not r.lane: continue
            n0 = r.lane.nodes[0]
            for att in list(n0.atts):
                if att.kind == "rung":
                    found.setdefault(att.part, []).append((r, att)); n0.atts.remove(att)
        res = []
        for p, lst in found.items():
            r0, att0 = lst[0]
            u, l = sorted({id(r0): r0, id(att0.other): att0.other}.values(), key=lambda x: x.i)
            used.add(p)
            if l.i - u.i == 1 and u.lane is not None and l.lane is not None:
                res.append((p, u, l))
            else:
                n0 = r0.lane.nodes[0]
                n0.atts.append(Att("hang", p, self.other(p, n0.net)))
        return res

    def chains(self, rows, rungs):
        out = []
        for p, u, l in sorted(rungs, key=lambda t: (t[1].i, self.refs.index(t[0]))):
            for ch in out:
                if ch["rows"][-1] is u and l not in ch["rows"]:
                    ch["rows"].append(l); ch["parts"].append((p, u, l)); break
            else:
                out.append(dict(rows=[u, l], parts=[(p, u, l)]))
        return out

    # ------------------------------------------------------------------ sizes (mm above and below a lane)
    def dn_h(self, att):
        L = self.plen(att.part)
        if att.kind == "dn": return 1.27 + L + 3.9 + (1.3 if att.far not in (None, "GND") and self.role(att.far) == "down" else 0.0)   # a named ground shows its name
        if att.kind == "hang": return 1.27 + L + 1.27 + 0.8
        if att.kind == "tap":
            if att.vert: return 3.8 + max(tw(att.part), tw(self.comps[att.part]["value"])) + 1.0
            return 5.4 if att.one else 7.6
        return 0

    def up_h(self, att):
        if att.kind == "tag": return 2.54 + 2.0
        L = self.plen(att.part)
        if att.twin: return 1.27 + L + 1.27 + 4.9                              # the node and the line of texts above the second diode
        return 1.27 + L + (4.9 if self.is_global_rail(att.far) else 1.27 + 1.9)

    def profile(self, r, chain_rows):
        """What one row asks of the space around its lane: texts above and below (sa, sb), how far its shunts reach up
        and down (ua, db), whether those shunts may stand in a staircase beside short lanes (stair), and whether the
        lane itself is short enough to stand beside another's shunt (light)."""
        p = dict(sa=1.9, sb=0.4, ua=0.0, db=0.0, stair=False, light=False)
        if r.kind == "nc":
            p.update(sa=0.5, sb=0.5, light=True)
            return p
        if r.lane is None:
            role = self.role(r.net)
            if role == "down": p["sb"] = 4.4
            elif role == "up" and self.is_global_rail(r.net): p["sa"] = 4.4
            p["light"] = r.joined is None
            return p
        lane = r.lane
        nshunt = sum(1 for node in lane.nodes for att in node.atts if att.kind in ("dn", "hang", "up"))
        simple = len(lane.nodes) == 1 and not lane.nodes[0].series and r.i not in chain_rows and r.join is None \
            and r.joined is None and nshunt < 3
        for node in lane.nodes:
            if node.series: p["sa"] = p["sb"] = 4.2
            for att in node.atts:
                if att.kind == "tap": att.one = not simple                # in a staircase the pad keeps its two short lines
                if att.kind in ("dn", "hang", "tap"): p["db"] = max(p["db"], self.dn_h(att))
                elif att.kind == "up": p["ua"] = max(p["ua"], self.up_h(att))
                elif att.kind == "tag": p["sa"] = max(p["sa"], self.up_h(att))
        p["stair"] = p["light"] = simple
        return p

    def tail(self, lane):
        """Wire between the last part of a lane and its end (see end_tail)."""
        n, term = lane.nodes, lane.term
        if term is None: return TAIL
        if n[-1].series: part = n[-1].series                                   # the lane ends right behind this part
        elif len(n) > 1 and not n[-1].atts and n[-2].series: part = n[-2].series
        else: return TAIL
        return self.end_tail(part, term, TAIL)

    def lane_end(self, r, sg):
        """How far from the pin the wire and its end (label, symbol) of a row reach."""
        if r.kind == "nc": return 1.5
        if r.lane is None:
            return 2.54 * r.col + (self.stub_len(r.net) if r.col > 1 or r.pinned else 2.54) + self.end_extent(r.net, sg)
        e = r.u_end
        if r.lane.term and not (r.jearly and not r.jowner): e += self.tail(r.lane) + self.end_extent(r.lane.term, sg)
        return e

    def min_layout(self, rows, prof, cp):
        """The tightest rows on a side may stand: positions top to bottom, each at least the small texts of its
        neighbours away, and clear of every shunt that reaches it unless that shunt can stand in a staircase beside a
        short lane."""
        Y = []
        for j in range(len(rows)):
            pj = prof[j]
            y = 0.0
            if j:
                pk = prof[j - 1]
                y = Y[j - 1] + max(pk["sb"] + pj["sa"] + LANE_GAP, cp.get((j - 1, j), 0), 2.54)
            y = math.ceil(y / G - 1e-6) * G
            for _ in range(20):
                moved = False
                for k in range(j):
                    pk = prof[k]
                    if pk["db"] > 0 and pj["ua"] > 0 and y < Y[k] + pk["db"] + pj["ua"] + LANE_GAP - 0.01:   # shunts toward each other
                        y = math.ceil((Y[k] + pk["db"] + pj["ua"] + LANE_GAP) / G - 1e-6) * G; moved = True
                    if pk["db"] > 0 and y - pj["sa"] - LANE_GAP < Y[k] + pk["db"] - 0.01:       # lane j (with its texts) is inside the reach of k's shunts
                        ok = pk["stair"] and pj["light"] and j - k <= N_STAIR and not (pj["ua"] > 0 and y - pj["ua"] <= Y[k] + 0.01)
                        if not ok:
                            y = max(y, math.ceil((Y[k] + pk["db"] + pj["sa"] + LANE_GAP) / G - 1e-6) * G); moved = True
                    if pj["ua"] > 0 and Y[k] > y - pj["ua"] + 0.01:                 # lane k is inside the reach of j's shunts
                        ok = pj["stair"] and pk["light"] and j - k <= N_STAIR and not (pk["db"] > 0 and Y[k] + pk["db"] >= y - 0.01)
                        if not ok:
                            y = max(y, math.ceil((Y[k] + pj["ua"] + pk["sb"] + LANE_GAP) / G - 1e-6) * G); moved = True
                if not moved: break
            Y.append(y)
        return Y

    def shift(self, r, att, delta):
        """Move an attachment of node 0 and everything behind it on the lane away from the pin."""
        lane = r.lane
        seq = list(lane.nodes[0].atts)
        started = False
        for a_ in seq:
            if a_ is att: started = True
            if started: a_.u += delta
        for j, node in enumerate(lane.nodes):
            if j > 0 and not (r.jowner and j == len(lane.nodes) - 1):       # parts beyond a join are placed again from the join
                for a_ in node.atts: a_.u += delta
            if node.series: node.u += delta
        r.u_end += delta
        r.u_ser += delta

    def stairs(self, rows, prof, sg):
        """Shunts that reach past the lanes of their neighbours stand beyond those lanes, so a stack of resistors to
        ground on neighbouring pins is a staircase and not a tower."""
        n = len(rows)
        for _ in range(4):
            moved = False
            for k in range(n - 1, -1, -1):                              # down shunts, bottom row first
                p = prof[k]
                if not (p["stair"] and p["db"] > 0): continue
                att = next((a_ for a_ in rows[k].lane.nodes[0].atts if a_.kind in ("dn", "hang", "tap")), None)
                reach = [j for j in range(k + 1, n) if rows[j].y - rows[k].y < p["db"] - 0.01]
                if att is None or not reach: continue
                need = max(self.lane_end(rows[j], sg) for j in reach) + STAIR_CLEAR + self.sym_text_half(att) + self.att_extra(att)
                if att.u < need - 0.01: self.shift(rows[k], att, need - att.u); moved = True
            for k in range(n):                                          # up shunts, top row first
                p = prof[k]
                if not (p["stair"] and p["ua"] > 0): continue
                att = next((a_ for a_ in rows[k].lane.nodes[0].atts if a_.kind == "up"), None)
                reach = [j for j in range(k) if rows[k].y - rows[j].y < p["ua"] - 0.01]
                if att is None or not reach: continue
                need = max(self.lane_end(rows[j], sg) for j in reach) + STAIR_CLEAR + self.sym_text_half(att) + self.att_extra(att)
                if att.u < need - 0.01: self.shift(rows[k], att, need - att.u); moved = True
            if not moved: break

    def sym_text_half(self, att):
        """Half the width of the net name under a ground or above a supply symbol (plain GND shows none)."""
        far = att.far
        if far is None or far == "GND": return 0.0
        if self.role(far) == "down" or (self.role(far) == "up" and self.is_global_rail(far)):
            return max(0.0, tw(self.short(far)) / 2 - 1.0)
        return 0.0

    def att_w(self, att):
        """Width a part standing on a lane takes along it, with its texts to the right."""
        if att.kind == "tag":
            return 2.0 + tw(self.short(att.far)) + 2.5
        if att.vert: return 10.16
        if att.kind == "tap":
            if att.one: return 5.0 + tw(att.part) + PAD_GAP + tw(self.comps[att.part]["value"])
            return 5.0 + max(tw(att.part), tw(self.comps[att.part]["value"]))
        if att.twin:
            return max(self.vw_part(att.part), 2.0 + 2.54 + self.plen(att.twin) + 2.54 + tw(self.short(self.other(att.twin, att.far))) + 3.0)
        return self.vw_part(att.part)

    def lead(self, part):
        """Distance from the end of what comes before it on a lane to the pin axis of an upright part: a body that is
        lopsided toward the pin (the light side faces the texts) needs more."""
        return max(2.0, self.pext(part)[1] - 1.4)

    def att_lead(self, att):
        return self.lead(att.part) if att.kind in ("dn", "up", "hang") and not att.vert else 2.0

    def att_extra(self, att):
        """How much wider than a plain two-terminal body the part of an attachment reaches toward the pin."""
        return max(0.0, self.pext(att.part)[1] - 2.03) if att.kind in ("dn", "up", "hang") and not att.vert else 0.0

    def vw_part(self, part):
        c = self.comps[part]
        return self.lead(part) + max(2.54, max(2.03, self.pext(part)[0]) + 0.7) + max(tw(part), tw(c["value"])) + 1.9

    def ser_w(self, part):
        c = self.comps[part]
        return max(self.plen(part), tw(part), tw(c["value"])) + 2.54

    # ------------------------------------------------------------------ one side of an IC
    def plan_all(self, a, sides, cl, used):
        """Plan the lanes of every row of every side together: rows on signal nets first, so a pull-up or a filter part goes
        to the pin of its own signal and not to the supply pin it also touches; supply pins take what is left."""
        prio = {None: 0, "up": 1, "down": 2}
        rowof = {s: {} for s in sides}
        for s, rows in sides.items():
            for r in rows:
                if r.kind != "nc" and r.net: rowof[s].setdefault(r.net, r)
        order = sorted(((s, r) for s, rows in sides.items() for r in rows if r.kind != "nc"),
                       key=lambda t: (prio[self.role(t[1].net)], "LRUD".index(t[0]), t[1].i))
        for s, r in order:
            if s in "LR":
                lane = self.plan_lane(a, r, cl, used, rowof[s])
                if lane and (len(lane.nodes) > 1 or lane.nodes[0].atts or lane.nodes[0].series): r.lane = lane
            else:
                rows_s = sides[s]
                dirn = -1 if r is rows_s[0] else (1 if r is rows_s[-1] else 0)   # shunts go outward, never across a neighbour
                r.shunts = [p for p in self.on.get(r.net, []) if dirn and p in cl and p not in used and self.other(p, r.net) is not None
                            and self.role(self.other(p, r.net)) == "down" and self.role(r.net) != "down"]
                r.sdir = dirn
                used.update(r.shunts)

    def side_lr(self, S, a, s, rows, cl, used):
        """Position and draw the planned lanes of one side (left or right) of an IC."""
        sg = 1 if s == "R" else -1
        rowof = {}
        for r in rows:
            if r.kind != "nc" and r.net: rowof.setdefault(r.net, r)
        rungs = self.valid_rungs(rows, used)
        chains = self.chains(rows, rungs)
        for ch in chains:                                    # shunts at the ends of a ladder join its column
            f, l = ch["rows"][0], ch["rows"][-1]
            for r_, kind, key in ((f, "up", "up"), (l, "dn", "dn")):
                att = next((x for x in r_.lane.nodes[0].atts if x.kind == kind), None)
                if att: ch[key] = att; r_.lane.nodes[0].atts.remove(att)
        self.find_joins(rows, rowof)
        self.mark_stairs(rows, chains)
        for attempt in range(2):
            self.pair_joins(rows)
            prof, pinned, shift, mincol = self.vertical(a, s, rows, chains, rungs, sg)
            far = [r for r in rows if r.join is not None and abs(r.join.y - self._rowy(r.join)) > JOIN_MAX]
            if not far: break
            for r in far: r.join.joined, r.join = None, None                 # a loop that long is a label at both ends
        if os.environ.get("DEBUG_MOVED"):
            for r in rows:
                if r.lane is None and r.kind != "nc" and abs(r.y - self._rowy(r)) > 0.01:
                    print(f"MOVED {a}.{s} row {r.i} net={r.net} pin_y={self._rowy(r):.2f} y={r.y:.2f} d={r.y - self._rowy(r):.2f}")
            for r in pinned: print(f"PINNED {a}.{s} row {r.i} net={r.net} shift={shift} mincol={mincol}")
        # fan-out columns: rows moving up turn first from the top, rows moving down first from the bottom
        up = [r for r in rows if r.y < self._rowy(r) - 0.01]
        dn = [r for r in rows if r.y > self._rowy(r) + 0.01]
        for c, r in enumerate(up, 1): r.col = c + shift
        for c, r in enumerate(reversed(dn), 1): r.col = c + shift
        for r in rows:
            if r.col == 0 and len(r.pts) > 1: r.col = 1 + shift
        maxcol = max([r.col for r in rows] + [mincol])
        px0 = rows[0].pts[0][0] if rows else 0
        u0 = 2.54 * maxcol + 2.54
        self.layout_u(rows, chains, u0)
        self.stairs(rows, prof, sg)
        self.place_joins(rows)
        self.draw_rows(S, sg, px0, rows, chains)

    def vertical(self, a, s, rows, chains, rungs, sg):
        """Where the rows of one side stand: the profile of each, the rows left on their pins, and how far out the fan-out
        wires are moved. Sets r.y of every row."""
        chain_rows = {r.i for ch in chains for r in ch["rows"]}
        prof = [self.profile(r, chain_rows) for r in rows]
        for ch in chains:
            f, l = ch["rows"][0], ch["rows"][-1]
            if ch.get("up"): prof[f.i]["ua"] = max(prof[f.i]["ua"], self.up_h(ch["up"]))
            if ch.get("dn"): prof[l.i]["db"] = max(prof[l.i]["db"], self.dn_h(ch["dn"]))
        cp = {}
        for p, u, l in rungs: cp[(u.i, l.i)] = max(cp.get((u.i, l.i), 0), self.plen(p) + 2.54)
        self.layout_u(rows, chains, 0.0)                     # a dry run for the widths
        for r, p_ in zip(rows, prof): p_["light"] = p_["light"] and self.lane_end(r, sg) <= L_STAIR
        Y = self.min_layout(rows, prof, cp)
        if os.environ.get("DEBUG_ROWS") and a == os.environ["DEBUG_ROWS"] and s == os.environ.get("DEBUG_SIDE", s):
            for r, p_, y_ in zip(rows, prof, Y):
                print(f"   row {r.i:2d} net={r.net} pin_y={self._rowy(r):7.2f} Y={y_:6.2f} " + " ".join(f"{k}={v:.1f}" if isinstance(v, float) else f"{k}={v}" for k, v in p_.items()))
        gaps = self.gaps(rows, Y)
        wts = [self.fit_weight(r) for r in rows]                                                   # a supply pin keeps its decoupling close
        ys = pava([self._rowy(r) for r in rows], gaps, wts) if rows else []
        for r, y in zip(rows, ys): r.y = snap(y)
        for r in rows: r.ys = r.y                                                                  # where the lanes would stand without pinned rows
        if self._vlog is not None: self._vlog[s] = list(rows)
        pinned, shift, mincol = self.pinned_rows(rows, prof, cp, wts, sg)
        return prof, pinned, shift, mincol

    @staticmethod
    def gaps(rows, Y):
        """Least distance between the first pins of neighbouring rows: what the lanes need, and the pins of the upper row."""
        return [max(Y[k + 1] - Y[k], 2.54 * len(rows[k].pts)) for k in range(len(rows) - 1)]

    def pinned_rows(self, rows, prof, cp, wts, sg):
        """A row that is nothing but a stub to a label or a ground symbol is not pushed far from its pin by the lanes above or
        below it: it stays on its pin, and the wires that pass it stand beyond its label. The other rows are laid out again
        without it. Returns the pinned rows, by how many columns the wires of the other rows move out, and the least number
        of columns the fan-out zone must have so that the lanes start clear of the labels."""
        n = len(rows)
        cand = []
        for r in rows: r.pinned = False
        for k, r in enumerate(rows):
            if r.lane is not None or r.kind != "pin" or r.joined is not None or len(r.pts) != 1: continue
            if abs(r.y - self._rowy(r)) < PIN_MIN: continue
            y0 = self._rowy(r)
            if self.role(r.net) == "down":                                                                 # the symbol hangs below its end
                hang = 3.0 if r.net == "GND" else 4.6
                if any(x.kind != "nc" and any(y0 < q[1] < y0 + hang for q in x.pts) for x in rows if x is not r): continue
            elif self.is_global_rail(r.net):                                                               # the symbol stands above its end
                if any(x.kind != "nc" and any(y0 - 4.9 < q[1] < y0 for q in x.pts) for x in rows if x is not r): continue
            cand.append(k)
        orig = [r.y for r in rows]
        while cand:
            pin = set(cand)
            idx = [k for k in range(n) if k not in pin]
            pos = {k: i for i, k in enumerate(idx)}
            sub = [rows[k] for k in idx]
            cp2 = {(pos[u], pos[l]): v for (u, l), v in cp.items() if u in pos and l in pos}
            if sub:
                Y2 = self.min_layout(sub, [prof[k] for k in idx], cp2)
                ys = pava([self._rowy(r) for r in sub], self.gaps(sub, Y2), [wts[k] for k in idx])
                for r, y in zip(sub, ys): r.y = snap(y)
            for k in cand: rows[k].y = snap(self._rowy(rows[k]))
            up = [r for r in sub if r.y < self._rowy(r) - 0.01]
            dn = [r for r in sub if r.y > self._rowy(r) + 0.01]
            col = {}
            for c, r in enumerate(up, 1): col[id(r)] = c
            for c, r in enumerate(reversed(dn), 1): col[id(r)] = c
            shift, mincol, worst = 0, 0, None
            for k in cand:
                p = rows[k]
                need = math.ceil((self.stub_len(p.net) + self.end_extent(p.net, sg) + 1.3) / 2.54 - 1e-6)       # columns the label and its stub take
                mincol = max(mincol, need - 1)
                z0, z1 = p.y - 1.27, p.y + 1.27                                                  # the space its end takes along the pin
                if self.role(p.net) == "down": z1 = p.y + (3.0 if p.net == "GND" else 4.6)
                elif self.is_global_rail(p.net): z0 = p.y - 4.9
                for r in sub:
                    ys_ = [q[1] for q in r.pts] + [r.y]
                    if max(min(ys_), z0) <= min(max(ys_), z1):                                   # its wire passes the end
                        c = col.get(id(r), 1 if len(r.pts) > 1 else 0)
                        if c or len(r.pts) > 1: shift = max(shift, need - c)
            if shift <= PIN_MAXSHIFT:
                for k in cand: rows[k].pinned = True
                return [rows[k] for k in cand], shift, mincol
            k = max(cand, key=lambda k: self.end_extent(rows[k].net, sg))                         # too wide: let the widest label go
            cand.remove(k)
        for r, y in zip(rows, orig): r.y = y
        return [], 0, 0

    def fit_weight(self, r):
        """How much it matters that this row stands at its pin: a supply pin (its decoupling must be close) most, a lane that
        is only the decoupling of its pin next, any other lane least."""
        if r.lane is None: return 1.0
        if self.role(r.net) == "up": return SUPPLY_W
        n = r.lane.nodes
        if len(n) == 1 and not n[0].series and n[0].atts and all(
                a.kind in ("dn", "up") and self.comps[a.part]["lib"].split(":")[1] in ("C", "C_Polarized") for a in n[0].atts):
            return DECOUPLE_W
        return 1.0

    @staticmethod
    def _rowy(r):
        return r.pts[0][1] if len(r.pts) == 1 else (r.pts[0][1] + r.pts[-1][1]) / 2

    def pair_joins(self, rows):
        """Neighbouring lanes that end on the same net (the output of a regulator and the top of its feedback divider) meet
        in one wire; the lower one goes up to the upper one (jup)."""
        for r in rows: r.jup = r.jdown = r.jx = None; r.jearly = r.jowner = False
        for a, b in zip(rows, rows[1:]):
            if a.lane is None or b.lane is None or a.kind == "nc" or b.kind == "nc": continue
            ta, tb = a.lane.term, b.lane.term
            if ta is None or ta != tb or self.role(ta) == "down": continue
            if a.join is not None or b.join is not None or a.joined is not None or b.joined is not None: continue
            if a.jdown is not None or a.jup is not None or b.jdown is not None or b.jup is not None: continue
            b.jup, a.jdown = a, b

    def place_joins(self, rows):
        """Where the join wires stand. A lane that ends in a join (a pair of lanes on one net, or a loop back to the pin beside
        it) and that has parts on its end net (the output capacitors behind an inductor) is joined right behind its last series
        part; those parts stand beyond the join wire, so the feedback divider does not run along the whole output bank. Without
        such parts the join is at the end of the lanes."""
        for r in rows:
            if r.lane is None or not r.jowner: continue
            r.u_end = r.u_ser
        ue = lambda r: r.u_ser if r.jowner else r.u_end
        for r in rows:
            if r.lane is None: continue
            if r.join is not None:                                          # a loop to the pin beside it
                r.jx = ue(r) if r.jearly else r.u_end
            elif r.jdown is not None:                                       # the upper lane of a pair
                b = r.jdown
                if r.jearly or b.jearly: r.jx = b.jx = max(ue(r), ue(b))
                else: r.jx = b.jx = max(r.u_end, b.u_end) + max(self.tail(r.lane), self.tail(b.lane))
        for r in rows:
            if r.lane is None: continue
            if r.jearly and not r.jowner: r.u_end = r.jx                    # it ends at the join
            if r.jowner:
                u = r.jx + 2.54
                for att in r.lane.nodes[-1].atts:
                    att.u = u + self.att_lead(att); u += self.att_w(att)
                r.u_end = u

    def find_joins(self, rows, rowof):
        """A lane that ends on the net of the pin next to it (a pi match between two pins) is wired back to that pin."""
        for r in rows:
            if not r.lane or r.lane.term is None: continue
            r2 = rowof.get(r.lane.term)
            if r2 is None or r2 is r or r2.lane is not None or r2.joined or r2.kind == "nc": continue
            if abs(r2.i - r.i) != 1: continue
            r.join, r2.joined = r2, r

    # ------------------------------------------------------------------ columns along the lanes
    def layout_u(self, rows, chains, u0):
        """Distance from the pin end of every stem and series part, per lane: each lane uses only what it needs, and the
        capacitors of a ladder share one column."""
        cur = {r.i: u0 for r in rows if r.lane}
        for r in rows:
            if not r.lane: continue
            for node in r.lane.nodes:
                bank = [a_ for a_ in node.atts if a_.kind in ("dn", "up", "hang")]
                if len(bank) >= 3:
                    for a_ in bank: a_.vert = True
            for att in r.lane.nodes[0].atts:
                att.u = cur[r.i] + self.att_lead(att)
                cur[r.i] += self.att_w(att)
        for ch in chains:
            uc = max(cur[r.i] for r in ch["rows"])
            parts = [p for p, _, _ in ch["parts"]] + [x.part for x in (ch.get("up"), ch.get("dn")) if x]
            ch["u"] = uc + 2.0
            w = max(self.vw_part(p) for p in parts)
            for r in ch["rows"]: cur[r.i] = uc + w
        dfr = {}
        for r in rows:                                       # lanes whose end-net parts stand beyond a join (see place_joins)
            if not r.lane: continue
            n = r.lane.nodes
            dfr[r.i] = len(n) > 1 and not n[-1].series and bool(n[-1].atts) and (r.join is not None or r.jup is not None or r.jdown is not None)
        for r in rows:
            if r.jdown is not None and dfr.get(r.i) and dfr.get(r.jdown.i): dfr[r.i] = dfr[r.jdown.i] = False
        for r in rows:
            r.jowner = bool(dfr.get(r.i))
            r.jearly = r.jowner or (r.jdown is not None and bool(dfr.get(r.jdown.i))) or (r.jup is not None and bool(dfr.get(r.jup.i)))
        for r in rows:
            if not r.lane: continue
            u = cur[r.i]
            last = len(r.lane.nodes) - 1
            for j, node in enumerate(r.lane.nodes):
                if j > 0:
                    if r.jowner and j == last: break
                    for att in node.atts:
                        att.u = u + self.att_lead(att)
                        u += self.att_w(att)
                if node.series:
                    node.u = u + 1.27
                    u += 1.27 + self.ser_w(node.series)
            r.u_end = r.u_ser = u
        self.place_joins(rows)

    # ------------------------------------------------------------------ drawing
    def draw_rows(self, S, sg, px0, rows, chains):
        self._px0 = px0
        for r in rows:
            if r.kind == "nc":
                S.nc(*r.pts[0]); continue
            self.draw_row(S, sg, r, chains)
        for ch in chains:
            self.draw_chain(S, ch, sg)

    def fan(self, S, sg, r):
        """Wires from the pin ends to where the lane starts. Returns that point."""
        y, net = r.y, r.net
        px = r.px
        if r.col == 0 and len(r.pts) == 1 and abs(y - r.pts[0][1]) < 0.01:
            return r.pts[0]
        cx = px + sg * 2.54 * r.col
        for (x_, y_) in r.pts: S.wire(x_, y_, cx, y_, net)
        ys = [p[1] for p in r.pts] + [y]
        S.wire(cx, min(ys), cx, max(ys), net)
        return (cx, y)

    def draw_row(self, S, sg, r, chains):
        net = r.net
        sx, sy = self.fan(S, sg, r)
        X = lambda u: self._px0 + sg * u
        if r.lane is None:
            if r.joined is not None:
                return                                           # the lane that ends here draws the wire
            xe = sx + sg * (self.stub_len(net) if r.col > 1 or r.pinned else 2.54)
            S.wire(sx, sy, xe, sy, net)
            self.end(S, net, xe, sy, sg)
            if self.role(net) == "down" and hasattr(self, "_gstubs"): self._gstubs.append((net, xe, sy, sg, 1 if sg > 0 else 2))
            return
        lane = r.lane
        xw = sx                                                   # where the wire being drawn started
        far = sx                                                  # farthest point reached
        def further(x): return x if (x - far) * sg > 0 else far
        for j, node in enumerate(lane.nodes):
            for att in node.atts:
                xc = X(att.u)
                self.draw_att(S, att, sg, xc, sy, node.net)
                far = further(xc)
            if j == 0:
                for ch in chains:
                    if r in ch["rows"]: far = further(X(ch["u"]))
            if node.series:
                p = node.series
                xs = X(node.u)
                if sg > 0:
                    l, rr = self.hpart(S, p, xs, sy, node.net, at="left")
                    near, farp = l, rr
                else:
                    l, rr = self.hpart(S, p, xs, sy, node.far, at="right")
                    near, farp = rr, l
                S.wire(xw, sy, near[0], sy, node.net)
                xw = farp[0]; far = further(xw)
        if lane.term:
            xe = further(xw) + sg * self.tail(lane)               # where its own wire ends
            xj = X(r.jx) if r.jx is not None else None            # where it joins another lane or the pin beside it
            if r.jowner:                                          # the parts of the end net stand beyond the join
                if not lane.need: xe = further(xw)
            elif xj is not None:
                xe = xj
            S.wire(xw, sy, xe, sy, lane.term)
            paired = r.jup is not None or r.jdown is not None
            if r.jup is not None:                                 # the lower lane of a pair goes up to the upper one
                S.wire(xj, sy, xj, r.jup.y, lane.term)
            if paired:
                if r.jearly and not r.jowner: return              # it ends at the join; the lane with the parts draws the end
                if r.jup is not None and not r.jowner: return
                if not lane.need: return
            elif r.join is not None:
                r2 = r.join
                sx2 = r2.px + sg * 2.54 * r2.col if (r2.col or abs(r2.y - r2.pts[0][1]) > 0.01) else r2.pts[0][0]
                S.wire(sx2, r2.y, xj, r2.y, lane.term)
                S.wire(xj, min(sy, r2.y), xj, max(sy, r2.y), lane.term)
                if lane.need: self.end(S, lane.term, xe, sy, sg)
                return
            self.end(S, lane.term, xe, sy, sg)
        elif (far - xw) * sg > 0:
            S.wire(xw, sy, far, sy, lane.nodes[-1].net)

    def draw_att(self, S, att, sg, xc, y, net):
        """A part hanging from the lane at (xc, y)."""
        p = att.part
        if att.kind == "tag":
            S.wire(xc, y, xc, y - 2.54, att.far)
            S.label(self.short(att.far), xc, y - 2.54, 0 if sg > 0 else 180, att.far in self.glob, net=att.far)
            return
        if att.kind == "tap":
            S.wire(xc, y, xc, y + 2.54, net)
            self.pad(S, p, xc, y + 2.54, "D", side=sg, one=att.one, vert=att.vert)
            return
        if att.kind in ("dn", "hang"):
            top, bot = self.vpart(S, p, xc, y + 1.27, net, sg, at="top", vert=att.vert)
            S.wire(xc, y, top[0], top[1], net)
            if att.kind == "dn": self.end(S, att.far, bot[0], bot[1], sg)
            elif att.rail is not None:
                S.wire(bot[0], bot[1], bot[0], att.rail, att.far)
            else:
                S.wire(bot[0], bot[1], bot[0], bot[1] + 1.27, att.far)
                S.label(self.short(att.far), bot[0], bot[1] + 1.27, 0 if sg > 0 else 180, att.far in self.glob, net=att.far)
        elif att.kind == "up":
            top, bot = self.vpart(S, p, xc, y - 1.27, att.far, sg, at="bottom", vert=att.vert)
            S.wire(bot[0], bot[1], xc, y, net)
            if att.twin is not None: self.draw_twin(S, att, sg, top)
            elif self.is_global_rail(att.far): self.power(S, att.far, top[0], top[1], "up")
            else:
                S.wire(top[0], top[1], top[0], top[1] - 1.27, att.far)
                S.label(self.short(att.far), top[0], top[1] - 1.27, 0 if sg > 0 else 180, att.far in self.glob, net=att.far)

    def draw_twin(self, S, att, sg, top):
        """Diode OR: the cathodes of the upright diode and of its twin meet in a node; the end net leaves that node away from
        the twin, the twin lies beside the node with its texts above and its anode net ends in a label."""
        q, f = att.twin, att.far
        xn = self.other(q, f)
        nx, ny = top[0], snap(top[1] - 1.27)
        S.wire(top[0], top[1], nx, ny, f)
        S.wire(nx, ny, nx - sg * 2.54, ny, f)
        self.end(S, f, nx - sg * 2.54, ny, -sg)
        if sg > 0:
            l, r = self.hpart(S, q, nx + 2.54, ny, f, text="line", at="left", tx=nx + 2.0, tj="left")
            S.wire(nx, ny, l[0], ny, f)
            S.wire(r[0], ny, r[0] + 2.54, ny, xn)
            self.end(S, xn, r[0] + 2.54, ny, 1)
        else:
            l, r = self.hpart(S, q, nx - 2.54, ny, xn, text="line", at="right", tx=nx - 2.0, tj="right")
            S.wire(r[0], ny, nx, ny, f)
            S.wire(l[0] - 2.54, ny, l[0], ny, xn)
            self.end(S, xn, l[0] - 2.54, ny, -1)

    def draw_chain(self, S, ch, sg):
        xc = self._px0 + sg * ch["u"]
        rows = ch["rows"]
        for (p, u, l) in ch["parts"]:
            ym = snap((u.y + l.y) / 2)
            top, bot = self.vpart(S, p, xc, ym, u.lane.nodes[0].net, sg, at="center")
            S.wire(xc, u.y, top[0], top[1], u.lane.nodes[0].net)
            S.wire(bot[0], bot[1], xc, l.y, l.lane.nodes[0].net)
        if ch.get("up"): self.draw_att(S, ch["up"], sg, xc, rows[0].y, rows[0].lane.nodes[0].net)
        if ch.get("dn"): self.draw_att(S, ch["dn"], sg, xc, rows[-1].y, rows[-1].lane.nodes[0].net)
