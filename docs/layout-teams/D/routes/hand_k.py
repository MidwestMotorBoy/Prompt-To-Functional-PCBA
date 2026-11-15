"""Eighth hand pass, on board j1: Port 1 charger enable (U403.7 -> R435 / R417).   HB=j1 python3 hand_k.py"""
from hand_lib import *
P1 = '/USB Port 1/'; CE = P1 + 'CE_N'; CG = '/Cells and Gauge/'
ok = cross2(CE, depth=3, r=1.5)
if not ok:
    ok = group([CE, CG + 'CHG', CG + 'CHG_INH'], (102.0, 112.5, 114.0, 118.0), maxtry=6)
if not ok:
    ok = group([CE, P1 + 'I2CC_SCL', CG + 'CHG_INH', CG + 'CHG'], (102.0, 112.5, 112.0, 118.0), maxtry=24)
st(CE); why(CE, margin=12.0)
m.save('hand_k.json')
