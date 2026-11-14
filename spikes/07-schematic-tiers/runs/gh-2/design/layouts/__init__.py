"""Hand-guided layouts, one function per block: layout(h, **kw) draws with the hand.Hand toolkit."""
from . import rail_3v3, cells_gauge, mcu, usb_port

LAYOUTS = {
    "3V3 Rail": (rail_3v3.draw, {}),
    "Cells and Gauge": (cells_gauge.draw, {}),
    "MCU": (mcu.draw, {}),
    "USB Port 1": (usb_port.draw, dict(n=400)),
    "USB Port 2": (usb_port.draw, dict(n=500)),
}
