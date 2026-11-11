---
name: kicad-tools-and-mcp
description: Run KiCad from an agent - kicad-cli for netlists, ERC, DRC and exports, a local KiCad MCP server on the user's PC, and what to do when no KiCad is available - including the fix for a KiCad MCP that stops after a KiCad reinstall. Use when you need ERC/DRC/exports, when KiCad tools fail, or when deciding whether to work in the cloud or on the user's machine.
---

# KiCad tooling for agents

## Where KiCad runs

- **A cloud container can run KiCad through Docker** (found 2026-11-09; before that this project believed it could not). The apt PPA, downloads.kicad.org and flathub were blocked, Docker Hub was open. See "KiCad in a cloud container" below. With it, DRC, ERC, zone refill, pcbnew scripts, renders and gerbers need nobody's PC.
- **Where Docker is not available**, work on the files as text (`kicad-schematic-scripting`, `pcb-copper-resistance`), and get real ERC/DRC from the user's machine.
- **The user's PC.** Either use `kicad-cli` through a remote session, or use a KiCad MCP server running there (`mixelpixx/KiCAD-MCP-Server` on this project, tools `kicad__*`).
- **Heavy batches** (thermal sweeps, many solver runs) go to the user's machine too if it's set up for them.

## kicad-cli (KiCad 8–10)

```
kicad-cli sch export netlist --format kicadxml -o net.xml root.kicad_sch
kicad-cli sch erc --format json -o erc.json root.kicad_sch
kicad-cli pcb drc --format json --severity-all -o drc.json board.kicad_pcb     # add --schematic-parity / --refill-zones if your version has them
kicad-cli pcb export step|gerbers|drill|pos ...
```
On Windows the path is `C:\Program Files\KiCad\<ver>\bin\kicad-cli.exe`. KiCad's bundled Python (`...\bin\python.exe`) has pcbnew available, and is the interpreter to use for scripts that import it.

## KiCad in a cloud container (Docker)

```
dockerd > /tmp/dockerd.log 2>&1 &          # the daemon is not running by default; wait until `docker info` answers
docker pull kicad/kicad:10.0               # about a minute
docker run --rm -u 0 -v <work>:/w -v <conf>:/root/.config/kicad -w /w kicad/kicad:10.0 \
    kicad-cli pcb drc --schematic-parity --all-track-errors --severity-all --format json -o /w/drc.json /w/Board.kicad_pcb
docker run --rm -u 0 -v <work>:/w -w /w kicad/kicad:10.0 python3 /w/script.py      # `import pcbnew` works
```

What it took to make the results trustworthy:

- **Work on a copy.** `kicad-cli` rewrites the `.kicad_pro`. Copy the project to a scratch folder, `chmod -R a+rwX`
  it, and restore the project file after each run.
- **The board must carry the project's name and sit beside its `.kicad_pro` and `.kicad_dru`.** A scratch copy
  called `try7.kicad_pcb` is checked with default rules: the custom rules and net classes are silently not
  applied. Copy the candidate to `<dir>/<Project>.kicad_pcb` for the DRC that counts. pcbnew's Python likewise
  only knows the net classes when `<board>.kicad_pro` sits beside the board.
- **Footprint library table.** Run as root (`-u 0`) and mount a folder that holds `10.0/fp-lib-table` (KiCad's
  template) at `/root/.config/kicad`. Without it DRC reports about 200 `lib_footprint_issues`.
- **Python packages.** The image's Python has no pip and no numpy. On the host:
  `pip download --python-version 3.13 --only-binary=:all: numpy pillow scipy -d wheels`, unzip the wheels into a
  folder, mount it and set `PYTHONPATH`. Better: keep KiCad scripts to pcbnew + the standard library, dump what
  they read to JSON, and do the numeric work on the host.
- **One daemon, one command.** Wrap every call in a script that starts `dockerd` if needed, runs the command and
  stops the daemon it started (`hardware/Production/groundup/dk.sh`). Never run two such commands at once: the
  first to finish stops the daemon under the other. Do not leave `dockerd` running as a background task.
- **A zone refill from a script can report edge-clearance errors on zones that a second DRC run does not.** Judge
  a board by the DRC of the saved, renamed file, not by the DRC inside the edit step.
- The image has no KiCad 3-D model library: a STEP export only contains the project's own models.
- Times on 4 cores, 430-part six-layer board: DRC with parity 8 to 10 s, load + refill + save 15 s.

## Working with a local KiCad MCP

- **Read tools are safe** (`get_*`, `list_*`, `run_drc`, `run_erc`, `export_*`) and work with KiCad open.
- **`open_board`, `refill_zones` and `save_board` rewrite the file** in pcbnew's normalised form. That trips KiCad's "file changed on disk" guard and can fight the person's unsaved work. Run them on a copy (`review/revN-drc/`) unless the person asked for the edit.
- **Live board edits** (only when the board owner asks): have them save, write with KiCad closed or with a modification-time check, then `refill_zones` / `save_board(force)`, then they reopen or revert. Keep a backup in `review-backups/<what>/`.
- The server may have no tool for some edits (for example lines or polygons on silkscreen). Fall back to a text edit of a closed file.
- Some servers keep the open board's state in a Python process. If results look stale, reload the board.

## Fix: every call returns "Python process for KiCAD scripting is not running"

Seen 2026-10-30 after a clean reinstall of KiCad 10, while the MCP server still showed as connected.
1. Look in the server's log (`~\.kicad-mcp\logs\kicad-mcp-<date>.log` for this server). The helper process had crashed with `ModuleNotFoundError: sexpdata`.
2. Cause: the server's Python dependencies had been installed into KiCad's bundled site-packages, which the reinstall wiped. The config paths in `claude_desktop_config.json` were still fine.
3. Fix: install the requirements into the per-user KiCad Python folder, which survives reinstalls:
   ```
   "C:\Program Files\KiCad\10.0\bin\python.exe" -m pip install --target "%USERPROFILE%\Documents\KiCad\10.0\3rdparty\Python311\site-packages" -r <server>\requirements.txt
   ```
   `cairosvg` fails to load on Windows (no Cairo DLL). That's expected; the server renders with pymupdf instead.
4. Fully quit the Claude desktop app (from the tray) and reopen it, so the MCP server restarts.

Diagnose from a remote session on the PC. Folder access to dot-folders such as `~/.kicad-mcp` may be refused.

## When nothing can run

Say so in the report ("DRC not run: KiCad server down"), do the script-only checks you can (clearances, Kelvin taps, netlist from text), and list the ERC/DRC run as an open item for the person.
