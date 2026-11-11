# Token cost of netlist encodings (measurement notes)

Run 2026-11-11 on LibreSolar `bms-c1` (public KiCad project, 199 parts with nets, 142 nets, 525 pads),
cloned from https://github.com/LibreSolar/bms-c1.

    python3 netlist_encodings.py <path>/bms-c1.kicad_pcb <unused>   # writes out/*.txt
    npm install gpt-tokenizer && node count_tokens.js 199           # counts with o200k_base

Tokenizer is OpenAI o200k_base (via the npm package `gpt-tokenizer`, which bundles the vocabulary). Claude's
tokenizer was not reachable from the container; current Claude models are documented as using roughly 1.0 to
1.35 times as many tokens as the previous Claude tokenizer, so treat the figures as a lower bound and re-measure
with the `count_tokens` endpoint.

| encoding | chars | tokens | tokens/part | scaled to 430 parts |
|---|---|---|---|---|
| raw .kicad_pcb | 2,738,359 | 1,389,120 | 6,980 | 3,001,616 |
| raw .kicad_sch, all sheets | 872,595 | 411,631 | 2,069 | 889,454 |
| JSON, verbose (one object per pin, indented) | 52,641 | 20,700 | 104 | 44,729 |
| JSON, compact (ref -> [value, footprint, {pin: net}]) | 16,663 | 8,291 | 41.7 | 17,915 |
| net-centric text (`NET: R1.1 U2.5 ...` + part list) | 10,623 | 6,349 | 31.9 | 13,719 |
| component-centric compact text (2-pin parts on one line) | 8,776 | 4,819 | 24.2 | 10,413 |
| placement table (ref, footprint, x, y, rot, layer) | 7,517 | 4,509 | 22.7 | 9,743 |
| ICs/connectors/FETs only + passive counts | 3,895 | 2,227 | 11.2 | 4,812 |
