"""Views: how each block's sheet is laid out. One function per block, written with the toolkit in scene.py.
A block without a view is still drawn, by the automatic drawer in draw.py (draw_block)."""
from views.rail_3v3 import view as _rail
from views.mcu import view as _mcu
from views.usb_port import view as _usb
from views.cells_gauge import view as _cells
VIEWS = {"Cells and Gauge": _cells, "3V3 Rail": _rail, "MCU": _mcu, "USB Port*": _usb}
