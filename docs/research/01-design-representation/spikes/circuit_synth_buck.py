from circuit_synth import *

@circuit(name="buck_5v")
def buck(vin, vout, gnd):
    """TPS54202 buck, 5 V out"""
    u = Component(symbol="Regulator_Switching:TPS54202DDC", ref="U", footprint="Package_TO_SOT_SMD:SOT-23-6")
    l = Component(symbol="Device:L", ref="L", value="10uH", footprint="Inductor_SMD:L_Bourns_SRP5030T")
    cin = Component(symbol="Device:C", ref="C", value="10uF", footprint="Capacitor_SMD:C_0805_2012Metric")
    cout = Component(symbol="Device:C", ref="C", value="22uF", footprint="Capacitor_SMD:C_0805_2012Metric")
    cboot = Component(symbol="Device:C", ref="C", value="100nF", footprint="Capacitor_SMD:C_0402_1005Metric")
    rtop = Component(symbol="Device:R", ref="R", value="100k", footprint="Resistor_SMD:R_0402_1005Metric")
    rbot = Component(symbol="Device:R", ref="R", value="13.3k", footprint="Resistor_SMD:R_0402_1005Metric")
    sw, fb, boot = Net("SW"), Net("FB"), Net("BOOT")
    u["VIN"] += vin; u["EN"] += vin; u["GND"] += gnd
    u["SW"] += sw; u["BOOT"] += boot; u["FB"] += fb
    cboot[1] += boot; cboot[2] += sw
    l[1] += sw; l[2] += vout
    cin[1] += vin; cin[2] += gnd
    cout[1] += vout; cout[2] += gnd
    rtop[1] += vout; rtop[2] += fb
    rbot[1] += fb; rbot[2] += gnd

@circuit(name="top")
def top():
    vin, v5, gnd = Net("VIN"), Net("+5V"), Net("GND")
    j1 = Component(symbol="Connector_Generic:Conn_01x02", ref="J", footprint="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical")
    j2 = Component(symbol="Connector_Generic:Conn_01x02", ref="J", footprint="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical")
    j1[1] += vin; j1[2] += gnd; j2[1] += v5; j2[2] += gnd
    buck(vin, v5, gnd)

c = top()
c.generate_kicad_netlist("top.net")
c.generate_kicad_project("top_proj", force_regenerate=True)
