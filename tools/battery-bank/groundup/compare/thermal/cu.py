"""Routed-board copper losses (Layout-P0, 2026-10-30) added to the p0f model.
cu_losses.json: per port, battery-side copper (PACK_P Q102->RBAT, BAT_SNS_P RBAT->leg B, GND RS101->stage) and USB-side
copper (VBUS J->TPS25751, PPHV, AC_SNS_N RAC->leg A) as resistance plus 2 mm loss tiles from the DC grid solver."""
import os, sys, json, time
os.environ.setdefault('SMD_LAYOUT', 'p0f')
import numpy as np
import smd as S
P, N = S.P, S.N
HERE = os.path.dirname(os.path.abspath(__file__))
CU = json.load(open(os.environ.get('CU_JSON', os.path.join(HERE, 'cu_losses.json'))))
R_REF = 1e-3
DROP = float(os.environ.get('CU_DROP', '0'))
ON = [False]
_ob, _ol, _bw = P.src_boxes, P.port_loss, P.Grid.box_weights
def bw(self, boxes):
    if boxes and len(boxes[0]) == 7:
        w = 0.0
        for b in boxes: w = w + _bw(self, [b[:6]]) * b[6]
        return w
    return _bw(self, boxes)
P.Grid.box_weights = bw
def boxes():
    b = _ob()
    for p in (1, 2):
        for k in ('cub', 'cuu'):
            d = CU[f'{k}{p}']; tl = d['boxes']
            if DROP: tl = [t for t in tl if np.hypot(abs((t[0] + t[1])/2) - 15.5, (t[2] + t[3])/2 - 29.0) > DROP]
            s = d['R'] / R_REF / sum(t[4] for t in tl)       # same total loss, moved off the tiles round TH101 / TH104
            b[f'{k}{p}'] = [(25.3, 26.9, y0, y1, z0, z1, f * s) for y0, y1, z0, z1, f in tl]
    return b
RB = 0.5 * (CU['cub1']['R'] + CU['cub2']['R']); RU = 0.5 * (CU['cuu1']['R'] + CU['cuu2']['R'])
def loss(p_usb, v_usb, v_bus, sink, prm=P.P0):
    L, i_b = _ol(p_usb, v_usb, v_bus, sink, prm); L = dict(L)
    if not ON[0] or p_usb <= 0:
        L.update(cub=0.0, cuu=0.0); return L, i_b
    i_u = p_usb / v_usb
    extra = RB * i_b**2 + RU * i_u**2
    i_b = (p_usb - sum(L.values()) - extra) / v_bus if sink else (p_usb + sum(L.values()) + extra) / v_bus
    L.update(cub=R_REF * i_b**2, cuu=R_REF * i_u**2)        # weights of cub{p} / cuu{p} carry R_port / R_REF
    return L, i_b
P.src_boxes, P.port_loss = boxes, loss
P.CASES['dis100s'] = dict(P.CASES['dis100'], title='100 W out of USB1, first 4.4 min (both at full power)', hours=4.4/60)

def job(spec):
    case, pol, ntc, cu = spec
    ON[0] = cu
    P.DERATE, P.DERATE_HOT, P.CHG_HOT = S.POLICIES[pol]
    g = P.get_grid(); S.use_spot(ntc)
    P.run_case(g, case, verbose=False, tag=f'_cu{int(cu)}{"_drop%g" % DROP if DROP else ""}_{pol}_{ntc}', probes=S.spot_points(), ntc_front=N.SPOT)
    return spec

def pool(specs, n):
    import multiprocessing as mp
    with mp.get_context('spawn').Pool(n, maxtasksperchild=1) as pl:
        for r in pl.imap_unordered(job, specs): print(r, 'done', time.strftime('%H:%M:%S'), flush=True)

if __name__ == '__main__':
    cases = sys.argv[1].split(',') if len(sys.argv) > 1 else ['dis100', 'dis100u2', 'chg1', 'pass']
    cus = [int(c) for c in sys.argv[2].split(',')] if len(sys.argv) > 2 else [0, 1]
    P.get_grid()
    pool([(c, 'd44', 'out29', bool(u)) for u in cus for c in cases], int(os.environ.get('NPROC', '4')))
