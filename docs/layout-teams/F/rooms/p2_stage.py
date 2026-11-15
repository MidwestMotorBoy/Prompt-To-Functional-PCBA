"""p2_stage: Port 2's power stage = p1_stage's arrangement moved 23.1 mm left (see p1_stage.py), adjusted on the
output side (the shunt R527 lies in the room's bottom-right corner, C534 sits above C531)."""
import sys; sys.path.insert(0, '../tools')
from p1_stage import build
build('p2_stage', -23.1, True).done()
