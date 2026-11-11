"""netdiff.py a.kicad_pcb b.kicad_pcb (KiCad python): tracks / vias whose net differs between two boards (matched by id), and items only in one."""
import sys, pcbnew
M = pcbnew.ToMM
A = {t.m_Uuid.AsString(): t for t in pcbnew.LoadBoard(sys.argv[1]).GetTracks()}
B = {t.m_Uuid.AsString(): t for t in pcbnew.LoadBoard(sys.argv[2]).GetTracks()}
n = 0
for u, t in A.items():
    if u in B and B[u].GetNetname() != t.GetNetname():
        n += 1; p = t.GetPosition(); print(t.GetClass(), '%.3f,%.3f' % (M(p.x), M(p.y)), t.GetNetname(), '->', B[u].GetNetname())
print('changed', n, 'only in a', len(set(A) - set(B)), 'only in b', len(set(B) - set(A)))
