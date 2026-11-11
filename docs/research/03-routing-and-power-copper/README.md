# Notes for report 03 (routing and power copper)

What was run in the research container on 2026-11-11 (Linux, 4 cores, 3.4 GB heap seen by Java):

- Freerouting 2.5.0 jar from the project's GitHub release, with a Temurin JRE 25 unpacked in a scratch folder
  (the container's own Java is 21 and the 2.5.0 jar needs 25). Command form:
  `java -Djava.awt.headless=true -jar freerouting-2.5.0.jar --gui.enabled=false -de board.dsn -do board.ses`.
  `--analytics.enabled=false` is not a valid setting (the log says "Unknown settings property"); the documented
  one is `usage_and_diagnostic_data.disable_analytics`. Analytics calls failed at the proxy, so nothing was sent.
- Inputs were DSN files from the Freerouting repository: `scripts/benchmark/fixtures/PCBench/z2amiller_sensorboard/unrouted.dsn`,
  `fixtures/Issue367-Charger.dsn`, `fixtures/Issue145-smoothieboard.dsn`. No KiCad was available in the container,
  so the DSN export and SES import steps were not exercised.
- `ses_stats.py` counts segments, track length and widths in a Specctra SES file.
- The two `.log` files are the Freerouting logs of the first two runs (lines cut at 400 characters).

Not run: KiCadRoutingTools (the session's permission system refused to run downloaded code), PCBWorld (needs a
KiCad engine build), padne.
