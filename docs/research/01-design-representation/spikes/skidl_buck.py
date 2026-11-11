import os
os.environ["KICAD9_SYMBOL_DIR"] = os.environ["KSYM"]
os.environ["KICAD8_SYMBOL_DIR"] = os.environ["KSYM"]
from skidl import *
set_default_tool(KICAD9)

@subcircuit
def buck_tps54202(vin, vout, gnd, vout_v=5.0):
    """TPS54202 2 A sync buck. Vref = 0.596 V."""
    u = Part("Regulator_Switching", "TPS54202DDC", footprint="Package_TO_SOT_SMD:SOT-23-6")
    l = Part("Device", "L", value="10uH", footprint="Inductor_SMD:L_Bourns_SRP5030T")
    cin = Part("Device", "C", value="10uF", footprint="Capacitor_SMD:C_0805_2012Metric")
    cout = Part("Device", "C", value="22uF", footprint="Capacitor_SMD:C_0805_2012Metric", dest=TEMPLATE)(2)
    cboot = Part("Device", "C", value="100nF", footprint="Capacitor_SMD:C_0402_1005Metric")
    rtop = Part("Device", "R", value="100k", footprint="Resistor_SMD:R_0402_1005Metric")
    rbot = Part("Device", "R", value="13.3k", footprint="Resistor_SMD:R_0402_1005Metric")
    sw, fb, boot = Net("SW"), Net("FB"), Net("BOOT")
    sw.netclass = "SWITCHING"          # layout intent carried on the net
    fb.netclass = "SENSITIVE"
    u["VIN"] += vin; u["EN"] += vin; u["GND"] += gnd
    u["SW"] += sw; u["BOOT"] += boot; u["FB"] += fb
    cboot[1, 2] += boot, sw
    l[1, 2] += sw, vout
    cin[1, 2] += vin, gnd
    cin.fields["serves"] = f"{u.ref}.VIN"       # cap-to-pin binding as a field
    cin.fields["hot_loop"] = "HL1"
    for c in cout: c[1, 2] += vout, gnd
    rtop[1, 2] += vout, fb
    rbot[1, 2] += fb, gnd
    # design assertion checked at compile time
    vr = 0.596 * (1 + 100e3 / 13.3e3)
    assert abs(vr - vout_v) / vout_v < 0.03, f"divider gives {vr:.3f} V, want {vout_v}"

vin, v5, gnd = Net("VIN"), Net("+5V"), Net("GND")
vin.drive = POWER; gnd.drive = POWER
j = Part("Connector_Generic", "Conn_01x02", footprint="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", dest=TEMPLATE)
jin, jout = j(), j()
jin[1, 2] += vin, gnd
jout[1, 2] += v5, gnd
buck_tps54202(vin, v5, gnd)
ERC()
generate_netlist(file_="buck.net")
try:
    generate_schematic(filepath=".", top_name="buck", flatness=1.0)
    print("schematic generated")
except Exception as e:
    print("SCHEMATIC FAIL:", type(e).__name__, str(e)[:500])
