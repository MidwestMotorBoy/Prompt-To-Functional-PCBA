# port 1 top block -- variant v3 (from v2): U401 rot 0 (hand orientation), VBUS pad 23 / PPHV pad 20 facing east.
#  - D401 (VBUS TVS) at J401's east VBUS pins, so no VBUS copper runs along U405's north / west pins
#  - CC caps beside U405, the strip north of U401 pins 26..36 free for vias
#  - C407 (PP5V) in front of pin 34, shifted east so pins 36/37 can leave north; 3V3 cap C403 at the NW corner
#  - R424 east of pad 20: PPHV leaves pad 20 eastwards, away from pins 16..19; kelvin filters R425/R426 at its two ends
#  - C408 (GND pad with vias) 1.5 mm below GND pins 11..14 so their return joins stay short and pins 8..10 can leave
#  - EEPROM and pull-ups 3 mm below the south row
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
put('C449',110.4,82.0,0)          # PPHV cap between pad 20 and R424.1
put('R425',112.3,83.0,0)          # kelvin filters: PPHV end (north), AC_SNS_N end (south)
put('R426',112.0,86.7,90)
put('C407',104.5,76.95,90)        # PP5V, pad 1 at pin 34
put('C403',101.0,76.2,0)          # 3V3, NW of pin 38
put('C404',100.6,79.9,270)        # LDO caps west of pins 1..6
put('C405',100.6,82.7,270)
put('C408',105.0,84.9,0)          # GND pad under pins 12..14
# south row (pins 7..19) escapes south: EEPROM and pull-ups 3 mm below it
put('U402',101.6,87.0,0)
for i,r in enumerate(('R402','R403','R404','R441')): put(r,106.2+0.95*i,86.7,90)
A('D401',pins={'5':'J401.A4','2':(112.5,71.0)},at=(111.0,71.0))
A('R455',pins={'2':'U401.37','1':'C404.1'},at=(102.9,76.2))
A('C401',pins={'1':'U405.12'},rots=(90,270),at=(101.6,75.6))
A('C402',pins={'1':'U405.11'},rots=(90,270),at=(101.0,75.6))
A('C451',pins={'1':'U405.3'},rots=(0,180))
A('C452',pins={'1':'U405.10'},rots=(0,180,90,270))
A('C439',pins={'1':'U404.7'},at=(113.0,84.3))
A('R433',pins={'2':'U404.8','1':'L402.2'},at=(112.6,83.0))
A('R432',pins={'1':'U404.2'},at=(114.0,85.8))
A('C450',pins={'1':'U401.23'},at=(109.3,76.0))
