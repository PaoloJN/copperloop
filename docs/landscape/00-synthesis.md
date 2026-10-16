# Agent-driven PCB design stack — landscape synthesis (2026-10-16)

Four surveys: 01 KiCad automation, 02 design entry/review, 03 placement/routing, 04 research/parts/fab.
Rule: KiCad stays the editor. We glue OSS tools + public APIs; we write only what nobody has.
License for our code: MIT. Never vendor AGPL (Konnect, KiBot, easyeda2kicad is AGPL too: call it as a CLI, don't import).

## Stage → tool

| Stage | Take (exists) | Build (gap) |
|---|---|---|
| Idea / research | GitHub search `topic:kicad` + MPN; OSHWA API; Hackaday.io API; Kitspace boards.txt; kicad-happy datasheets skill; DigiKey v4 + Mouser APIs (1000/day each); jlcparts/jlcsearch | reference-design importer (clone → netlist → pattern detect → lift subcircuit) |
| Decisions / docs | docs/decisions.md + changelog (what we do now); HackRF / Open Book repo layout | evidence bundle per decision (KiCadAI idea) |
| Schematic | KiCad GUI; kicad-cli sch erc/bom/netlist; SKiDL 3 + schematizer if code-defined | nothing (IPC sch API is KiCad 11) |
| Library | KiCad official libs; easyeda2kicad (LCSC → sym/fp/3D); KLC checkers | — |
| Review | kicad-happy (installed): sch, pcb, emc, spice, bom; kicad-tools ERC repair | — |
| Placement | our polar placer; kicad-tools CMA-ES for generic boards | keep ours |
| Routing | per-net transactions over IPC (kipy commit/undo); our routelib (collision-checked) + grid router; KiCadRoutingTools (Rust A*, corridors) per net; Freerouting 2.5 only for easy nets with hard ones protected; viastitching | region render per layer; propose→DRC gate→accept loop (nexatech acceptance rule); LGA escape planner with keepout awareness; violation→picture |
| Verification | kicad-cli drc json + parity (the only truth); nexatech verify.py ideas (decoupling, IR drop); spicelib + ngspice; gerber2ems for SI | — |
| Fab | kicad-cli gerbers/drill/pos; Fabrication Toolkit; Cimos .kicad_dru for JLC; JLC API (apply) | DFM diff vs JLC capabilities page |
| Bring-up | probe-rs, pyOCD, adafruit-nrfutil (MIT), OpenHTF | BLE DFU test plug |
| Agent layer | skills per stage (kicad-happy model); thin MIT MCP: kipy + kicad-cli, kipilot-style mutation gate, kicad-mcp-pro profiles (read/build/release) | the MCP itself |

## Skip
heypcb, Flux, Quilter, DeepPCB (closed engines). atopile (no .kicad_sch, Py 3.14). PySpice (stale). KiBot/Konnect (AGPL). OrthoRoute (backplanes). SWIG-only tools except behind an adapter (gone in KiCad 11, ~Mar 2027).

## Hard facts that shape the design
- KiCad 10 IPC: GUI must be open; can create/update/remove/commit/undo/refill/select/run_action; cannot DRC, plot, place from library, or touch schematics. kicad-cli does DRC/plot/export headless. So: edits via IPC, truth via kicad-cli, files via S-expr.
- No tool scripts push-and-shove. Chokepoint nets stay human.
- No router honours .kicad_dru or no-via regions; model them as keepouts/pre-strip.
- Distributor data can't be cached into a shared DB (DigiKey/Nexar terms). Store MPN + query, fetch live.

## Milestone 1 (on the puck, this week)
1. `pip install kicad-python`; prove connect to the open v2 board.
2. `see`: render a region of the board per layer to PNG (kicad-cli svg → viewBox crop → png).
3. `gate`: kicad-cli drc json + parity → one-line verdict + diff vs last run.
4. `fanout 3V3`: port fanout_planes to IPC commits, one commit per pad, Paolo watches and can Ctrl+Z; gate after each batch.
Success = 3V3 fully fanned out live with 0 new DRC errors and no file copying.

## Milestone 2
Per-net route transaction: plan → routelib/KiCadRoutingTools → IPC commit → gate → keep/drop. Use on the easy signal nets. Human does module escapes.

## Milestone 3
Package: new repo, `tools/` + `skills/` + thin MCP, README, used by sensei-cup as first client. Then fab stage (Fabrication Toolkit + dru + JLC API).
