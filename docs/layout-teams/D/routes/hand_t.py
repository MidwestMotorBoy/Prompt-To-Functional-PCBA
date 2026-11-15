from hand_lib import *
T = '/USB Port 2/TS'
print(via_sites(T, (87.6, 96.6, 89.0, 98.2)))
g = Point(88.29, 97.31).buffer(0.225)
for l in SIG: print(l, viol(T, g, l))
print([k.bounds for k in m.ko_v if k.buffer(0.3).contains(Point(88.29, 97.31))])
