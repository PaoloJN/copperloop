# KiCad automation layer survey (2026-10-16)

Verified locally against KiCad 10.0.3 and kicad-python 0.8.0 (PyPI, 2026-08-30); GitHub stars/push dates pulled from the GitHub API today. Items marked *(unverified)* came only from READMEs/aggregators.

## 1. KiCad 10 IPC API / kipy

| Item | Status |
|---|---|
| Docs / install | https://docs.kicad.org/kicad-python-main/ ; `pip install kicad-python` (deps: protobuf, pynng). Source: https://gitlab.com/kicad/code/kicad-python. Dev docs: https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/for-addon-developers/ |
| Transport | protobuf over NNG, Unix socket `api.sock`; enable in Preferences > Plugins; env `KICAD_API_SOCKET`, `KICAD_API_TOKEN` |
| Can do (kipy 0.8.0 Board) | get footprints/pads/tracks/vias/zones/text/shapes/nets/items_by_net/netclass/connected_items; create/update/remove items; begin_commit/push_commit/drop_commit (one undo step); selection; refill_zones; flip_items; interactive_move; hit_test; bounding boxes; pad shapes as polygons; stackup; layers; save/save_as/revert; KiCad.run_action (any GUI action by name); Project.get_net_classes |
| Cannot do in KiCad 10 | No DRC run, no plot/export (KiCad 11), no footprint-from-library placement (11), no get/set design rules (11), no netlist import (11), no project/board creation, no schematic API (kipy Schematic class fails to import on 10) |
| Headless | GUI only in 9/10. `kicad-cli api-server` is KiCad 11. |
| Known issues | Editor must have the board open; modal dialogs block the socket; under-documented; version skew warnings |

## 2. kicad-cli 10.0.3

| Command | Notable flags |
|---|---|
| `pcb drc` | `--format json`, `--severity-all`, `--exit-code-violations`, `--schematic-parity`, `--all-track-errors`, `--refill-zones` (+`--save-board`), `-D var=val` |
| `sch erc` | `--format json`, severity flags, `--exit-code-violations` |
| `pcb export gerbers` / `drill` / `pos` | full JLC set; `--variant`; drill map formats; pos csv `--smd-only --exclude-dnp` |
| `pcb export svg` / `pdf` | `-l layers`, `--mode-single`, `--fit-page-to-board`, `--mirror`, `--scale`, `--black-and-white` |
| `pcb export step` (+brep/glb/stl/…) | `--include-tracks/pads/zones`, `--net-filter`, `--component-filter` |
| `pcb render` | raytraced PNG: `--side --rotate --zoom --pan --perspective --quality` |
| `pcb export` others | dxf, gencad, ipc2581, ipcd356, odb, ps, stats (`--format json`) |
| `sch export` | bom (`--fields --group-by --filter --exclude-dnp`), netlist (`spice`, `spicemodel`, kicadxml…), pdf, svg |
| `jobset run`, `pcb/sch upgrade`, `--variant` global | |

## 3. Legacy SWIG pcbnew
Still shipped in 10.0.3, removed in 11 (~Feb–Mar 2027). Only SWIG does: headless LoadBoard/SaveBoard, NewBoard, FootprintLoad from libs, offline ZONE_FILLER, PLOT_CONTROLLER, WriteDRCReport. Must use the app's bundled python. Everything built on it has a ~1-year shelf life; keep behind an adapter.

## 4. MCP servers

