# kept where they are on the current board: Tag-Connect footprints (their holes go through the board and the cup side
# was checked against them), the antenna matching network, and the BLE module's decoupling next to them
for r in ('J301','J302','C313','C314','C315','R321','C301','C302','C303','R304'):
    P[r]=db.fp[r]['base']

# fixed parts that later scripts place by hand: reserve their spots before the automatic placer runs
put('Q102',103.4,118.5,270); put('C544',98.05,85.9,90)
