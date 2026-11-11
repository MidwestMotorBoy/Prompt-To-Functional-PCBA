"""stagev.py -> spec for both charger stages: vias in the FET source, switch-node and drain pads, vias at the FET end of the
inductor pads (the switch node now reaches the FET through the back layer), and the ground strap from each moved 100 nF
capacitor to its FET's source pads. Port 2 coordinates; port 1 is 23.026 mm to the right."""
import json
S = []
def V(net, x, y): S.append({"net": net, "via": [round(x, 3), y]})
for port, dx in ((2, 0.0), (1, 23.026)):
    P = '/USB Port %d/' % port
    for leg, x0, dn in ((1, 0.0, 'AC_SNS_N'), (2, 4.5, 'BAT_SNS_P')):
        o = x0 + dx; sw = P + 'SW%d' % leg
        for y in (98.83, 99.47, 100.125): V('GND', 84.9 + o, y)                      # source pads 5, 6, 7
        V(sw, 85.964 + o, 99.8)
        for s in (-0.31, 0.31):
            for y in (98.6, 99.4, 100.2, 101.0): V(sw, 85.964 + s + o, y)
        for y in (99.35, 100.25): V(P + dn, 87.494 + o, y)
        for y in (98.83, 99.47, 100.125): V(P + dn, 88.16 + o, y)
        xs = (86.1, 86.6, 87.1) if leg == 1 else (90.5, 91.0, 91.5)                  # inductor pad, FET end
        for x in xs:
            for y in (94.1, 94.7, 95.3, 95.9): V(sw, x + dx, y)
        S.append({"net": "GND", "layer": "F", "w": 0.4, "pts": [[round(x + o, 3), y] for x, y in ((86.04, 97.32), (85.6, 97.76), (85.15, 97.95), (84.9, 98.4), (84.9, 98.83))]})
print(json.dumps(S))
