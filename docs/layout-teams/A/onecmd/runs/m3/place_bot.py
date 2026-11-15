import placelib as _pl, os
_g0=(_pl.GAP,_pl.RING); _pl.GAP=float(os.environ.get('GAPB',_pl.GAP)); _pl.RING=float(os.environ.get('RINGB',_pl.RING))   # the gauge corner is fuller: smaller gaps
# bottom: protection FETs, fuse, gauge, protector, 3V3 buck, MCU bits
A=lambda *a,**k: auto(P,*a,**k)
put('Q102',103.4,118.5,270)      # DSG FET, PACK_P source pins on top, under the PACK_P bus
put('Q101',103.4,126.0,90)       # CHG FET, CELL_P source pins at the bottom, drains face each other
put('F102',113.79,131.83,180)    # fuse right above the PACK+ wire hole
put('RS101',88.6,133.0,0)        # sense resistor at the PACK- wire hole
# 3V3 buck, bottom left
put('U204',82.4,128.2,0)
put('L201',86.6,128.3,0)
put('C206',81.6,124.9,0)
put('C207',87.2,124.7,0)

A('Q104',pins={'3':'F102.3'},rots=(180,),at=(117.0,129.0))
A('R124',pins={'2':'Q104.1'},at=(120.6,128.4))
A('R125',pins={'1':'Q104.1'},at=(119.7,128.4))
A('R126',pins={'1':'Q104.1'},at=(120.2,129.9))
A('C118',pins={'1':'Q104.1'},at=(120.1,130.9))
# gauge
put('U101',96.9,121.0,0)
A('C106',pins={'1':'U101.8','2':'U101.6'},rots=(90,270),at=(93.9,122.0))
A('C105',pins={'1':'U101.1'},rots=(0,180),at=(93.0,118.6))
for i,(c,r) in enumerate((('C101','R104'),('C102','R103'),('C103','R102'),('C104','R101'))):
    A(c,pins={'1':f'U101.{2+i}'},at=(93.3-0.0*i,119.8+0.5*i),rots=(90,270))
for i,r in enumerate(('R104','R103','R102','R101')):
    A(r,pins={'2':f'U101.{2+i}'},at=(90.5,119.5+1.0*i),rots=(0,180))
A('R105',pins={'2':'U101.32'},at=(95.3,117.6),rots=(90,270))
A('D101',pins={'1':'R105.1'},at=(94.5,116.8))
A('R109',pins={'1':'U101.31'},at=(96.3,117.6),rots=(90,270))
A('R111',pins={'1':'U101.28','2':'Q102.4'},at=(98.3,117.3))
A('R113',pins={'2':'U101.27'},at=(97.3,117.6),rots=(90,270))
A('R106',pins={'2':'U101.26'},at=(99.6,117.6))
A('R112',pins={'1':'Q102.4'},at=(100.0,116.0))
A('D103',pins={'1':'Q102.4'},at=(98.0,115.6))
A('R110',pins={'1':'Q101.4','2':'Q101.3'},at=(104.8,130.4))
A('R115',pins={'1':'U101.19'},at=(99.9,121.6))
A('R116',pins={'1':'U101.18'},at=(99.9,122.4))
A('Q103',pins={'1':'U101.15'},at=(98.6,125.6))
A('R117',pins={'1':'U101.15'},at=(96.6,124.2))
put('R107',87.65,131.3,0)       # Kelvin filter resistors: fixed, the sense taps are drawn to them
put('R108',90.1,130.85,90)
# cell protector under the gauge
put('U102',99.2,131.5,0)
A('R123',pins={'1':'U102.1'},at=(96.6,130.3))
A('C116',pins={'1':'U102.1'},at=(96.6,131.4))
for i,(r,c) in enumerate((('R119','C112'),('R120','C113'),('R121','C114'),('R122','C115'))):
    A(r,pins={'2':f'U102.{2+i}'},at=(96.5+1.5*i,133.4))
for i,c in enumerate(('C112','C113','C114','C115')):
    A(c,pins={'1':f'U102.{2+i}'},at=(96.5+1.5*i,134.2))
A('C117',pins={'2':'U102.7'},at=(100.6,131.4))
# FET clamp / ESD caps, wake
A('C110',pins={'1':'Q101.1'},at=(100.0,128.9))
A('C111',pins={'1':'C110.2'},at=(100.0,127.6))
A('C107',pins={'1':'Q102.1'},at=(106.9,116.2))
A('C108',pins={'1':'C107.2'},at=(107.2,117.4))
A('R118',pins={'1':'Q101.1'},at=(100.0,126.0))
A('TP113',pins={'1':'R118.2'},at=(99.5,124.5))
# MCU bits
A('C304',pins={'1':'U301.14'},at=(109.9,124.3))
A('R302',pins={'2':'U301.14'},at=(109.9,123.5))
A('R313',pins={'2':'U301.15'},at=(109.9,125.1))
A('R305',pins={'2':'U301.10'},at=(109.9,120.1))
A('R314',pins={'2':'U301.21'},at=(118.7,127.1))
A('TP301',pins={'1':'L201.2'},at=(89.8,126.3))

# test points
put('TP412',117.5,66.2,0); put('TP512',82.5,66.2,0)
put('TP106',100.3,92.3,0); put('TP109',100.3,89.9,0)

_pl.GAP,_pl.RING=_g0
