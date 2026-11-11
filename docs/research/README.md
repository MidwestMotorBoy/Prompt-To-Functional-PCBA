# Research

Outside research goes here as leads. Nothing in this folder is verified until a note says who checked it and
against what source.

Start with `00-synthesis.md`.

| File | What it is | Status |
|---|---|---|
| `00-synthesis.md` | Reads across the five deep dives: where they agree, where they disagree, recommendation per stage, how the tool improves by machine alone, five proposed spikes | Proposal for Logan, 2026-11-11 |
| `01-design-representation.md` | How the LLM authors the circuit and what the source of truth is. Ran atopile, SKiDL, circuit-synth, tscircuit on one buck block | Research lead. Paper figures need re-reading from the PDFs |
| `02-placement.md` | Placement architecture. Three experiments on the Monolith dump | Research lead |
| `03-routing-and-power-copper.md` | Routing by net type, power copper generation. Ran Freerouting headless on three boards | Research lead |
| `04-verification-and-grounding.md` | Gate checks, datasheet grounding, simulation. Ran a pin-table cross-check, ngspice, and known-answer tests of the project's solvers | Research lead |
| `05-prior-art-architecture-and-evaluation.md` | Prior art, agent-system design for cost, block library, public data, benchmark harness | Research lead |
| `2026-11-10-gemini-autorouter-and-placement.pdf` | Gemini deep-research chat (13 pages): autorouter families (maze, shape-based, topological), negotiated congestion (PathFinder), SAT pin escape, physics cost terms, placement methods (sequence pair + annealing, analytical, clustering), routability-driven placement, and an LLM-in-the-loop design where the LLM writes constraints and diagnoses failures while deterministic engines do geometry | Unverified. It cites 5 web sources, mostly vendor blogs. Formulas, performance figures and claims about commercial tools need checking against primary papers |

## Ideas worth testing from the Gemini chat

- The LLM should not output coordinates. It writes a constraint spec (clusters, anchors, loop pairs, swappable
  pins) and picks from a small set of mutations (rotate, flip side, inflate courtyard, swap pins). This matches
  what the Battery-Bank skills found: knowledge typed into tools as lists should come from the schematic.
- Count airwire crossings in the placement score.
- Bind decoupling caps and other two-pin support parts to their parent pin before global placement.
- When routing fails, feed back a text bottleneck report plus a cropped picture, then change placement locally.
- Price loop area, return-path breaks and aggressor-victim coupling inside the router's cost, not only after.

## Open against our own evidence

- The chat proposes writing a new placer and router in Rust. Battery-Bank already has a working Python grid
  router and greedy placer with real DRC in the loop. Whether to extend those, use Freerouting, or build new is a
  research-stage decision.
