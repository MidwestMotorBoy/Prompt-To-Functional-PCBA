export default () => (
  <board width="30mm" height="20mm">
    <chip name="U1" footprint="sot23_6" pinLabels={{1:"GND",2:"SW",3:"VIN",4:"FB",5:"EN",6:"BOOT"}} />
    <inductor name="L1" inductance="10uH" footprint="1210" />
    <capacitor name="C1" capacitance="10uF" footprint="0805" />
    <capacitor name="C2" capacitance="22uF" footprint="0805" />
    <capacitor name="C3" capacitance="100nF" footprint="0402" />
    <resistor name="R1" resistance="100k" footprint="0402" />
    <resistor name="R2" resistance="13.3k" footprint="0402" />
    <trace from=".U1 > .VIN" to="net.VIN" /><trace from=".U1 > .EN" to="net.VIN" />
    <trace from=".U1 > .GND" to="net.GND" /><trace from=".U1 > .SW" to=".L1 > .pin1" />
    <trace from=".L1 > .pin2" to="net.VOUT" /><trace from=".C1 > .pin1" to="net.VIN" /><trace from=".C1 > .pin2" to="net.GND" />
    <trace from=".C2 > .pin1" to="net.VOUT" /><trace from=".C2 > .pin2" to="net.GND" />
    <trace from=".U1 > .BOOT" to=".C3 > .pin1" /><trace from=".C3 > .pin2" to=".U1 > .SW" />
    <trace from=".R1 > .pin1" to="net.VOUT" /><trace from=".R1 > .pin2" to=".U1 > .FB" />
    <trace from=".R2 > .pin1" to=".U1 > .FB" /><trace from=".R2 > .pin2" to="net.GND" />
  </board>
)
