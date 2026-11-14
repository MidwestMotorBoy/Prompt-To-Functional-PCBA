"""Lead key routes, tier 0: Kelvin sense pairs of both ports, escape vias for the high-side gates and thermistor lines.
Run from the routes folder:  python3 lead_kelvin.py <dir> <board>   -> lead_kelvin.json"""
import sys, json; sys.path.insert(0, '../tools')
from obst import HR
from dlib import Board
d, board = sys.argv[1], sys.argv[2]
h = HR(d, board); b = Board(); b.set(json.load(open('../best_placement.json')))
def pad(ref, num, n=0):
    return [p for p in b.pads(ref) if p['num'] == num][n]
for port, dx in (("1", 0.0), ("2", -23.1)):
    P = "/USB Port %s/" % port; k = "4" if port == "1" else "5"
    # gate: via in the gate pad of the input half-bridge, the router takes it from there
    g = pad("Q%s01" % k, "1"); h.via(P + "HG1", g['x'], g['y'], quiet=True)
    # (a via in the thermistor pad was tried: the SW2 pour on B and PACK_P on In2 do not clear it, DRC error)
    sh_ac, sh_bat = "R%s24" % k, "R%s27" % k
    # each tap: (net, shunt, shunt pad, sense resistor) ; tap point = inner edge of the shunt pad (the edge facing the other pad)
    for net, sh, num, rs in ((P + "PPHV", sh_ac, "1", "R%s25" % k), (P + "AC_SNS_N", sh_ac, "2", "R%s26" % k),
                             (P + "BAT_SNS_P", sh_bat, "1", "R%s28" % k), ("PACK_P", sh_bat, "2", "R%s29" % k)):
        sp = pad(sh, num); op = pad(sh, "2" if num == "1" else "1"); rp = pad(rs, "1")
        x0, y0, x1, y1 = sp['box']; cx, cy = sp['x'], sp['y']
        # inner edge point, 0.25 mm inside the pad
        if abs(op['x'] - cx) > abs(op['y'] - cy): tap = (x1 - 0.25 if op['x'] > cx else x0 + 0.25, cy)
        else: tap = (cx, y1 - 0.25 if op['y'] > cy else y0 + 0.25)
        h.link(net, tap, (rp['x'], rp['y']), "In3.Cu", r=0.9)
h.save('lead_kelvin.json')
