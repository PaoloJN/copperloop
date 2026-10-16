# Placement & Routing Landscape for an Agent-Driven KiCad 10 Flow (2026-10-16)

Legend: **4L dense?** = plausibly usable on a 4-layer, ~Ø46 mm board with a 0.4 mm-pitch module under a no-via zone. "unverified" = could not confirm from a primary source.

## 1. Autorouters usable with KiCad 10

| Name | What | KiCad ver | License | Stars / last commit | 4L dense? | Take? | Gaps |
|---|---|---|---|---|---|---|---|
| [Freerouting 2.5.0](https://github.com/freerouting/freerouting) | Java/GraalVM autorouter, DSN in / SES out; also IPC plugin for KiCad 10. CLI: `-de -do -dr -drc -mp -mt -inc -us {greedy,global,hybrid} -hr -is -im --router.layers.routable --router.optimizer.improvement_threshold` (`-oit` deprecated); REST API server. v2.5.0 (2026-10-05) claims 30.9%→75% clean-completion, copper-pour awareness, pre-existing-DRC detection | 9, 10 | GPL-3.0 | 2.1k / Oct 2026 | Partly | Yes, as batch stage | DSN carries only netclass width/clearance/via; `class_class`, custom `.kicad_dru` rules and per-pair clearances are dropped ([forum](https://forum.kicad.info/t/solved-kicad-9-01-freerouting-2-01-drc-not-transferred/60202)). `(type protect)` wires are fixed-but-not-connectivity: partial rip-ups never complete a net; with everything protected it makes zero progress (this project, 2026-10-11). Boxes dense module escapes in by using the no-via zone as a highway; fragments GND pours. |
| [kicad-agent-toolkit](https://github.com/nexatech-ltd/kicad-agent-toolkit) (nexatech) | 180 CLI tools: Freerouting rounds with monotone per-net acceptance (accepted nets locked, failed nets retried), `maze_route.py`, PyTorch GPU wavefront router with regional rip-up, `stitch_gnd.py`, `sync_board.py`, `verify.py`, `gate.sh` | 10 (kicad-cli + SWIG pcbnew) | Apache-2.0 | 0 / v0.1.0 released days ago (page shows "Oct 4"; year unverified) | Unknown, proven only on their 6-layer 370-fp board | Take the pattern (rounds + acceptance + gate), evaluate code | Brand new, single author, SWIG-based (fragile across KiCad 10.x), needs Java 25 + CUDA. |
| [KiCadRoutingTools](https://github.com/atomic14/KiCadRoutingTools) | Rust A* octilinear multilayer router, diff pairs, trombone length match, corridors/keepouts, BGA/QFN escape, pure-file parse/write, pure-Python DRC, Claude Code skills | 9, 10 | MIT | ~107 / Apr 2026 | Yes for signal nets | Yes, as incremental per-net router | No push-and-shove; no layer swap for stubs; no rule regions; own DRC, not KiCad's. |
| [rjwalters/kicad-tools](https://github.com/rjwalters/kicad-tools) | `kct route` (grid/lattice/Delaunay engines), force-directed + GA placement, pure-Python DRC, MCP server | 8+ | MIT | 70 / active | Partly | Evaluate; overlaps with above | Round-trip writer risk; DRC not KiCad's. |
| [DeepPCB plugin](https://github.com/instadeepai/deeppcb-kicad-plugin) | Cloud RL place+route, plugin open source; 1 credit = $1, 0.5 credit/min, 30 free min ≤150 airwires; 8 layers / 1,200 airwires ([pricing](https://deeppcb.ai/pricing/)) | plugin README says 6+, blog says 10+ | Apache-2.0 plugin, engine closed | 66 / May 2026 beta | Probably | Optional benchmark only (closed engine violates "OSS only") | Unknown handling of keepouts/locked tracks; board leaves machine. |
| [Quilter](https://quilter.ai) | Closed cloud full-layout; per-pin pricing, annual commitments, quote-based | KiCad import/export | Closed | n/a | n/a | No | Closed, enterprise pricing. |
| [OrthoRoute](https://github.com/bbenchoff/OrthoRoute) | GPU PathFinder over IPC API | 10 (API server) | MIT | 420 | No (2% clean on OSS boards) | No | Built for huge backplanes. |
| [PCBWorld](https://github.com/LGAI-Research/PCBWorld) | Gymnasium env wrapping KiCad 9.0.8 push-and-shove; RL + LLM tool-calling agents; 679 real boards bench ([arXiv 2607.05915](https://arxiv.org/abs/2607.05915)) | 9.0.8 engine submodule | BSD-3 (env), GPLv3 engine | 31 / 2 commits | Research only | Take ideas (action schema, engine-grounded reward) | Not KiCad 10, no trained weights shipped as a tool. |
| [PCBEnv2](https://pypi.org/project/pcbenv/) | RL routing env, 2026.1.0 | none | GPL-3.0 | unverified | No | No | No KiCad I/O. |
| [freeroute (Python)](https://git.supported.systems/warehack.ing/freeroute) | Java-free Freerouting reimplementation, rip-up-retry maze | DSN/SES | unverified | unverified | Unknown | Watch | Single-dev, Gitea-hosted. |
| KiCad PNS router via IPC | `run_action("pcbnew.InteractiveRouter.*")` toggles the tool; no API to feed a path/drag. GUI must be running in 9/10; headless `kicad-cli api-server` only in 11 ([dev-docs](https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/for-addon-developers/)) | 10 | GPL | n/a | n/a | Use for commits/undo, not routing | Cannot script push-and-shove in 10. |

## 2. Placement

| Name | What | KiCad ver | License | Stars/commit | 4L dense? | Take? | Gaps |
|---|---|---|---|---|---|---|---|
| kicad-tools `kct placement` | Force-directed + GA optimizer | 8+ | MIT | 70 | Yes | Evaluate | Netlength-only objective; no thermal/RF constraints. |
| kicad-agent-toolkit placement tools | "Placement optimization" scripts | 10 | Apache-2.0 | 0 | Unknown | Evaluate | Undocumented. |
| KiCad 10 Multichannel (built-in) | Rule-zone-based channel replication, replaces Replicate Layout; bug fixed in 10.0.5 RC1 ([forum](https://forum.kicad.info/t/replicate-layout/70424)) | 10 | GPL | n/a | n/a | Yes, for repeated channels | Not scriptable from IPC (unverified). |
| [Replicate Layout](https://github.com/MitjaNemec/ReplicateLayout) | Hierarchical replication | ≤9 | GPL | greyed out in 10 PCM | n/a | No | Dead on 10. |
| [KiKit 1.8.1](https://github.com/yaqwsx/KiKit) | Panelization/export, multi-board | 9, 10 | MIT | large / Aug 2026 | n/a | Yes for fab outputs | No placement. |
| [kbplacer](https://github.com/adamws/kicad-kbplacer), HierPlace, kle-placement-router | Keyboard/hierarchy placement | kbplacer 10; others stale | GPL/MIT | various | No | No | Domain-specific. |
| Polar/circular placement | No public helper found; this project's own `scripts/` polar placer is the only one seen | 10 | ours | — | Yes | Keep ours | Unverified that none exists. |

## 3. Fan-out and stitching

| Name | What | KiCad ver | License | Stars | 4L dense? | Take? | Gaps |
|---|---|---|---|---|---|---|---|
| [weirdgyn/viastitching](https://github.com/weirdgyn/viastitching) | Zone via arrays (grid/stagger/random), collision check, remove | 6+, reported OK on 10 | MIT | 110 | Yes | Yes | SWIG; no fence-along-track. |
| kicad-action-scripts ViaStitching | Older stitcher | broken on 10 | GPL | — | No | No | Legacy API. |
| KiCad native via-stitching zones | MR in progress ([forum](https://forum.kicad.info/t/via-stitching-in-kicad-v10/68443)) | 11? | GPL | — | — | Wait | Not in 10. |
| Teardrops | Built-in since KiCad 8 (knowledge, not re-verified) | 8+ | GPL | — | Yes | Yes | IPC exposure unverified. |
| Length tuning | KiCad 10 rebuilt tuning, time-domain constraints, tuning profiles ([release](https://www.kicad.org/blog/2026/03/Version-10.0.0-Released/)) | 10 | GPL | — | Yes | Yes | GUI tool; no IPC path to drive it (unverified). KiCadRoutingTools has trombone tuner in files. |
| BGA/QFN fan-out | KiCadRoutingTools escape generator; [OneKiwiTech/kicad-fanout-tool](https://github.com/OneKiwiTech/kicad-fanout-tool) (unverified on 10) | 9/10 | MIT | — | Yes | KiCadRoutingTools | No LGA-under-keepout awareness. |
| Round tracks | mitxela Round Tracks (RF Tools breaks tuning) | 10 | GPL | — | Yes | Optional | Cosmetic. |

## 4. Human + agent hybrid

| Name | What | KiCad ver | License | Stars | Take? | Gaps |
|---|---|---|---|---|---|---|
| [kicad-agentic-mcp](https://github.com/nevenfo/kicad-agentic-mcp) | Rust MCP, 202 tools over IPC; edits land in the live editor, undoable with Ctrl+Z; verification via kicad-cli ERC/DRC (posted 2026-08-27) | 10 | AGPL-3.0 | unverified | Take the "edit via IPC, human undoes" pattern | No explicit accept gate, no screenshots to LLM, slow (6-7 min/turn), macOS unsigned. |
| [mixelpixx/KiCAD-MCP-Server](https://github.com/mixelpixx/KiCAD-MCP-Server) | kicad-python MCP; PNG render of board/selection, select + invoke actions | 9/10 | MIT | 46 (2025) | Take the region-render tool | Stale. |
| [lamaalrajih/kicad-mcp](https://github.com/lamaalrajih/kicad-mcp) | Freerouting pipeline, DRC tool | 9/10 | MIT | — | Reference | File-based. |
| kicad-cli `pcb render` / `pcb export svg` | `--side --width --height --quality --perspective`; SVG per layer; crop regions downstream | 10 | GPL | — | Yes, for LLM inspection | No region crop flag; crop in Python. |
| pcbnew shape collision | `SHAPE_POLY_SET`/`Collide()` via SWIG; our `grid_router.py` uses rasterized pair clearances instead | 10 | GPL | — | Keep ours | No off-the-shelf collision-checked routing library found. |
| Propose-then-accept in GUI | Nothing found that renders a proposal as a ghost and lets a human click accept | — | — | — | Build: IPC commit per net + `drop_commit` on reject | Missing. |

## 5. Verification after routing

| Name | What | KiCad ver | License | Take? | Gaps |
|---|---|---|---|---|---|
| `kicad-cli pcb drc --format json --schematic-parity --all-track-errors --severity-all --exit-code-violations` | JSON `$schema` drc.v1: `violations[]`, `unconnected_items[]`, `schematic_parity[]`, each `{type, severity, description, excluded, items[{uuid, description, pos{x,y}}]}`; exit 5 on violations ([CLI ref](https://docs.kicad.org/10.0/en/cli/cli.html)) | 10 | GPL | Yes, the gate | Parity needs `.kicad_sch` beside the board (project note); custom-rule exclusions can show as errors ([#24264](https://gitlab.com/kicad/code/kicad/-/issues/24264)). |
| kicad-agent-toolkit `verify.py`/`gate.sh` | Decoupling path length, unconnected pins, IR drop on real copper, power sequencing, RF plane continuity | 10 | Apache-2.0 | Yes | Unproven outside author's board. |
| [gerber2ems](https://github.com/antmicro/gerber2ems) | Gerbers → openEMS FDTD SI sim | any | Apache-2.0, 223 stars | For the antenna cavity only | Minutes-hours runtime, manual mesh. |
| EMF Inspector | Pure-Python EMI heatmap + 12 heuristics ([engrXiv](https://engrxiv.org/preprint/view/7226)) | file-based | unverified | Watch | No repo URL found. |
| FOSSEE Power Integrity Analyzer | IPC-2221 width, IR drop, decap distance | 9 | unverified | Watch | Repo not found. |
| KiCadRoutingTools / kicad-tools DRC | Pure-Python DRC, creepage audit | 8-10 | MIT | Pre-check only | Not authoritative. |

## Parts we should take
Freerouting 2.5.0 CLI (`-mp -us hybrid -inc`, `-drc` JSON) as the bulk stage; kicad-agent-toolkit's round/acceptance/gate structure; KiCadRoutingTools as the per-net incremental router with corridors and keepouts; viastitching; KiCad 10 built-in tuning/teardrops/multichannel; kicad-cli DRC JSON + parity as the only truth; kicad-python IPC for commit/undo and selection; kicad-cli render + Python crop for LLM inspection; PCBWorld's action schema as the agent interface design.

## Parts missing
No OSS router honors `.kicad_dru` custom rules or no-via regions (must be modelled as keepouts or pre-stripped); no scriptable push-and-shove in KiCad 10 (11 adds headless); no propose/accept UI; no polar placement helper; no maintained IPC-native via fence/fan-out; no light IR-drop/EMC tool with a verified repo.

## Recommended strategy
Treat routing as per-net transactions, never whole-board autorouting. Agent plans channels first (reserve B.Cu under the FDC for local nets, define corridors), then routes nets in priority order with KiCadRoutingTools or our grid router under KiCad's own clearances, committing each net through the IPC API so the human sees it live and can Ctrl+Z; every commit is followed by `kicad-cli pcb drc --format json` and accepted only if violations and unconnected count are monotone non-increasing (the nexatech acceptance rule). Use Freerouting 2.5 only on the remaining easy nets with hard nets protected and its DSN limitations documented, then re-run the gate. The human handles the few chokepoint nets with push-and-shove in the GUI, which is the one thing no open tool can script in KiCad 10; the agent renders cropped regions and proposes alternatives (pin swap, channel re-plan) rather than brute-forcing.
