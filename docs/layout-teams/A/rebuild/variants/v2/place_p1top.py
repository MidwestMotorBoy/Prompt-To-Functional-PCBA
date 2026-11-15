# port 1 top block -- variant v2 (from v1): U401 rot 0 (hand orientation), VBUS pad 23 / PPHV pad 20 facing east.
#  - D401 (VBUS TVS) moves from west of U405 to the east VBUS pins of J401, so no VBUS copper crosses U405's north pins
#  - CC caps beside U405 (not in front of U401's north pins): the strip north of pins 26..36 stays free for vias
#  - C407 (PP5V) directly in front of pin 34; R424 east of pad 20 so PPHV leaves pad 20 eastwards, away from pins 16..19
A=lambda *a,**k: auto(P,*a,**k)
put('U401',105.1,81.0,0)
put('U405',104.3,73.3,-90)
# 5 V buck, top right (input caps 0.5 mm east to make room for D401)
put('L402',114.6,79.3,180)
for i,r in enumerate(('C441','C442','C443')): put(r,113.8+2.4*i,74.05,90)
put('U404',115.0,84.0,90)
put('C446',115.5,85.9,0)
put('C440',116.9,83.2,-90)
put('C444',119.05,84.7,90)
put('R434',113.6,85.85,180)
# VBUS / PPHV side (east)
put('C406',110.1,79.0,270)        # J401 VBUS input cap beside pad 23, VBUS pad north
put('R424',110.4,84.4,-90)        # PPHV sense, PPHV pad north-east of pad 20
put('R425',110.4,87.2,180)        # kelvin filters under R424 (PPHV / AC_SNS_N pads toward it)
put('R426',108.6,87.4,90)
put('C449',110.4,82.0,0)          # PPHV cap between pad 20 and R424.1
put('C407',104.1,76.95,90)        # PP5V, pad 1 at pin 34
put('C403',100.9,77.2,180)        # 3V3 (pin 38)
put('C404',100.6,79.9,270)        # LDO caps west of pins 1..6
put('C405',100.6,82.7,270)
# south row (pins 7..19) escapes south: EEPROM and pull-ups 3 mm below it
put('U402',102.0,86.8,0)
for i,r in enumerate(('R402','R403','R404','R441')): put(r,104.4+1.0*i,86.6,90)
A('D401',pins={'5':'J401.A4','2':(112.5,71.0)},at=(111.0,71.0))
A('C401',pins={'1':'U405.12'},rots=(90,270),at=(101.6,75.6))
A('C402',pins={'1':'U405.11'},rots=(90,270),at=(101.0,75.6))
A('C451',pins={'1':'U405.3'},rots=(0,180))
A('C452',pins={'1':'U405.10'},rots=(0,180,90,270))
A('C439',pins={'1':'U404.7'},at=(113.0,84.3))
A('R433',pins={'2':'U404.8','1':'L402.2'},at=(112.6,83.0))
A('R432',pins={'1':'U404.2'},at=(114.0,85.8))
A('C450',pins={'1':'U401.23'},at=(109.3,76.0))
A('C408',pins={'1':'U402.8'},at=(100.2,86.6))
A('R455',pins={'2':'U401.37','1':'C404.1'},at=(101.2,75.4))
