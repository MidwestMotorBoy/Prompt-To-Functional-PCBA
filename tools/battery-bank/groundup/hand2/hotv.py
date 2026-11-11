"""hotv.py -> spec: ground vias in the source pads of the four charger FETs and beside the 100 nF capacitors (both ports)"""
import json
S = []
for dx in (0.0, 23.026):
    for x0 in (84.9, 89.4):                       # Q501 / Q502 source pads 5, 6, 7
        for y in (98.83, 99.47, 100.125): S.append({"net": "GND", "via": [round(x0 + dx, 3), y]})
    S.append({"net": "GND", "via": [round(92.75 + dx, 3), 98.05]})      # under C538 pad 2
print(json.dumps(S))
