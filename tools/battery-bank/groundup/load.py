import sx, pickle, sys
t=open('/home/user/Battery-Bank/hardware/Production/Monolith.kicad_pcb',newline='').read()
b=sx.parse(t)
pickle.dump(b,open('board.pkl','wb'))
from collections import Counter
print(Counter(c[0] for c in b if isinstance(c,list)))
