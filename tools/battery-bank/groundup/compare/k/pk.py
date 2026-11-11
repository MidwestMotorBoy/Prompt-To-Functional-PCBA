"""pk.py: PACK_P Q102 -> RBAT resistance of both ports only (quick check after a hand edit). PCB=board [PNG=prefix for current-density pictures]"""
import os
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lossmap.py')).read().split("res={'paths':{}}")[0]
exec(src.replace("RES=0.1", "RES=float(os.environ.get(\"RES\", \"0.1\"))"))
for p in (1, 2):
    h = str(p + 3); R, Pm, per = path('PACK_P', 'Q102', ['1', '2', '3'], f'R{h}27', ['2'])
    print(f'P{p} PACK_P Q102 to RBAT: {R*1e3:.2f} mOhm', {L[:3]: round(v / R * 100) for L, v in per.items() if v / R > 0.02}, flush=True)
    if os.environ.get('PNG'):
        import numpy as np
        from PIL import Image
        a = np.log10(Pm + 1e-12); a = np.clip((a - a.max() + 4) / 4, 0, 1); Image.fromarray((a * 255).astype('uint8')).resize((Pm.shape[1] * 2, Pm.shape[0] * 2)).save(os.environ['PNG'] + f'_p{p}.png'); np.save(os.environ['PNG'] + f'_p{p}.npy', Pm.astype('float32'))
