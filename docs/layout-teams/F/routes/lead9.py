import sys; sys.path.insert(0, 'tools')
from rip import RML
h = RML('/home/claude/runs/rt4', 'm9'); print("pruned", h.prune()); h.save('routes/lead9.json')
