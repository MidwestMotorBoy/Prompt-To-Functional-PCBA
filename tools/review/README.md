# Stage 5: design review

The intent gate proves what the design declares. The review stage looks for what nobody declared.

- `review_packet.py <build> <limits> <limitsmap.json> <design dir>` writes `review_packet.md` from the build: what the
  gate did not check (parts without limits, waivers, nets without a voltage, IC pins without a limit row), the
  thinnest margins, the declared set points, waived findings, and eight questions the reviewer must answer.
- The reviewer (an LLM that did not make the design) reads the packet and the datasheets and writes `findings.json`.
- `review_check.py <findings.json> <datasheet dir>` rejects any finding whose quote is not on the page it names, and
  fails while a serious finding is open. Outcomes: fixed, rule, waived, not a problem. A finding a machine could have
  caught should end as "rule", so the same miss cannot happen twice.

## First test (2026-11-11, Opus 5.5 reviewer, one run)

Design: the 24 V adapter change from spike 5 as the new-pipeline Opus agent left it, with the gate as it was before
the tested-tolerance rule. The reviewer was told the three problems the gate had flagged and asked for everything else.
Files are in `example/`.

Result: 7 findings, every quote verified on its page. 28 model calls, 22 k output tokens, 5.5 minutes.

| Finding | Severity | Gate could check it? |
|---|---|---|
| PD controller's own VBUS-to-PPHV overvoltage cut-off tops out at 24 V, so the port never charges from 25.2 V | blocks | yes, as a recommended-range style row on a configurable limit |
| CC protector TPD4S201 tested for a short to VBUS only to 21.5 V | blocks | yes; now the `tested_max` rule |
| The charger's 26.5 V cut-off only stops the charger, it disconnects nothing, and sits behind the PD switch | should fix | no; needs judgement about what a "cut-off" protects |
| VBIAS capacitor must be rated 63 V for the new protector | should fix | yes, as an application requirement row |
| 225 uF behind the PD controller's switch against a 100 uF recommended maximum, now charged from 25 V | should fix | yes, as a capacitance limit on a pin |
| No PPHV row in the PD controller's limits file | note | yes; the packet's "pins with no limit row" list shows it |
| TVS needs input edges slower than 2.5 V/us; a plain adapter plugs in at full voltage | note | no; bench check |

The reviewer found, without being told, the 21.5 V problem that had taken a separate benchmark run to stumble on, and
a larger one nobody had seen: the change cannot work at all because of the PD controller's 24 V ceiling.
Five of the seven can become limits rows or rules. One run, so this shows the stage is worth having, not how often it works.
