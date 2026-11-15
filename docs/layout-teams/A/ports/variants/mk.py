"""mk.py <name>: build a ports variant on top of lead_merge/merged3_gu.json. Each variant is a list of moves below
(ref, x, y, abs_rot) with the reason; variants can build on each other with 'base'."""
import sys; sys.path.insert(0, '/home/claude/repo/docs/layout-teams/A/ports/tools'); import pf
V = {
 # pdfix a4 (never scored): lane west of R541 0.2 mm wider (R541/R504 0.1 east, U502 0.1 west), SDA pull-up R502 back
 # near its merged spot (a3 moved it and R502->U503 got blocked), SCL pull-up R503 west of it.
 'b1': dict(base=None, mv=[('U502', 84.4, 86.5, 90), ('C508', 82.3, 84.7, 0), ('R541', 86.6, 84.25, 90), ('R504', 86.5, 85.9, 90),
                          ('R502', 82.2, 86.8, 90), ('R503', 81.3, 86.8, 90)]),
 # port 2 PP5V crosses the VBUS stem on a B.Cu detour from C507.1 to C541.1 at y ~77.6, grown to y 79.3 right above
 # U501 pins 26-31: no via site for CC1/CC2 (28/29). C507 1.5 mm north moves the detour north.
 'b2': dict(base='b1', mv=[('C507', 83.5, 75.45, 90)]),
 # b2 opened PP5V at U501 (pin 34 lost its copper). Half the move:
 'b3': dict(base='b1', mv=[('C507', 83.5, 76.45, 90)]),
 # port 2 protector: J501's A4/B9 VBUS stub sits over U505 pins 3-4; pdfix a2 (0.35 S) freed VBIAS. 0.2 mm more south,
 # with the CC/LDO caps below it 0.2 mm south too (C542/C543 courtyards 0.1 mm below them).
 'b4': dict(base='b1', mv=[('U505', 95.75, 73.85, -90), ('C552', 94.6, 77.2, -90), ('C502', 95.62, 77.1, -90), ('C501', 96.64, 77.1, -90)]),
 # U505 0.4 mm west (pins 3-5 further from the A4/B9 stub at x 95.9; H102 courtyard 0.05 mm away)
 'b5': dict(base='b1', mv=[('U505', 95.35, 73.65, -90)]),
}
def build(name):
    v = V[name]; P = build(v['base']) if v['base'] else pf.load()
    for r, x, y, rot in v['mv']: P[r] = [x, y, rot]
    return P
if __name__ == '__main__':
    name = sys.argv[1]; P = build(name); e = pf.check(P); print('check', e)
    g, s, ov = pf.save(P, name); print(g, s, len(ov), 'changed vs merged3')
