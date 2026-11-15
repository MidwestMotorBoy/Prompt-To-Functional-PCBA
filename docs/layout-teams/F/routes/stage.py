"""stage.py: closes the open items of the power-stage region (y 92..114) on board g1."""
import sys; sys.path.insert(0, '/home/claude/prompt-to-functional-pcba/docs/layout-teams/F/tools')
from ml import ML
h = ML('/home/claude/runs/c_stage', 'g1')
OK = {}
# 1, 2: gate resistor to gate pad, straight on F.Cu through the gap in the AC_SNS_N pour (0.33 mm from the source pad)
for p, r, q in (('1', 'R444', 'Q401'), ('2', 'R544', 'Q501')):
    a = h.pad(r, 2); b = h.pad(q, 1)
    h.force('/USB Port %s/HG1' % p, 'F.Cu', [(b[0], b[1]), (b[0], b[1] - 0.6), (a[0], a[1] + 0.19), (a[0], a[1])], w=0.2)
# 3: TS port 1: via in TH401 pad 1, In3 under the stage, to the TS via at R4xx
n = '/USB Port 1/TS'; a = h.pad('TH401', 1); v = (round(a[0], 3), round(a[1], 3))
assert h.via_free(n, *v); h.via(n, *v)
OK['TS1'] = h.route(n, v, (119.125, 111.575), layers=('In2.Cu', 'In3.Cu', 'B.Cu'), margin=6.0)
# 4: TS port 2: no via fits in TH501 pad 1 (In3 AC_SNS_N Kelvin track under it, In2 CHG_INT); via just up-left of the pad
n = '/USB Port 2/TS'; a = h.pad('TH501', 1); v = (87.84, 96.66)
h.via(n, *v); h.force(n, 'F.Cu', [v, (a[0], a[1])], w=0.2)
OK['TS2'] = h.route(n, v, (88.825, 114.075), w=0.15, margin=6.0)   # 0.2 finds no way through the stage
# 5: SW2 port 2: via in U503 pin 18 needs the B.Cu DRV_SUP diagonal out of the way: drop it, lay the via, re-lay it
d = '/USB Port 2/DRV_SUP'; n = '/USB Port 2/SW2'
h.drop(d, 'B.Cu', [89.3, 107.55, 92.0, 110.1])            # diagonal + its 0.2 mm lead-in + the stub to the via (re-laid next line)
h.via(d, 90.875, 107.7745); h.force(d, 'B.Cu', [(89.375, 107.6745), (90.775, 107.6745), (90.875, 107.7745)], w=0.2)
e = (90.55, 109.25); h.via(n, *e)
OK['DRV_SUP'] = h.route(d, (90.875, 107.7745), (91.875, 109.97), layers=('B.Cu',), margin=3.0)
s = h.pad('C513', 2)
OK['SW2'] = h.route(n, (s[0], s[1]), e, margin=5.0)
for k, v in OK.items(): print(k, v)
h.save('/home/claude/prompt-to-functional-pcba/docs/layout-teams/F/routes/stage.json')
