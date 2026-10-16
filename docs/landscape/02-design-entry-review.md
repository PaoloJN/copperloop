# Survey: design entry, schematic generation, review (2026-10-16)

Verified via GitHub/PyPI/docs fetches today unless marked **(unverified)**. "Last commit" dates were often not exposed by the fetch; I give latest release date instead.

## 1. Code-to-schematic / code-to-board

| Name | What | Output | KiCad ver | License | Stars / latest | Agent-friendly? | Take? | Gaps |
|---|---|---|---|---|---|---|---|---|
| [atopile](https://github.com/atopile/atopile) | `.ato` DSL, constraint solver, auto part picking, writes/updates `.kicad_pcb` | `.kicad_pcb` only; **no schematic** | Not stated anywhere; Py ≥3.14 req. KiCad 10 compat unverified | MIT | 4.0k; v0.15.9 (2026-09-12) | Yes: declarative text, ships `CLAUDE.md`/`.cursor`; models write ato for EEBench | Yes, as the design-capture + part-pick layer | No `.kicad_sch`; KiCad 10 support unconfirmed; opinionated toolchain |
| [tscircuit](https://github.com/tscircuit/tscircuit) + [circuit-json-to-kicad](https://github.com/tscircuit/circuit-json-to-kicad) | React/TSX circuits → Circuit JSON | `.kicad_sch` (hierarchical), `.kicad_pcb`, `.kicad_pro`, KiCad library (`tsci export -f kicad-library`) | Not stated | MIT | 2.8k (converter 9); active | Yes: "prompt your agent to use tscircuit", text-to-footprint AI | Maybe: only OSS DSL that emits a full project incl. schematic | JS ecosystem; converter young (9 stars); KiCad 10 format unverified |
| [SKiDL](https://github.com/devbisme/skidl) + [schematizer](https://pypi.org/project/schematizer/) | Python netlist DSL; schematizer turns JSON netlist → placed/routed `.kicad_sch` | netlist, XML BOM, DOT, `.kicad_sch`/SVG | KiCad 5–10 (schematic out: 6–10) | MIT | 1.7k; SKiDL 3.0.0 (2026-10-16!), schematizer 0.2.0 (2026-10-13) | Yes: plain Python, stable API | Yes: Python netlist + schematic drawing | Auto-placed schematics are "readable-ish", not pretty; 3.0 is days old |
| [kicad-skip](https://github.com/psychogenic/kicad-skip) | Generic s-expr read/write for sch/pcb | in-place edits | 7+ | LGPL-2.1 | 231; last commit 2024-04-04 | OK for scripted edits | Reference only | Stale; no 9/10 format validation |
| [kicad-sch-api](https://github.com/circuit-synth/kicad-sch-api) / circuit-synth | Byte-exact `.kicad_sch` writer + 15-tool MCP server | `.kicad_sch` | states 7/8 only | MIT | 54; 0.5.6 (2025-11-19) | Yes (MCP) | Borrow ideas (grid-aligned placement, format preservation) | 9/10 unverified; small |
| [akcli-kicad](https://github.com/tipoLi5890/akcli) | JSON op-list → `.kicad_sch`, ERC-lite, review, ngspice sim, Claude/Codex/OpenCode plugins | `.kicad_sch` | not stated | MIT | 9; 0.22.0 (2026-08-25) | Designed for agents | Watch; borrow op-list + undo pattern | Tiny community |
| [JITX](https://docs.jitx.com/cad-integration/kicad-export.html) | Stanza code → full board; VS Code ext. | Exports KiCad project (docs say KiCad 7/8) | 7/8 | Proprietary; free tier requires CERN-OHL + telemetry, JITX keeps copies | n/a | Yes but closed | No (closed) | Open only: [open-components-database](https://github.com/JITx-Inc/open-components-database) |
| Flux.ai | Browser EDA | Imports KiCad; **no** native KiCad export | — | Closed | — | — | No | Lock-in |
| Quilter | Cloud placement+routing, takes KiCad files | KiCad | — | Closed, ~€80–200/iteration (unverified) | — | — | No | Budget |
| [DeepPCB plugin](https://github.com/instadeepai/deeppcb-kicad-plugin) | KiCad plugin, cloud routing, credits | KiCad | 6+ (blog says 10+) | Plugin Apache-2.0, engine closed | 66 | API key | Note only | Cloud/paid |
| heypcb | Browser AI EDA | ? | — | Closed | — | — | No | See §5 |

## 2. Schematic review & analysis

| Name | What | Output | KiCad | License | Stars/latest | Agent? | Take? | Gaps |
|---|---|---|---|---|---|---|---|---|
| [kicad-cli sch erc](https://docs.kicad.org/10.0/en/cli/cli.html) | Official ERC; also `export netlist --format spice/spicemodel`, bom, pdf/svg | JSON/report | 10 | GPL | — | Yes (headless) | Yes, baseline gate | Syntactic only |
| [kicad-happy](https://github.com/aklofas/kicad-happy) | 11 Claude Code/Codex skills + GitHub Action: schematic/PCB/Gerber parse, design review, DFM, datasheet-extracted specs cached per MPN with `confidence: datasheet-backed`, SPICE testbenches, EMC 44 rules, distributor/BOM skills | findings w/ severity + confidence | 5–10 | MIT | 1.4k; v2.3.1 | Built for agents, stdlib-only Python | **Yes** (already installed in this repo's skills) | Heuristics; needs real datasheets |
| [rjwalters/kicad-tools](https://github.com/rjwalters/kicad-tools) | Python toolkit + MCP: ERC w/ auto-repair, net trace, `sch tidy`, autorouter, placement, creepage audits, ee-review skill | JSON | 8+ | MIT | 70; 5.5k commits | Yes (MCP) | Pick pieces (ERC repair, sch tidy) | Single-author |
| [DRCY](https://arxiv.org/abs/2603.15672) (AllSpice) | 5-agent pin-by-pin datasheet review as CI action | inline review comments | — | Paper 2026-03-13; code OSS? **unverified**, likely closed | — | Yes | Pattern to copy, not code | No metrics in abstract |
| [Traceformer.io](https://forum.kicad.info/t/llm-driven-tool-for-catching-pcb-schematic-errors/65687) | SaaS LLM datasheet-grounded review, OSS KiCad export plugin | web | — | Closed; free = 1 review/mo | — | — | No | SaaS |
| [EEBench](https://www.eebench.org/) ([benchlm](https://benchlm.ai/benchmarks/eebench)) | atopile-run benchmark: 13 tasks (V1), models write ato, graded by deterministic SPICE at tolerance corners; score = 0.65 performance + 0.35 cost vs reference BOM. Launch: Opus 5 61.6%, Grok 4.6 57.1%; 2026-10-12 snapshot: Opus 5.5 75.0%, GPT-6 Astra 69.3%, Sonnet 5.5 67.2% | leaderboard | — | "open-source" per secondary sources; repo URL **unverified** (atopile/eebench 404) | 27 models | — | Use as eval model for our verification loop | Only 13 tasks; atopile-centric; no layout stage |

## 3. Simulation

| Name | What | KiCad | License | Status | Agent? | Take? | Gaps |
|---|---|---|---|---|---|---|---|
| kicad-cli + ngspice | `kicad-cli sch export netlist --format spice` then run ngspice CLI; **no sim subcommand** in kicad-cli 10 | 10 | GPL | current | Yes | Yes, headless path | Must inject `.control` blocks yourself |
| [spicelib](https://pypi.org/project/spicelib) | Python driver for ngspice/LTspice/Xyce/QSPICE; raw-file parsing, sweeps | — | GPL-3 | pushed 2026-05 | Yes | Yes (over PySpice) | — |
| [PySpice](https://pypi.org/project/PySpice/) | ngspice bindings | — | GPL-3 | 1.5, 2021-05; ngspice ≤34 | — | No | Stale |
| kicad-happy `spice` / akcli sim | auto testbenches per subcircuit, Monte Carlo | 5–10 | MIT | active | Yes | Yes | Behavioural models |
| [openEMS](https://openems.readthedocs.io) + [pyems](https://github.com/matthuszagh/pyems) | FDTD; pyems adds auto-mesh, KiCad footprint gen | — | GPL-3 | pyems 105★, no PyPI | Scriptable | For antenna-under-glass study | No KiCad→openEMS importer (hyp2mat retired) |
| [gerber2ems](https://github.com/antmicro/gerber2ems) (Antmicro) | Gerbers+stackup → openEMS S-params/impedance, KiCad SI wrapper | any | Apache-2.0 | 269★ | Yes (CLI) | Yes, headless EM from our Gerbers | SI focus, not radiation patterns |

## 4. Component library automation

| Name | What | License | Status | Agent? | Take? | Gaps |
|---|---|---|---|---|---|---|
| KiCad official libs (gitlab.com/kicad/libraries) | symbols/footprints/3D | CC-BY-SA 4.0 | 10.x | file access | Yes | Coverage |
| [easyeda2kicad](https://github.com/uPesy/easyeda2kicad.py) | `--lcsc_id Cxxxx` → sym+fp+3D | AGPL-3.0 | 1.7k★; "KiCad 6+" | CLI, trivial | Yes (JLC parts) | Quality unguaranteed; AGPL |
| [kicad-library-utils](https://gitlab.com/kicad/libraries/kicad-library-utils) | `klc-check/check_symbol.py`, `check_footprint.py` | GPL-3 | Debian snapshot 2026-08-29; a fetch showed an "archived" banner — **conflict, verify** | CLI | Yes as lint gate | — |
| SnapMagic/SnapEDA | web downloads free/unlimited w/ account; [API](https://www.snapeda.com/get-api) "free and Premium", form-gated, no public limits | Closed | — | API opaque | Optional | ToS |
| Ultra Librarian | free KiCad export, 50 downloads/day/user; no public API found | Closed | — | No | No | — |

## 5. Reference-design discovery

| Name | What | API | Take? | Gaps |
|---|---|---|---|---|
| [Kitspace v2](https://github.com/kitspace/kitspace-v2) | OSS board registry, Gitea backend, `boards.txt` + `kitspace.yaml` | No documented API; v1 `registry.json` in archived repo | Scrape `boards.txt` | AGPL; 34★ |
| [OSHWA cert API](https://certificationapi.oshwa.org/documentation) | certified projects, read+write | REST, Bearer token (free signup, 100-day expiry) | Yes | Points to docs URLs, not KiCad files |
| [Hackaday.io API](https://dev.hackaday.io/) | `/projects`, `/search`, `/projects/:id/components` | OAuth2, JSON | Yes | Few repos linked |
| [GitHub topic `kicad`](https://github.com/topics/kicad) | 5,095 repos | GitHub Search API: `topic:kicad`, `filename:*.kicad_pro` | **Yes, primary** | Licence/quality triage |
| heypcb Circuit World | 8,800 open boards indexed by component (press, 2026) | None; closed | Note only | Scrape = ToS risk |

Agent import recipe: GitHub code search for `.kicad_pro` + MPN → clone → `kicad-cli sch export netlist` / `pcb export` → kicad-happy pattern detection → lift subcircuit via kicad-skip/kicad-sch-api.

## Parts we should take
1. **kicad-cli** (ERC, DRC, SPICE netlist, renders) as every gate.
2. **kicad-happy** for review, datasheet-backed checks, SPICE testbenches, EMC; **kicad-tools** for ERC auto-repair / `sch tidy`.
3. **SKiDL 3 + schematizer** for Python-defined netlists that still produce an editable `.kicad_sch` (6–10); **tscircuit's circuit-json-to-kicad** as the alternative full-project emitter.
4. **atopile** as agent-facing design DSL if we accept pcb-only output; its EEBench scoring loop (SPICE at tolerance corners, 0.65/0.35 perf/cost) is the verification template.
5. **spicelib** + ngspice; **gerber2ems** for headless EM.
6. **easyeda2kicad** + **KLC checkers** for library ingest/lint.
7. Discovery: GitHub Search API, OSHWA API, Hackaday.io API, Kitspace `boards.txt`.

## Parts missing
- No OSS tool proves `.kicad_sch` output against **KiCad 10** format (claims stop at 7/8 or are unstated).
- KiCad 10 IPC API has **no schematic commands** (slated for v11); schematic automation is file-level only.
- No OSS, open-weights datasheet-grounded pin checker with published accuracy (DRCY/Traceformer closed; kicad-happy heuristic).
- `kicad-cli` cannot run ngspice; no standard testbench format.
- No KiCad→openEMS importer for antenna radiation (only SI via gerber2ems).
- EEBench: 13 tasks, atopile-only, no layout/fab stage; repo location unverified.
- No open index of KiCad reference designs searchable by MPN (heypcb has one, closed).
