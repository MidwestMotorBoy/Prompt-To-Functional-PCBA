# Self review, start of round 4

| criterion | 3V3 | Cells+Gauge | MCU | USB 1+2 |
|---|---|---|---|---|
| Flow | 4 | 3 | 3 | 3 |
| Grouping | 3 | 3 | 3 | 3 |
| Wires vs labels | 4 | 2 | 3 | 3 |
| Clutter | 3 | 3 | 3 | 2 |
| Space | 3 | 3 | 2 | 3 |
| Recognisable | 4 | 2 | 4 | 3 |
| Annotation | 3 | 3 | 3 | 3 |
| Reviewability | 3 | 2 | 3 | 3 |

## Five changes (none done in this final round; page-packing weight tweak had no effect)
1. Gauge cell taps: per-input RC column instead of lanes (crossings, U101 left-side label collisions).
2. Lone parts (R432/R532 EN pull-down, TP412, D101): attach beside the pin or IC they serve; stop the big vertical gap under the 5 V buck.
3. Fuse ignition (F102, Q104, R124-126, C118) as one series template.
4. MCU: pull-ups as a bus feeding U301 with the antenna block under the module; fill the empty right half.
5. Move label text off wires near IC pins (R-value text sitting on wires).
