# port 2 top block -- variant v5: U501 turned to rot 0 like port 1 (v4), so VBUS pad 23 / PPHV pad 20 face east:
# VBUS comes down from J501's west VBUS pins past D501, PPHV leaves pad 20 east to R524, and neither wraps a pin row
# (with rot -90 the VBUS copper ran from J501 to pad 23 down the whole east pin column, and C549 west of R524 pulled
# the PPHV pour under pins 16..19).
A=lambda *a,**k: auto(P,*a,**k)
UX=84.1
put('U501',UX,81.0,0)
put('C550',UX+4.25,79.6,90)       # VBUS 10n, VBUS pad at pad 23
put('C549',UX+4.25,82.4,270)      # PPHV 0.1u, PPHV pad at pad 20
put('R524',UX+3.9,85.3,-90)       # PPHV sense, PPHV pad north
put('R526',UX+3.9,87.9,0)         # kelvin filter at the AC_SNS_N end
put('C507',UX-0.6,76.95,90)       # PP5V, pad 1 at pin 34
put('C504',UX-3.1,77.7,0)         # LDO_3V3 (pins 1, 2) at the NW corner
put('C503',UX-3.1,76.1,0)         # 3V3 (pin 38)
put('C505',UX-4.15,81.4,270)      # LDO_1V5 (pin 4), west of the chip
put('C508',UX-1.1,84.7,0)         # EEPROM decoupling, GND pad under pins 11..12
put('U502',UX+1.1,86.5,90)        # EEPROM under pins 13..17
put('R502',UX-1.9,86.8,90); put('R503',UX-1.0,86.8,90)
put('R504',UX-3.8,86.8,90); put('R541',UX-2.9,86.8,90)
# TVS and TPD6S300 right of the peg (unchanged)
put('D501',87.8,71.75,0)
put('U505',95.75,73.3,-90)
# 5 V buck in the centre top (unchanged)
put('L502',92.0,81.4,90)
put('C541',91.72,76.9,0)
put('C552',94.6,77.0,-90)
put('C502',95.62,76.9,-90)
put('C501',96.64,76.9,-90)
put('C542',96.1,80.5,-90)
put('C543',98.5,80.5,-90)
put('U504',93.9,86.6,180)
put('C546',95.85,85.6,90)
put('C544',98.05,85.9,90)
put('C540',91.7,86.2,-90)
put('C506',87.95,75.6,90)        # J501 VBUS input cap on the VBUS path between D501 and pad 23, VBUS pad south
A('R525',pins={'1':'R524.1'},at=(90.0,85.8))
A('C551',pins={'1':'U505.3'},rots=(0,180))
A('R534',pins={'1':'U504.8'},at=(90.8,87.8))
A('C539',pins={'1':'U504.7'},at=(90.2,86.4))
A('R533',pins={'2':'R534.1','1':'L502.2'},at=(89.8,85.2))
A('R532',pins={'1':'U504.2'},at=(95.0,87.8))
A('R555',pins={'2':'U501.37','1':'C504.1'},at=(82.0,75.0))
try: A('R554',pins={'1':'Q509.3'},at=(99.0,93.9))
except Exception as e: print(e)
