"""p1_stage / p2_stage: the four-switch power stage, hand placed. p2_stage.py imports build() from here.
All coordinates below are Port 1's; Port 2 is the same arrangement moved 23.1 mm left (dx=-23.1).

Idea: each half-bridge lies with its pin rows north/south and its free end pointing outward, so the first capacitor
sits on the free end and the bulk capacitor right behind it in the same orientation (textbook row):
  left  row, west to east:  C420 | C430 | Q401 (D1 row north = AC_SNS_N from the entry above, S2 row south)
  right row, west to east:  Q402 (S2 row north, D1 row south = BAT_SNS_P to the shunt) | C438 | C431
The gate ends face the middle, above the charger's driver pins; SW leaves each FET on that end and turns north into
the inductor pad. The other three input capacitors lie on their side in the left column, AC pads east, so the pads
and the strip beside them are one straight 3 mm wide AC_SNS_N path from the entry down to Q401's D1 row."""
import sys; sys.path.insert(0, '../tools')
from room import Room

def build(name, dx, P2):
    rm = Room(name); p = '5' if P2 else '4'
    R = lambda s: s[0] + p + s[2:] if s[1] == '4' else s           # 'C420' -> 'C520' on port 2
    def side(ref, num):
        c = rm.court(ref); x, y = rm.pad(f'{ref}.{num}'); cx, cy = (c[0]+c[2])/2, (c[1]+c[3])/2
        ax, ay = (x-cx)/(c[2]-c[0]), (y-cy)/(c[3]-c[1])
        return ('E' if ax > 0 else 'W') if abs(ax) > abs(ay) else ('S' if ay > 0 else 'N')
    def place(ref, num, want, **edges):
        """put ref by courtyard edges (Port 1 x), turned so that pad `num` is on side `want`"""
        ref = R(ref)
        for k in ('left', 'right'):
            if k in edges: edges[k] += dx
        for rot in (0, 90, 180, 270):
            rm.put_court(ref, rot=rot, **edges)
            if side(ref, num) == want: return
        raise SystemExit(f'{ref}: no turn puts pad {num} on {want}')

    # ---- input side: left column (AC_SNS_N enters through the top edge at x 104-108)
    L = 101.6 if P2 else 101.1                       # port 2's room starts 0.5 mm further right
    place('C427', 1, 'E', left=L, top=87.8)          # on their side: GND pads west, AC pads east
    place('C424', 1, 'E', left=L, top=91.1)
    place('C423', 1, 'E', left=L, top=94.4)
    CY = 100.1                                       # both FETs 1.05 mm below the inductor: room for a gate resistor
    rm.put(R('Q401'), 107.91 + dx, CY, 270)          # D1 row north, S2 row south, gates on the east end
    place('C430', 1, 'N', left=104.92, top=CY + 0.3 - 0.955)   # first capacitor on Q401's free (west) end
    place('C420', 1, 'N', left=101.6, top=97.72)     # bulk right behind it, same orientation
    # ---- output side
    rm.put(R('Q402'), 115.25 + dx, CY, 90)           # S2 row north, D1 row south, gates on the west end
    if not P2:
        place('C438', 1, 'S', left=117.23, top=CY - 0.93 - 0.955)   # GND pad on the S2 pin row (y 98.4-99.0): the return
                                                                    #   via lands in the pad (stage_x1: 0.37 nH on Port 2 vs 0.51 here 0.63 mm lower)
        place('C431', 1, 'S', left=118.27, top=95.44)
        place('C434', 1, 'N', left=118.3, top=100.15)        # BAT pads of C431 and C434 face each other beside Q402's D1
        place('R427', 1, 'W', left=116.83, top=104.85)       # shunt on its side: PACK_P pad east, 1 mm above J113
    else:
        place('C438', 1, 'S', left=117.23, top=CY - 0.93 - 0.955)   # 0.6 mm higher: the shunt lies below it
        place('C431', 1, 'S', left=118.27, top=95.44)
        place('R427', 1, 'W', right=122.4, top=100.15)       # PACK_P pad at x 97.8-98.9, y 100.4-102.2
        place('C434', 1, 'N', left=118.27, top=90.72)        # no room near D1: above C531, sharing its GND vias
    # ---- the gate pin of each FET that is walled in by its switch node (HG1, LG2) gets its resistor right at the
    #      pin, in the strip between inductor and FET; the resistor's far pad is a full-size pad that can take a via
    place('R444', 2, 'E', left=106.995, top=96.815)          # HG1 pad over Q401 pin 1; HIDRV1 pad west
    place('R447', 2, 'W', left=114.215, top=96.815)          # LG2 pad over Q402 pin 8; LODRV2 pad east
    # ---- boot capacitors at the switch-node copper, between the two FETs
    place('C412', 2, 'N', left=111.2, top=98.85)
    place('C413', 2, 'N', left=112.3, top=99.6)              # below the SW2 strip (beside it, its BTST2 pad pinched the strip to 0.5 mm)
    # ---- the other gate resistors and the boot diodes: one row above the charger's driver pins, in the pins' order
    place('R445', 2, 'N', left=108.365, top=102.33)          # LG1 pad straight under Q401's LG1 pin
    place('D404', 1, 'N', left=110.31, top=101.65)           # BTST1 pad under C412's BTST1 pad
    place('D405', 1, 'N', left=111.81, top=101.65)           # BTST2 pad under C413's; DRV_SUP pads side by side
    place('R446', 2, 'N', left=113.885, top=102.6)           # HG2 pad straight under Q402's HG2 pin
    return rm

if __name__ == '__main__':
    build('p1_stage', 0.0, False).done()
