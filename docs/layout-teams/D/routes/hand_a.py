from hand_lib import *
# FB at U403.12: the SRN_F branch to C419.1 walls it. Pull that branch, lay FB on F, pull FB's In2 run, re-lay SRN_F, re-lay FB.
S = '/USB Port 1/SRN_F'; FB = 'Net-(U403-FB)'
m.rip_tracks(S, 'F.Cu', (115.7, 111.0, 121.2, 113.7))
joinall(FB)
m.rip_tracks(FB, 'In2.Cu', (116.5, 110.3, 120.0, 112.1)); st(FB)
joinall(S); joinall(FB); why(S); why(FB)
# stage 2: pull the In2 pack strap, close what it walled, strap back afterwards
m.rip_tracks('PACK_P', 'In2.Cu', (98, 104, 121, 121))
OPEN = ['/USB Port 1/CE_N', '/USB Port 1/CHG_INT', '/USB Port 1/I2CC_SDA', '/USB Port 2/CHG_INT', '/USB Port 2/I2CC_SDA', '/USB Port 2/TS', 'IRQ_N', 'SDA', '/Cells and Gauge/CELL_P', '3V3']
for n in OPEN:
    joinall(n, margin=9.0); why(n, margin=9.0)
# stage 3: pin escapes walled by the neighbour pin's track
P1, P2 = '/USB Port 1/', '/USB Port 2/'
swap(P1 + 'I2CC_SDA', [P1 + 'I2CC_SCL'], (105.5, 82.0, 111.5, 88.0))
group([P1 + 'CHG_INT', P1 + 'I2CC_SDA', P1 + 'I2CC_SCL'], (107.5, 112.0, 113.0, 117.0))
# Port 2 charger pins 1-3 (SCL, SDA, CHG_INT): hand fan-out, straight out of each pin to staggered vias; REGN's In2 run moves aside
SDA2, SCL2, CI2, RG2 = P2 + 'I2CC_SDA', P2 + 'I2CC_SCL', P2 + 'CHG_INT', P2 + 'REGN'
for v in (SDA2, SCL2, CI2): rip_box(v, (83.0, 110.0, 89.0, 116.5))
rip_box(RG2, (86.0, 106.7, 88.0, 116.0))
stub(SCL2, [(85.56, 113.0), (85.6, 113.2), (85.6, 114.25)])
stub(SDA2, [(86.06, 113.0), (86.08, 113.65)])
stub(CI2, [(86.56, 113.0), (86.56, 113.95), (86.42, 114.25)])
for v in (SCL2, CI2, RG2, SDA2): joinall(v, margin=9.0)
# CE_N at U403.7: hand escape west under the unused pins 6..4 to a via clear of TS4 (B) and ICHG (In2)
CE = P1 + 'CE_N'
stub(CE, [(113.19, 113.0), (113.19, 113.45), (113.09, 113.55), (112.2, 113.55)])
print('via sites west', via_sites(CE, (102.0, 113.3, 105.6, 116.2))[:60])
BX = (95.0, 111.5, 109.5, 119.0)
group([CE, P1 + 'I2CC_SDA'], BX) or group([CE, P1 + 'I2CC_SDA', '/Cells and Gauge/CHG'], BX) or group([CE, P1 + 'I2CC_SDA', 'EN_5V1', 'CHG_INH'], BX)
# Port 2 PD chip pin 18 (CHG_INT): the LDO_3V3 via sits right under the pin
escape_try(CI2, (87.6, 84.3), [P2 + 'LDO_3V3'], (85.0, 82.0, 89.5, 86.5), (87.2, 84.5, 89.2, 86.3))
# Port 2 thermistor pad: the only legal via spot is at the pad's north-west corner
TS2 = P2 + 'TS'
stub(TS2, [(88.29, 97.31), (88.0, 96.95)]); joinall(TS2, margin=9.0); why(TS2, margin=9.0)
# the two bus lines from the PD chips down to the MCU
ALL = (60.0, 60.0, 130.0, 140.0); GF, HG = '/Cells and Gauge/GAUGE_FUSE', P1 + 'HIDRV1'
swap('IRQ_N', [HG], ALL, margin=12.0)
AO = 'Net-(U403-ACOV)'
CB = (103.0, 99.5, 109.2, 113.6)
def multi(stuck, rips, margin=12.0):
    s = snap(); print('multi', stuck, [(v.split('/')[-1], bx) for v, bx in rips])
    for v, bx in rips: rip_box(v, bx)
    vs = list(dict.fromkeys(v for v, bx in rips))
    joinall(stuck, margin=margin)
    for v in vs: joinall(v, margin=margin)
    if one(stuck) and all(one(v) for v in vs): return True
    why(stuck, margin=margin)
    for v in vs: why(v, margin=margin)
    restore(s); print('  undone'); return False
K = (110.2, 116.2, 112.6, 117.7); CB = (104.3, 107.9, 109.2, 113.6)
multi('SDA', [('3V3', K)]) or multi('SDA', [('3V3', K), ('3V3', CB), (AO, CB)]) or multi('SDA', [('3V3', K), (HG, ALL)])
for n in OPEN: st(n)
m.save('hand_a.json')
