import json, sys
sys.path.insert(0, '.')
from seglib import *
d = json.load(open('new/cus0.json')); spec = []; add = []
def kill(net, L, box):
    it, ex = dels(d, net, L, lambda t: inbox(t, box)); spec.extend(it); add.extend(readd(ex))
    print(net, L, len(it), 'del points; collateral re-added', len(ex))
def kv(net, box):
    vs = vias(d, net, box); spec.extend(delvia(v) for v in vs); print(net, 'vias removed', [(v['x'], v['y']) for v in vs])
# ---- port 2 FB: R518 now sits at the FB pin
kv('Net-(U503-FB)', None); kill('Net-(U503-FB)', 'In2', (80, 100, 100, 120))
kv('PACK_P', (93.3, 108.4, 93.6, 108.8)); kill('PACK_P', 'F', (93.3, 108.4, 93.6, 108.9)); kill('PACK_P', 'B', (93.3, 107.6, 95.4, 108.8))
pv = [v for v in d['vias'] if v['net'] == 'PACK_P' and abs(v['x'] - 93.85) < 0.3 and abs(v['y'] - 113.65) < 0.3][0]; print('R113 PACK_P via', pv['x'], pv['y'])
add += [{"net": "Net-(U503-FB)", "layer": "F", "w": 0.2, "pts": [[92.4, 113.85], [91.625, 113.85]]},
        {"net": "PACK_P", "layer": "F", "w": 0.2, "pts": [[93.42, 113.85], [pv['x'], pv['y']]]}]
# ---- port 1 FB: R418 moved 0.9 mm east
kv('Net-(U403-FB)', (115.3, 108.8, 115.7, 109.2)); kill('Net-(U403-FB)', 'F', (115.3, 108.6, 115.7, 109.2)); kill('Net-(U403-FB)', 'In2', (115.3, 108.9, 116.45, 110.3))
# pcbnew re-netted the two PACK_P vias and their tracks under the moved FB pad to the FB net: one stays as the FB via, the rest goes
kv('Net-(U403-FB)', (116.1, 108.9, 116.3, 109.2)); kill('Net-(U403-FB)', 'F', (116.3, 108.3, 116.7, 108.9)); kill('Net-(U403-FB)', 'B', (116.1, 107.2, 116.8, 109.2))
add += [{"net": "Net-(U403-FB)", "layer": "In2", "w": 0.2, "pts": [[116.475, 108.4745], [116.85, 108.85], [116.85, 110.05], [116.625, 110.2745], [116.425, 110.2745]]},
        {"net": "PACK_P", "layer": "F", "w": 0.2, "pts": [[117.41, 108.75], [118.6, 108.75]]}]
# ---- EN_5V1 past the port 1 charger: no crossing of the SW2 track on In3
kill('EN_5V1', 'In2', (111.5, 100.7, 115.4, 110.5))
add += [{"net": "EN_5V1", "layer": "In2", "w": 0.15, "pts": [[115.325, 100.7745], [115.325, 103.2], [112.65, 103.2], [112.65, 105.0], [112.0, 105.65], [112.0, 107.1], [112.45, 107.55], [112.45, 109.2], [112.65, 109.4], [112.65, 110.4745], [111.625, 110.4745]]}]
# ---- EN_5V1 at the 5 V buck: via away from the SW pin (link by ml.py afterwards)
kv('EN_5V1', (115.3, 83.8, 115.7, 84.3)); kill('EN_5V1', 'F', (114.6, 83.9, 115.6, 84.8)); kill('EN_5V1', 'In2', (115.3, 83.9, 116.0, 87.6))
# ---- SBU_FLT via away from the inductor pad
kv('SBU_FLT', (93.5, 83.3, 93.9, 83.7)); kill('SBU_FLT', 'In2', (93.5, 73.5, 93.9, 83.7))
add += [{"net": "/USB Port 2/SBU_FLT", "via": [94.2, 83.5245]}, {"net": "/USB Port 2/SBU_FLT", "layer": "In3", "w": 0.2, "pts": [[93.675, 83.5245], [94.2, 83.5245]]},
        {"net": "/USB Port 2/SBU_FLT", "layer": "In2", "w": 0.2, "pts": [[94.2, 83.5245], [94.2, 83.3], [93.675, 82.775], [93.675, 73.6245]]}]
# ---- port 1 I2C clock: away from the BST via under the port 2 5 V buck
kill('Port 1/I2CC_SCL', 'In2', (94.1, 84.8, 94.5, 88.2))
add += [{"net": "/USB Port 1/I2CC_SCL", "layer": "In2", "w": 0.15, "pts": [[94.375, 84.9245], [94.375, 85.0], [94.7, 85.325], [94.7, 86.95], [94.275, 87.375], [94.225, 87.45], [94.225, 88.1245]]}]
# ---- TS4: whole detour through both stages removed (direct link by ml.py afterwards)
T = '/Cells and Gauge/TS4'
for v in d['vias']:
    if v['net'] == T and not (abs(v['x'] - 97.025) < 0.01): spec.append(delvia(v))
for L in ('In2', 'In3', 'B'): kill('Gauge/TS4', L, (0, 0, 200, 200))
json.dump(spec + add, open('hand3/s1.json', 'w'), indent=0)
for a in add: print(a if 'via' in a else (a['net'], a['layer'], a['pts'][0], a['pts'][-1]))
