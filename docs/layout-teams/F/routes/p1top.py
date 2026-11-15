import sys, time; sys.path.insert(0, '/home/claude/prompt-to-functional-pcba/docs/layout-teams/F/tools')
from ml import ML
from shapely.geometry import box as sbox
h = ML('/home/claude/runs/c_p1top', 'g1')
P1 = '/USB Port 1/'; LDO = '/P1_LDO_3V3'
def hard(net, excl=None, only=None):
    """hard copper of a net per layer (pads, vias, tracks), optionally outside / inside a box"""
    out = {}
    for L in h.items:
        for g, n, k, name in h.items[L]:
            if n != net or k not in ('pad', 'via', 'track'): continue
            if excl is not None and g.intersects(excl): continue
            if only is not None and not g.intersects(only): continue
            out.setdefault(L, []).append(g)
    return out
def T(label, f):
    t = time.time(); r = f(); print('%s: %s (%.0fs)' % (label, 'ok' if r else 'FAIL', time.time() - t)); 
    if r: print('   ', r)
    return r

CHG = P1 + 'CHG_INT'; SBU = P1 + 'SBU_FLT'; VB = P1 + 'VBUS'
# ---- drops first (a drop resets the obstacle map)
# P1_LDO_3V3 F.Cu track U402.8 -> C408.1 walls in U401.9 (SCL): dropped, C408.1 gets a via in the pad instead
h.drop(LDO, 'F.Cu', [104.1, 84.05, 106.4, 84.5])
# CHG_INT via (109.42, 84.57) sits between R403.1 and R441.1 (P1_LDO_3V3): moved 0.3 up to (109.45, 84.25)
h.drop(CHG, 'F.Cu', [109.0, 83.3, 109.8, 84.7]); h.drop(CHG, None, [109.3, 84.4, 109.6, 84.7])

# all fixed vias first so that every route sees them
h.via(VB, 107.05, 79.22); h.via(VB, 104.1, 69.17); h.via(SBU, 103.98, 70.07); h.via(SBU, 110.1, 84.02)

# 1. GND via just misses U405 pad 18: stub
h.force('GND', 'F.Cu', [(103.45, 73.87), (103.80, 74.02)], w=0.15)

# 6a. SCL escape: stub down between the SDA and IRQ_N vias, via where the LDO track was
h.force('SCL', 'F.Cu', [(105.59, 83.065), (105.58, 83.4), (105.58, 83.95), (105.5, 84.25)], w=0.15)
assert h.via_free('SCL', 105.5, 84.25); h.via('SCL', 105.5, 84.25)
SV = (105.5, 84.25)

# 5a. CHG_INT re-laid: pad 18 -> new via, In3 link to the old In3 track end
h.force(CHG, 'F.Cu', [(109.19, 83.065), (109.19, 83.45), (109.45, 83.75), (109.45, 84.25)], w=0.15)
assert h.via_free(CHG, 109.45, 84.25); h.via(CHG, 109.45, 84.25)
h.force(CHG, 'In3.Cu', [(109.45, 84.25), (109.425, 84.575)], w=0.2)

# 7. VBUS pieces: via in U401.32 -> C450.1 via ; via in J401.A9 -> VBUS copper
T('VBUS U401.32', lambda: h.try_route(VB, (107.05, 79.22), (106.885, 76.575), w=0.25, layers=('In2.Cu', 'In3.Cu', 'B.Cu')))
T('VBUS J401.A9', lambda: h.try_route(VB, (104.1, 69.17), (108.9, 69.17), w=0.25, layers=('In2.Cu', 'In3.Cu', 'B.Cu', 'F.Cu')))

# 2. P1_LDO_3V3: C408.1 -> R402.1 along the top of the AC_SNS_N pour lobe (the pour edge refills 0.15 mm lower),
#    R403.1 -> R441.1 under the moved CHG_INT via, and a via in C408.1 that feeds the group from the inner layers
h.force(LDO, 'F.Cu', [(106.2, 84.3), (106.2, 84.73), (107.6, 84.73)], w=0.15)
h.force(LDO, 'F.Cu', [(108.79, 84.72), (109.75, 84.72), (109.95, 84.665), (110.1, 84.665)], w=0.15)
LV = (106.15, 84.4); assert h.via_free(LDO, *LV); h.via(LDO, *LV)
T('LDO feed', lambda: h.route(LDO, LV, (104.425, 79.7745), layers=('In2.Cu',)))

# 4. SBU_FLT: via below J401.A9 (the VBUS pour blob under that pad refills round it), via in R441.2
h.force(SBU, 'F.Cu', [(103.4, 71.22), (103.4, 70.72), (103.62, 70.5), (103.98, 70.14), (103.98, 70.07)], w=0.15)
T('SBU long', lambda: h.try_route(SBU, (103.98, 70.07), (110.1, 84.02), layers=('In2.Cu', 'In3.Cu', 'B.Cu')))

# 5b. CHG_INT: R404.2 -> new via
T('CHG_INT', lambda: h.try_route(CHG, h.pad('R404', 2)[:2], (109.45, 84.25)))

# 6b. SCL long part: U401.9 via -> via X (107.65, 115.375) -> R304.2. X is the only spot where the copper reachable
#     from Port 1 and the copper reachable from the MCU's SCL overlap; the F.Cu FET_MID pour edge refills 0.3 mm back there
SX = (107.65, 115.375); h.via('SCL', *SX)
T('SCL north', lambda: h.route('SCL', SV, SX, w=0.15, layers=('In2.Cu', 'In3.Cu', 'B.Cu'), margin=25.0))
SOUTH = hard('SCL', only=sbox(100, 116.5, 121, 134))
T('SCL south', lambda: h.route('SCL', SX, (112.525, 124.875), w=0.15, margin=8.0, goal_geoms=SOUTH))
h.force('SCL', 'In3.Cu', [(107.85, 125.674), (107.93, 125.77)], w=0.15)

# 3. 3V3 island of Port 1 (C403.1, U401.38, In3 pour piece) -> nearest 3V3 hard copper outside it
C3 = (103.845, 77.875)
T('3V3', lambda: h.route('3V3', C3, (81.225, 81.09), w=0.2, margin=12.0, layers=('In2.Cu', 'In3.Cu')) or h.route('3V3', C3, (81.225, 81.09), w=0.2, margin=12.0, layers=('In2.Cu', 'In3.Cu', 'B.Cu')))

# 6c. U501.9 (SCL, Port 2) is NOT joined: everything a legal via/track can reach from that pin is one closed pocket
#     (In3 inside the AC_SNS_N'2 / LDO_3V3'2 / IRQ_N tracks, In2 between the GND vias under U501); see the report.
h.ok = True
#--more--
h.save('/home/claude/prompt-to-functional-pcba/docs/layout-teams/F/routes/p1top.json')