| Name | What | Backend | KiCad | License | Stars / push | Take? | Gaps |
|---|---|---|---|---|---|---|---|
| mixelpixx/KiCAD-MCP-Server | ~231 tools | IPC + SWIG fallback | 9+ | MIT | 2765 / 2026-10-01 | Reference | Node+Python; successor Konnect |
| mixelpixx/Konnect | Rust PCM plugin, 228 tools; sch via S-expr, PCB via IPC, kicad-cli exports | IPC+S-expr+cli | 10 | AGPL-3.0 | 1177 / 2026-10-12 | Study, don't vendor | AGPL; 174 open issues |
| nevenfo/kicad-agentic-mcp | Konnect fork, "KiCad decides" verification | same | 10.0.3–10.0.6 | AGPL-3.0 | 5 / 2026-10-12 | Study | AGPL |
| mnori0211/kicad-mcp-kipy | 18 read-mostly tools | kipy | 10 | MIT | 0 / 2026-08-11 | Thin-wrapper pattern | stale |
| paul356/KiCad-AI-Assistant (kcaa) | 60+ tools incl. sch place/wire, versioning/rollback | IPC+file | 10 | MIT | 115 / 2026-10-15 | Take rollback idea | own LLM key |
| belaszalontai/kipilot-mcp | 135 tools, read-first; guarded mutations env flag | kipy | 10 | Apache-2.0 | 12 / 2026-09-17 | YES: safety gating pattern | low adoption |
| iQreu/kicad-mcp | 54 tools, live edit + previews | kipy+cli+kicad-sch-api | 10.0.x | MIT | 0 / 2026-07-14 | Pattern | Windows-only |
| ProductOfAmerica/mcp-server-kicad | 109 tools, byte-preserving writes, Freerouting | file+cli+SWIG | 9/10 | GPL-3.0 | 13 / 2026-10-15 | Study writer | GPL, SWIG |
| oaslananka/kicad-mcp-pro | profiles read/build/release; DFM, SI/PI estimates | file/cli | — | MIT | 132 / 2026-10-16 | Take profile idea | first-order estimates |
| Seeed-Studio/kicad-mcp-server | 30+ tools | cli+S-expr+SWIG | 8+ | none | 158 | No | no license |
| lamaalrajih/kicad-mcp (installed here) | read-only DRC/BOM/netlist/thumbnails | cli+file | 9+ | MIT | 527 / 2025-10-17 | No | dormant |
| Netlist-Studio, blwfish, Finerestaurant, Huaqiu, others | small | kipy | 9 | MIT/none | ≤41 | No | dead/KiCad 9 |

## 5. Agent skill packs / toolkits

| Name | What | Backend | KiCad | License | Stars / push | Take? | Gaps |
|---|---|---|---|---|---|---|---|
| aklofas/kicad-happy | 11 skills: sch/PCB/Gerber review, spice, emc, datasheets, bom, distributors, jlcpcb/pcbway; GH Action | pure-Python S-expr | 5–10 | MIT | 1426 / 2026-10-15 | YES (installed) | read-only |
| nexatech-ltd/kicad-agent-toolkit | sync_board, Freerouting rounds w/ per-net acceptance, maze, GPU router, stitch_gnd, verify.py, gate.sh | SWIG+cli+Freerouting | 10 | Apache-2.0 | 0 / 2026-10-04 | YES: pipeline + gate pattern | SWIG dies in 11 |
| dshills/KiCadAI | Go CLI: intent compile, preflight, schematic-IR, evidence bundle | native writers + cli | 10.0.3 | MIT | 5 / 2026-10-08 | Take IR + evidence idea | narrow |
| eLSeR17/pcb-ai-agent | read tools, grounding gate, Ollama | S-expr | 6+ | MIT | 0 | grounding-gate idea | shallow |
| rjwalters/kicad-tools | nets/bom/erc/drc/creepage; A* route (C++), CMA-ES placement, stitch, fix-drc; MCP + skills | pure-Python S-expr | 8+ | MIT | 70 / 2026-10-16 | YES: headless parse/edit | router 74–80% |

## 6. Rendering

| Tool | What | Backend | License | Take? | Gaps |
|---|---|---|---|---|---|
| kicad-cli pcb export svg/pdf | per-layer 2D plot | cli | GPL tool | YES primary | no crop; rasterize + viewBox crop ourselves |
| kicad-cli pcb render | raytraced PNG | cli | — | yes, 3D sanity | slow |
| yaqwsx/PcbDraw | pretty SVG/PNG, pinouts | cli | MIT 1438 | yes | needs librsvg |
| InteractiveHtmlBom | HTML BOM + board | SWIG | MIT 4603 | human review | SWIG |
| KiKit | panelize | SWIG | MIT 2043 | panels only | SWIG |
| KiBot | YAML outputs | SWIG+cli | AGPL 753 | No (license) | |
| kipy export_png/svg | IPC plot | — | — | KiCad 11 | |

## Parts we should take
kicad-cli as every gate and export; kipy for live edits with commit/undo; kicad-happy for review; kicad-tools for headless S-expr; nexatech rounds+gate loop (wrapped); ideas from KiCadAI (evidence bundle), kcaa (rollback), kicad-mcp-pro (profiles), kipilot (mutation gating), Konnect ("KiCad decides", not vendored).

## Parts missing
Headless IPC, IPC DRC/plot/library/schematic (all KiCad 11); no permissive KiCad-10 MCP combining kipy + kicad-cli gates with adoption; no region-crop per-layer raster for agent vision; no interactive-router access via IPC; no violation→picture tool; SWIG deps expire in 11.
