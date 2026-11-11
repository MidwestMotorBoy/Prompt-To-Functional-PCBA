"""fetv.py [what] -> spec: extra vias in the switch-node and drain pads of the four charger FETs (what: sw, drain or both)"""
import json, sys
what = sys.argv[1] if len(sys.argv) > 1 else 'both'
S = []
for port, dx in ((2, 0.0), (1, 23.026)):
    P = '/USB Port %d/' % port
    for leg, xs, xd, xp, dn in ((1, 85.964, 87.184, 88.16, 'AC_SNS_N'), (2, 90.464, 91.684, 92.66, 'BAT_SNS_P')):
        if what in ('sw', 'both'):
            S.append({"net": P + 'SW%d' % leg, "via": [round(xs + dx, 3), 99.8]})
            for s in (-0.31, 0.31):
                for y in (98.6, 99.4, 100.2, 101.0): S.append({"net": P + 'SW%d' % leg, "via": [round(xs + s + dx, 3), y]})
        if what in ('drain', 'both'):
            for y in (99.35, 100.25): S.append({"net": P + dn, "via": [round(xd + 0.31 + dx, 3), y]})
            for y in (98.83, 99.47, 100.125): S.append({"net": P + dn, "via": [round(xp + dx, 3), y]})
print(json.dumps(S))
