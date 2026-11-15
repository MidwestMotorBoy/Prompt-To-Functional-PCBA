import sys; sys.path.insert(0, '/home/claude/prompt-to-functional-pcba/docs/layout-teams/F/tools')
from ml import ML
h = ML('/home/claude/runs/c_p2top', 'g1')
P2 = '/USB Port 2/'
F = ('F.Cu',); INNER = ('In2.Cu', 'In3.Cu', 'B.Cu')
R = {}
def rt(tag, *a, **k):
    R[tag] = h.route(*a, **k); print(tag, R[tag]); return R[tag]

# ---- 1. CC1: U501.28 is shut in by the CC2 track (runs right above it) and the GND track pin 27 -> via (86.65, 79.67)
h.drop('GND', 'F.Cu', [86.0, 79.6, 86.7, 80.55])                 # track + vias (86.35, 80.475), (86.65, 79.674)
h.via('GND', 86.35, 80.475)                                      # back (in pad 26); (86.65, 79.674) stays out
h.force('GND', 'F.Cu', [(86.0, 80.675), (86.4, 80.675)], w=0.2)  # pin 27 to pin 26 and its via
h.drop(P2 + 'CC2', 'F.Cu', [85.1, 78.4, 86.0, 80.7])             # CC2 pin 29 -> cap pad, + via (85.95, 78.874)
h.via(P2 + 'CC2', 85.95, 78.874)
h.force(P2 + 'CC2', 'F.Cu', [(85.95, 78.874), (85.9, 78.825), (85.75, 78.6)], w=0.2)
h.force(P2 + 'CC2', 'F.Cu', [(85.2, 80.675), (85.2, 79.35), (85.75, 78.8), (85.75, 78.6)], w=0.15)
rt('CC1', P2 + 'CC1', (85.6, 80.675), (87.7, 79.575), w=0.15, layers=F)

# ---- 2..4. south row: the SBU_FLT F track + its two jog vias wall pins 16, 17, 18
h.drop(P2 + 'SBU_FLT', 'F.Cu', [84.9, 84.4, 86.5, 85.3])
h.force(P2 + 'SBU_FLT', 'In3.Cu', [(85.0, 85.174), (85.051, 85.225), (85.65, 85.225)], w=0.15)   # jog now on In3
h.force(P2 + 'I2CC_SCL', 'F.Cu', [(85.6, 84.525), (85.6, 86.63)], w=0.15)
rt('SDA', P2 + 'I2CC_SDA', (85.2, 84.525), (84.625, 86.6245), w=0.15, layers=F)
rt('CHG', P2 + 'CHG_INT', (86.0, 84.525), (86.225, 86.4745), w=0.15, layers=F)
# SBU pin 19 to its via at the pull-up; passes 0.03 from the AC_SNS_N pour edge, which refills back
h.force(P2 + 'SBU_FLT', 'F.Cu', [(86.4, 84.525), (86.4, 85.75), (86.85, 86.2), (87.0, 86.374)], w=0.15)

# ---- 2b. I2CC_SCL to U502.6: the B.Cu DRV9_OFF track leaves no via spot in the pocket east of the pad -> move it west
h.drop(P2 + 'DRV9_OFF', 'B.Cu', [94.3, 79.3, 95.6, 84.5]); h.via(P2 + 'DRV9_OFF', 94.925, 79.4245)
scl_goal = {'In2.Cu': [g for g, n, k, nm in h.items['In2.Cu'] if n == P2 + 'I2CC_SCL' and k == 'track' and g.bounds[0] > 89 and g.bounds[1] > 79]}
print(len(scl_goal['In2.Cu']), 'SCL In2 goal tracks')
for w in (0.2, 0.15):
    if rt('SCL2', P2 + 'I2CC_SCL', (94.35, 81.1), (91.025, 83.8745), w=w, goal_geoms=scl_goal, layers=('F.Cu', 'In2.Cu', 'In3.Cu')): break
for w in (0.2, 0.15):
    if rt('DRV9', P2 + 'DRV9_OFF', (94.925, 79.4245), (94.475, 84.3745), w=w, layers=('B.Cu',)): break

# ---- 7. 3V3: the In3 track from the pin ends short of the 3V3 pour; no via is legal there (U501 pad on F), so the
#         track goes on between two thermal vias into the pour
h.drop('3V3', 'In3.Cu', [82.3, 83.1, 82.45, 83.5])                # old dead-end stub
h.force('3V3', 'In3.Cu', [(82.375, 83.1745), (82.45, 83.14), (83.8, 83.14)], w=0.15)

# ---- 6. GND: U504.1 has no via
rt('GND', 'GND', (81.56, 68.85)) if False else print('GND', h.plane('GND', (81.56, 68.85)))

# ---- 5. VBUS pieces. U501.32: via in the pad, then B.Cu / inner to the VBUS vias at C550
h.via(P2 + 'VBUS', 83.8, 80.675)
for w in (0.3, 0.25, 0.2):
    if rt('VBUS32', P2 + 'VBUS', (83.8, 80.675), (87.35, 80.674), w=w, layers=INNER): break
# J501 right pins (A4/B9) piece to the left piece (A9/B4)
# link 1: no via spot is legal outside the pad on the right side (checked 1.5 mm round), so one via in pad A4/B9
h.via(P2 + 'VBUS', 95.9, 69.45); h.via(P2 + 'VBUS', 91.05, 70.65)
h.force(P2 + 'VBUS', 'F.Cu', [(91.0161, 70.1244), (91.05, 70.65)], w=0.4)
for w in (0.5, 0.4, 0.3):
    if rt('VBUSJ', P2 + 'VBUS', (95.9, 69.45), (91.05, 70.65), w=w, layers=('In2.Cu',), margin=3): break
# link 2 (C506 via to D501, lower end) was tried at 0.5 / 0.4 / 0.3: no path
h.save('/home/claude/prompt-to-functional-pcba/docs/layout-teams/F/routes/p2top.json')
