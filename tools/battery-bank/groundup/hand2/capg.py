"""capg.py -> spec: ground strap from each moved 100 nF capacitor to the source pads of its FET"""
import json
S = []
for dx in (0.0, 23.026):
    for x0 in (0.0, 4.5):
        S.append({"net": "GND", "layer": "F", "w": 0.4, "pts": [[round(x + x0 + dx, 3), y] for x, y in ((86.04, 97.32), (85.6, 97.76), (85.15, 97.95), (84.9, 98.4), (84.9, 98.83))]})
print(json.dumps(S))
