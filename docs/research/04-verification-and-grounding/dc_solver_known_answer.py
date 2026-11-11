import sys
sys.path.insert(0, '/home/claude/prompt-to-functional-pcba/tools/battery-bank/review-tools')
from solve import *
for res in (0.1, 0.05):
    B = build('N', (5, 65, 15, 25), res)
    s = padnodes(B, 'R1', ['1']); k = padnodes(B, 'R2', ['1'])
    V, R = solve(B, s, k)
    print('res %.2f nodes %d  R = %.4f mOhm' % (res, B['n'], R * 1e3))
print('hand: 2 oz sheet 0.246 mOhm/sq; 49 mm between pad inner edges / 2 mm = 24.5 sq -> %.4f mOhm; +1/3 mm for spread source -> %.4f' % (24.5 * 0.246, (24.5 + 1/6) * 0.246))
