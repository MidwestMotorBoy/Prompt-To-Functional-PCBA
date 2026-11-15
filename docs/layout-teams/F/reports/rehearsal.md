Routing rehearsal on team D's round-2 placement (zones split, no lead copper), 2026-11-15:
- tiers (long nets first, then the rest with --nopre): 73 unconnected, 2 DRC errors; ml.py closed 2 of 49.
- one router run, --long=20, fan-out stubs on: 365 of 397 edges, 32 failed, 48 unconnected, 4 DRC errors, 107 min in the container.
  Almost every failure is "no way even with every other route gone": blocked by placement and power copper, not by congestion
  (Kelvin taps to zones, U401/U501 GND pins 31/36, J302.6, TS at TH401, C_CC under VBUS copper, HG1 in-pad, 3V3 at R302/R313).
  So: fix those at the copper stage (cuts, in-pad vias, hand escapes) BEFORE the router runs.
