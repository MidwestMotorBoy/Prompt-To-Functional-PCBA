# port 1 charger controller passives (translated to port 2 at the end)
_before=set(P)
import placelib as _pl
_pl.GHOST[:]=[(b[0]-DX2,b[1],b[2]-DX2,b[3]) for b in (db.world(r,*P[r])['bb'] for r in P if db.fp[r]['layer']=='F.Cu')]
def A(ref,**k):
    auto(P,ref,**k)
# kelvin filter resistors at the battery sense resistor
A('R428',pins={'1':'R427.1'},rots=(0,180),at=(116.6,103.6))
A('R429',pins={'1':'R427.2'},rots=(0,180),at=(116.6,104.7))
A('C417',pins={'1':'U403.14','2':'U403.13'},rots=(90,270),at=(115.6,111.7))
A('C418',pins={'1':'U403.14'},at=(116.3,110.3))
A('C419',pins={'1':'U403.13'},at=(116.3,113.0))
A('R419',pins={'1':'U403.12','2':'U403.11'},at=(115.6,113.6))
A('R418',pins={'2':'U403.12'},at=(116.8,113.6),box=(105.0,103.0,119.3,118.5))
A('C414',pins={'1':'U403.30','2':'U403.29'},rots=(90,270),at=(106.8,109.7))
A('C416',pins={'1':'U403.29'},at=(105.4,109.3))
A('C415',pins={'1':'U403.30'},at=(106.3,110.3))
A('C409',pins={'1':'U403.33'},rots=(0,180),at=(106.8,111.4))
A('R409',pins={'2':'U403.34','1':'C409.1'},at=(107.2,112.4))
A('R410',pins={'1':'U403.34','2':'U403.35'},at=(107.2,113.3))
A('R411',pins={'1':'U403.35'},at=(107.2,114.2))
A('R412',pins={'1':'U403.36'},at=(108.0,115.0))
A('R435',pins={'2':'U403.7'},at=(112.2,115.3))
A('R417',pins={'1':'U403.7'},at=(112.2,116.2))
A('R416',pins={'1':'U403.8'},at=(113.0,115.4))
A('R415',pins={'2':'U403.8'},at=(113.4,116.6))
A('R413',pins={'1':'U403.9'},at=(114.2,115.4))
A('R414',pins={'1':'U403.10'},at=(115.2,115.4))
A('D404',pins={'1':'C412.1','2':'C411.1'},at=(108.2,105.6))
A('D405',pins={'1':'C413.1','2':'C411.1'},at=(114.9,106.4))
A('D410',pins={'1':'C411.1','2':'C410.1'},at=(113.6,104.3))

STAGE1=set(P)-_before
# translate the controller passives to port 2
for r in list(P):
    if re.match(r'[A-Z]+4\d\d$',r) and port2(r) not in P and r in STAGE1:
        x,y,rot=P[r]; P[port2(r)]=(round(x+DX2,3),y,rot)
_pl.GHOST[:]=[]
