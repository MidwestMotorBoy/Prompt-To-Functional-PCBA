import sys, math
T = '/home/claude/prompt-to-functional-pcba/tools/battery-bank/'
sys.path[:0] = [T + 'groundup/compare', T + 'review-tools']
import loops
d = 0.27875 - 0.035
for h in (0.5, 0.25):
    o, _m = loops.hot_loop('plates', (8, 32, 8, 22), 'P', ['C1'], 'Q1', ['1'], ['2'], h=h)
    print('h %.2f branches %d  L(C1 loop) = %.4f nH' % (h, o['branches'], o['caps']['C1'] * 1e9))
for l in (19.0, 20.0):
    print('hand, wide-plate limit mu0*d*l/w, l=%g mm: %.4f nH' % (l, 4e-7 * math.pi * d * 1e-3 * l / 10 * 1e9))
