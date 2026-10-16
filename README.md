# CopperLoop

Agent-driven PCB design on top of KiCad 10, built from open-source tools and public APIs.

KiCad stays the editor. An agent (Claude Code, Codex, anything that can run a CLI) does the mechanical work: research, fan-out, stitching, routing proposals, DRC triage, exports. A human keeps the judgment calls and the push-and-shove router. Every change goes through the same loop:

**propose → gate → accept.** The agent edits the open board over the KiCad IPC API (one commit per change, undoable with Ctrl+Z). `kicad-cli` runs DRC and schematic parity. A change stays only if the violation and unconnected counts did not get worse.

Status: pre-alpha, being built while routing a real 4-layer board (the Water Puck carrier in [sensei-cup](https://github.com/PaoloJN/sensei-cup)). Everything here was pulled by a real need on that board.

## Principles

1. **KiCad decides.** `kicad-cli pcb drc --format json --schematic-parity` is the only truth. No home-grown DRC is authoritative.
2. **Edits over IPC, truth over CLI, files over S-expressions.** KiCad 10 IPC can edit a live board but cannot run DRC, plot, or touch schematics; `kicad-cli` can. The legacy SWIG API dies in KiCad 11, so anything SWIG sits behind an adapter.
3. **Human sees everything live.** Edits land in the open editor. Nothing is copied over the user's file behind their back.
4. **The agent must look.** Region renders per layer before claiming anything is routed.
5. **Only what nobody has.** We glue [kicad-happy](https://github.com/aklofas/kicad-happy), [kicad-tools](https://github.com/rjwalters/kicad-tools), Freerouting, [KiCadRoutingTools](https://github.com/atomic14/KiCadRoutingTools), distributor APIs. See `docs/landscape/`.
6. **MIT.** No AGPL vendored. Closed engines (heypcb, Flux, Quilter, DeepPCB) are not dependencies.

## Layout

```
copperloop/        python package, `cl` CLI
  kicad/           kicad-cli wrappers, IPC (kipy) session, S-expression parser
  route/           collision-checked routing primitives, fan-out, stitching (being ported)
  legacy/          scripts as they were used on the first board (SWIG pcbnew); reference until ported
docs/
  landscape/       2026-10-16 survey of every tool we found, with take/skip verdicts
  guides/          how to route with an agent, KiCad 10 quirks, per-stage checklists
skills/            agent skills, one per stage
examples/          worked boards
```

## Pipeline (target)

| Stage | Tool | Status |
|---|---|---|
| Research | DigiKey v4, Mouser, jlcparts, GitHub search, kicad-happy datasheets | planned |
| Schematic | KiCad GUI, kicad-cli erc/bom/netlist, kicad-happy review | planned |
| Placement | polar/scripted placement, region render | legacy |
| Fan-out | `cl fanout NET` over IPC, one commit per pad | works |
| Routing | per-net propose/gate/accept; Freerouting only for easy nets | milestone 2 |
| Verification | `cl gate [--live]` = DRC json + parity + diff vs last run | works |
| Seeing | `cl see X Y W H -l layers` region PNG, live or from file | works |
| Fab | kicad-cli gerbers/drill/pos, JLC design rules, Fabrication Toolkit | planned |
| Bring-up | probe-rs, OpenHTF | planned |

## Commands

```
cl connect                      # summary of the board open in the KiCad PCB editor
cl gate [BOARD] [--live]        # DRC + parity; PASS only if nothing got worse since last run
cl see X Y W H [-l F.Cu,B.Cu]   # region PNG per layer (board mm); live board unless --board FILE
cl fanout NET... [--apply]      # stub + via per pad into a plane; plan only unless --apply
```
`fanout --apply` makes one undoable commit per pad in the open editor, refills zones, then gates.

## Setup

```
python3 -m venv .venv && .venv/bin/pip install -e ".[route,render]"
```
KiCad 10 with the IPC API enabled (Preferences → Plugins → Enable IPC API). `kicad-cli` on PATH or at `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`.

## Roadmap

See `docs/roadmap.md`. Milestone 1: connect, see, gate, live 3V3 fan-out on the Water Puck.
