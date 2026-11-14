"""Monolith top level, all five blocks."""
import sys
from kernel import *
from blocks.rail_3v3 import rail_3v3
from blocks.usb_port import usb_port
from blocks.mcu import mcu
from blocks.cells_gauge import cells_gauge

gnd, pack_p, v3v3 = Net("GND"), Net("PACK_P"), Net("3V3")
declare(pack_p, kind="power", current_a=10, max_v=16.8)
sda, scl, irq_n, chg_inh = Net("SDA"), Net("SCL"), Net("IRQ_N"), Net("CHG_INH")
volts(3.6, v3v3, sda, scl, irq_n, chg_inh); volts(0, gnd)

sleep_n, en1, en2 = Net("3V3_SLEEP"), Net("EN_5V1"), Net("EN_5V2")
rail_3v3(pack_p, v3v3, gnd, sleep_n)
cells_gauge(gnd, irq_n, pack_p, scl, sda)
mcu(v3v3, gnd, sda, scl, irq_n, chg_inh, sleep_n, en1, en2)
usb_port("USB Port 1", 400, pack_p, gnd, v3v3, sda, scl, irq_n, chg_inh, en1, Net("/P1_LDO_3V3"))
usb_port("USB Port 2", 500, pack_p, gnd, v3v3, sda, scl, irq_n, chg_inh, en2, Net("/P2_LDO_3V3"),
         adcin1_high=False)

if __name__ == "__main__":
    comps, nets = build(sys.argv[1] if len(sys.argv) > 1 else "out", partial=True)
    print(len(comps), "parts,", len(nets), "nets")
