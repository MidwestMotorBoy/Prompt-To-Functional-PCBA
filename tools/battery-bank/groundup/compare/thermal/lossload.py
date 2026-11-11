"""Loss at several loads for both boards: the thermal model's part-loss model (same parts on both boards) plus each
board's routed copper (DC grid solver).  Cells at 25 C.  -> lossload_<NTAG>.json"""
import os, json
os.environ['SMD_LAYOUT'] = 'p0f'
import pack3d as P, smd as S
NT = os.environ.get('NTAG', 'new')          # the board compared with the current one
CU = {b: json.load(open(f'cu_{b}.json')) for b in ('base', NT)}
P0 = P.P0
def solve(board, port, mode, p_usb, v_usb, soc, i_chg=4.55):
    cu = CU[board]; RB, RU, RP = cu[f'cub{port}']['R'], cu[f'cuu{port}']['R'], cu['pack']['R']
    rc = 4 * P.r_cell(soc, 25.0); r_path = P0['prot'] + P0['fuse'] + P0['shunt'] + RP + P0['nickel']
    i_bat = 0.0; pw = p_usb
    for _ in range(40):
        v_bus = 4 * P.ocv(soc) - i_bat * (rc + r_path) * (1 if mode == 'src' else -1)
        L, ib = S.p0f_port_loss(pw, v_usb, v_bus, mode == 'snk'); L = dict(L)
        i_u = pw / v_usb
        for _ in range(6):
            extra = RB * ib**2 + RU * i_u**2
            ib = (pw - sum(L.values()) - extra) / v_bus if mode == 'snk' else (pw + sum(L.values()) + extra) / v_bus
        if mode == 'snk': pw = min(p_usb, pw + (i_chg - ib) * v_bus)
        i_bat = ib
    parts = sum(L.values()); pack_parts = (P0['prot'] + P0['fuse'] + P0['shunt'] + P0['nickel']) * i_bat**2
    cells = rc * i_bat**2
    cu_b, cu_u, cu_p = RB * i_bat**2, RU * i_u**2, RP * i_bat**2
    tot = parts + pack_parts + cells + cu_b + cu_u + cu_p
    return dict(board=board, port=port, mode=mode, p_usb=pw, v_usb=v_usb, soc=soc, v_bus=v_bus, i_bat=i_bat, i_usb=i_u,
                stage_parts=parts, pack_parts=pack_parts, cells=cells, cu_batt=cu_b, cu_usb=cu_u, cu_pack=cu_p,
                cu_total=cu_b + cu_u + cu_p, total=tot, parts_detail={k: float(v) for k, v in L.items()})
LOADS = [('15 W, 5 V 3 A', 'src', 15, 5.0), ('27 W, 9 V 3 A', 'src', 27, 9.0), ('45 W, 15 V 3 A', 'src', 45, 15.0), ('60 W, 20 V 3 A', 'src', 60, 20.0),
         ('100 W, 20 V 5 A', 'src', 100, 20.0), ('Charge 4.55 A, 20 V', 'snk', 100, 20.0)]
out = []
for soc in (1.0, 0.5, 0.1):
    for name, mode, pw, vu in LOADS:
        if mode == 'snk' and soc == 1.0: continue
        for port in (1, 2):
            for b in ('base', NT):
                r = solve(b, port, mode, pw, vu, soc); r['load'] = name; out.append(r)
json.dump(out, open(f'lossload_{NT}.json', 'w'), indent=1)
print(f"{'load':22s} soc port   Ibat  Iusb | copper mW  current board : ground-up   (batt/usb/pack)        | all losses W")
for i in range(0, len(out), 2):
    a, b = out[i], out[i+1]
    print(f"{a['load']:22s} {a['soc']*100:3.0f}  P{a['port']}  {a['i_bat']:5.2f} {a['i_usb']:5.2f} | {a['cu_total']*1e3:5.0f} ({a['cu_batt']*1e3:3.0f}/{a['cu_usb']*1e3:3.0f}/{a['cu_pack']*1e3:3.0f}) : {b['cu_total']*1e3:5.0f} ({b['cu_batt']*1e3:3.0f}/{b['cu_usb']*1e3:3.0f}/{b['cu_pack']*1e3:3.0f}) | {a['total']:.2f} : {b['total']:.2f}")
