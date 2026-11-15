"""pf.py: placement patch helpers for worker ports (run with any cwd).
P = {ref: [x, y, abs_rot]} (groundup format). Courtyard/peg/edge check through stage/placelib.check.
  load(path)             -> P
  pads(P, ref)           -> {num: (x, y, net)} world pad centres
  bb(P, ref)             -> courtyard box
  check(P, refs=None)    -> errors that involve refs (default: all)
  save(P, name, base)    -> variants/<name>_gu.json, <name>_score.json, <name>_ov.json (refs that differ from base)"""
import os, sys, json, subprocess, contextlib
A = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))      # docs/layout-teams/A
ST = os.path.join(A, 'stage'); PF = os.path.join(A, 'ports')
sys.path.insert(0, ST)
with contextlib.redirect_stdout(open(os.devnull, 'w')):
    _cwd = os.getcwd(); os.chdir(ST); import placelib; os.chdir(_cwd)
MERGED = os.path.join(A, 'lead_merge', 'merged3_gu.json')
def load(path=MERGED): return {k: list(v) for k, v in json.load(open(path)).items()}
def pads(P, ref):
    w = placelib.db.world(ref, *P[ref]); return {p['n']: (round(p['x'], 3), round(p['y'], 3), p['net']) for p in w['pads']}
def bb(P, ref): return [round(v, 3) for v in placelib.db.world(ref, *P[ref])['bb']]
def check(P, refs=None):
    e, m = placelib.check(P, verbose=False)
    if refs is not None: e = [x for x in e if any(r in x.replace('/', ' ').split() for r in refs)]
    return e
def save(P, name, base=MERGED):
    B = json.load(open(base)); os.makedirs(os.path.join(PF, 'variants'), exist_ok=True)
    g = os.path.join(PF, 'variants', name + '_gu.json'); s = os.path.join(PF, 'variants', name + '_score.json')
    json.dump(P, open(g, 'w'), indent=0)
    ov = {r: P[r] for r in P if [round(v, 4) for v in P[r]] != [round(v, 4) for v in B[r]]}
    json.dump(ov, open(os.path.join(PF, 'variants', name + '_ov.json'), 'w'), indent=0)
    subprocess.run(['python3', os.path.join(A, 'rebuild/gu/gu_to_score.py'), g, s, os.path.join(A, 'rebuild/runs/v5_build/base.json')], check=True, capture_output=True)
    return g, s, ov
