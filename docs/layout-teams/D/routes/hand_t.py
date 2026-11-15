from hand_lib import *
import json
P = json.load(open('/home/claude/runs/r2_route/e1.kicad_pro'))
print('min track', P['board']['design_settings']['rules'].get('min_track_width'), 'min clearance', P['board']['design_settings']['rules'].get('min_clearance'))
bx = sbox(106.5, 116.6, 110.8, 118.6)
for g, n, k, nm in m.items['F.Cu']:
    if g.intersects(bx) and k != 'pour': print(n.split('/')[-1], k, nm, [round(v, 3) for v in g.bounds])
