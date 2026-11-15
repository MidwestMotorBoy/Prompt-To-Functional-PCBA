# port 1 top block (USB-C, PD controller, 5 V buck) -- variant v1: U401 turned to rot 0 (as on the hand board) so
# that VBUS (pad 23) and PPHV (pad 20) face east: VBUS comes straight down from J401's east VBUS pins, PPHV goes
# straight south to R424, and neither wraps a pin column (with rot -90 the VBUS pour ran down the whole east pin
# column from J401 to pad 23 and walled pins 26..36). Support parts keep a strip in front of each pin row free.
A=lambda *a,**k: auto(P,*a,**k)
put('U401',105.1,81.0,0)
put('U405',104.3,73.3,-90)
put('D401',100.85,71.75,0)
# 5 V buck, top right (unchanged from groundup)
put('L402',114.6,79.3,180)
for i,r in enumerate(('C441','C442','C443')): put(r,113.3+2.4*i,74.05,90)
put('U404',115.0,84.0,90)
put('C446',115.5,85.9,0)
put('C440',116.9,83.2,-90)
put('C444',119.05,84.7,90)
put('R434',113.6,85.85,180)
# VBUS / PPHV side (east)
put('C406',110.1,79.0,270)        # J401 VBUS input cap beside pad 23, VBUS pad north
put('R424',109.6,85.0,-90)        # PPHV sense, PPHV pad north (below pad 20)
put('R425',111.5,84.4,90)
put('R426',111.5,86.4,90)
# north row (pins 26..38): CC caps, PP5V and 3V3 caps in front of their pins
put('C401',107.2,77.0,90)         # CC1 (pin 28)
put('C402',106.1,77.0,90)         # CC2 (pin 29)
put('C407',104.1,77.0,180)        # PP5V (pin 34)
put('C403',100.9,77.0,180)        # 3V3 (pin 38)
# west row (pins 1..6): LDO caps
put('C404',100.6,79.6,270)
put('C405',100.6,82.4,270)
# south row (pins 7..19) escapes south: EEPROM and pull-ups 3 mm below it
put('U402',102.0,86.6,0)
for i,r in enumerate(('R402','R403','R404','R441')): put(r,104.8+1.0*i,86.4,90)
A('C439',pins={'1':'U404.7'},at=(113.0,84.3))
A('R433',pins={'2':'U404.8','1':'L402.2'},at=(112.6,83.0))
A('R432',pins={'1':'U404.2'},at=(114.0,85.8))
A('C450',pins={'1':'U401.23'},at=(109.3,76.0))
A('C449',pins={'1':'R424.1'},at=(111.4,82.6))
A('C451',pins={'1':'U405.3'},rots=(0,180))
A('C452',pins={'1':'U405.10'},rots=(0,180,90,270))
A('C408',pins={'1':'U402.8'},at=(100.2,86.6))
A('R455',pins={'2':'U401.37','1':'C404.1'},at=(101.2,75.4))
