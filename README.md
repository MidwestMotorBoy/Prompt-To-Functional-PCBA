# Prompt to Functional PCBA

A tool that uses an LLM to take a person from a problem statement to a functional, assembled PCB through
back-and-forth prompting. Spec-driven, with a research stage and a verification gate after every stage.

Status: kickoff. The spec is a discussion draft.

## Layout

- `.claude/skills/`: agent skills carried over from the Battery-Bank (Monolith) project. Start with
  `pcb-proto-flow/SKILL.md`. They reference tools by their paths in the
  [Battery-Bank repo](https://github.com/MidwestMotorBoy/Battery-Bank).
  Nothing built with these skills had been powered when they were written, so every number in them is modelled.
- `tools/battery-bank/`: the placer, router, solvers and schematic helpers those skills call, as they left the
  Battery-Bank project. `HANDOFF.md` maps the paths the skills use to the paths here. Much of the code has
  that board's net names and coordinates typed in, so treat it as reference, not as a turnkey flow.
- `.env.example`: the API keys the tool reads from the environment. Copy to `.env`, which is gitignored.
