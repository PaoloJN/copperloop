# Landscape: research, parts, fabrication (2026-10-16)

Legend: **V** = verified from primary page today; **U** = unverified / secondary source only.

## 1. Parts search and data APIs

| Name | What | API/auth | Free tier | Data license | Status | Take? | Gaps |
|---|---|---|---|---|---|---|---|
| DigiKey Product Information v4 (https://developer.digikey.com) | Keyword/MPN search, product details, categories; price breaks, stock, datasheet URL, parameters, lifecycle (V) | OAuth2 client credentials; sandbox + prod | 120 req/min, 1000 req/day default (V); higher on request | Agreement forbids building your own DB from DK data, bulk download, redistribution (V, https://developer.digikey.com/api-user-agreement) | Live | Yes, primary | Cache only per-project; no shared parts DB |
| Mouser Search API (https://www.mouser.com/api-hub/) | Keyword/MPN search, price, stock, datasheet URL, lifecycle, attributes | UUID API key as query param (V) | 30 calls/min, 1000/day, 50 results/call (V via https://www.mouser.com/en/api-search/) | Terms at mouser.com/en/apiterms (U details) | Live | Yes, second source | Blocks automated PDF download |
| Nexar / Octopart (https://nexar.com) | GraphQL aggregation across distributors, specs, datasheets, lifecycle | OAuth2 client credentials | "Welcome 1K" 1000 calls/mo or 100 matched parts eval (U, conflicting pages) | Max 24 h cache, no self-hosting datasheets/images, octopart.com attribution (V, https://nexar.com/api/legal) | Live, Altium-owned | Optional (cross-distributor pricing) | Cache rule conflicts with agent memory |
| JLCPCB official API (https://api.jlcpcb.com) | Components API (price/stock), PCB quote/order, stencil, 3D print (V) | Developer account + "apply for free API access"; approval gated on account/business profile (U) | Free once approved (V landing page) | Not published (U) | Live | Apply; fallback below | Rate limits/approval criteria undocumented |
| yaqwsx/jlcparts (https://github.com/yaqwsx/jlcparts, https://yaqwsx.github.io/jlcparts/) | Scraped JLC assembly catalog: attributes, price tiers, stock, datasheet + LCSC page links; CI-rebuilt from JLC XLS (V) | None, static JSON/SQLite | Free | Code MIT (V); data = JLC's, unlicensed (U) | Maintained | Yes, offline search | Stock staleness |
| tscircuit/jlcsearch (https://jlcsearch.tscircuit.com) | Hosted search over jlcparts; append `.json` for API (V) | None | Free, unauthenticated | Same caveat as above | Live | Yes, quick lookups | No SLA |
| LCSC official | No public API found (U); use jlcparts/JLC Components API | — | — | — | — | No | — |
| element14/Farnell/Newark (https://partner.element14.com) | Product Search API: price, stock, datasheet, attributes; XML/JSON (V) | 24-char API key; contract pricing needs HMAC signature (V) | Free key; no published rate limit (V), community uses ~0.5 s spacing (U) | Standard T&Cs (U) | Live | Secondary (EU/UK) | Limits undocumented |
| Arrow (https://developers.arrow.com) | Pricing & Availability + Order API, free (V) | API key after registration | Free (V) | Not reviewed (U) | Live | Low priority | Limits unknown |
| Aisler Part Service (beta) | Aggregates DigiKey/Farnell/Mouser/Arrow; free beta key via form (V, community.aisler.net) | API key | Free (beta) | U | Beta | Watch | Not a quote API |

## 2. Datasheet acquisition and parsing

| Name | What | API/auth | Free | License | Status | Take? | Gaps |
|---|---|---|---|---|---|---|---|
| kicad-happy `digikey` + `datasheets` skills (https://github.com/aklofas/kicad-happy) | Sync PDFs per MPN from DK/LCSC/e14/Mouser into `datasheets/`; LLM extract to JSON (pinout, electrical, abs max, package) cached per-MPN with quality score (V) | Uses distributor keys | Free | MIT (V) | Active, already installed here | Yes | Extraction is LLM-based, needs manual spot checks |
| datasheet-cli (https://docs.rs/crate/datasheet-cli) | Rust CLI, LLM (Gemini vision) extracts pinout/config JSON (U) | Gemini key | Depends on LLM | U | Early (0.1.x) | Maybe | Vendor LLM dependency |
| adom-ds2sf (https://wiki.adom.inc/adom/adom-ds2sf) | Datasheet -> pins + land pattern JSON with per-field page provenance (U) | — | — | U | Early | Evaluate | Not on GitHub/PyPI as far as found |
| Open corpora | Zenodo 2020 datasheet corpus (transistors, opamps, connectors) https://zenodo.org/record/4558344; Open Schematics 84k .kicad_sch on HF (U) | — | Free | Per-dataset | Static | Reference only | No general MPN->PDF corpus; distributors forbid self-hosting |

Approach: PDF text via pdfplumber/pymupdf, tables via camelot/LLM; store extraction JSON next to PDF with page provenance (ds2sf pattern).

## 3. BOM and assembly

| Name | What | KiCad 10 status | License | Take? | Gaps |
|---|---|---|---|---|---|
| KiCad built-in `kicad-cli sch export bom` / `pcb export pos` | Native BOM/CPL, variants in v10 | Native | GPL | Yes, baseline | Needs JLC column mapping |
| Fabrication Toolkit (https://github.com/bennymeg/Fabrication-Toolkit) | One-click JLC Gerber+BOM+CPL | Works; design-variants bug: always exports default variant (V forum, 2026) | MIT | Yes (no variants) | Variant bug |
| kicad-jlcpcb-tools (https://github.com/Bouni/kicad-jlcpcb-tools) | Assign LCSC parts from JLC DB inside KiCad, BOM/CPL, rotation fixes | 2026.04.01 "brings KiCad 10 support" (V) | MIT | Yes | GUI-only, not CI |
| KiBot (https://kibot.readthedocs.io) | YAML-driven CI export: Gerbers, BOM, iBoM, 3D, DRC/ERC, panels, JLC templates | v1.9.0 (2026-05-12) KiCad 10.0.1; v1.9.1 (2026-07-28) workarounds; native variants experimental (V) | AGPL-3 | Yes, pipeline backbone | Docker image large |
| KiKit (https://github.com/yaqwsx/KiKit) | Panelization, mousebites, multi-board, fab export | 1.8.0/1.8.1 (2026) claim KiCad 10 support (U, PyPI date Aug 2026) | MIT | Yes (if panelizing) | Reinstall per KiCad update |
| InteractiveHtmlBom (https://github.com/openscopeproject/InteractiveHtmlBom) | Searchable HTML assembly BOM | 2.11.1 breaks on KiCad 10.0.1 NPTH pads; fixed in master, release pending (V forum) | MIT | Yes (master) | Wait for release |

## 4. Fab quoting and DFM

| Name | What | API/auth | Status | Take? | Gaps |
|---|---|---|---|---|---|
| JLCPCB capabilities (https://jlcpcb.com/capabilities/pcb-capabilities, /pcb-assembly-capabilities) | 4L: 0.09/0.09 mm trace/space, via 0.25/0.15 mm, annular ring 0.15 min / 0.20 rec, hole-to-copper 0.2 mm, ENIG, ±10% impedance (V). PCBA: **both tiers do single and double-sided SMT**; Economic min 0402, 0.5 mm BGA; Standard 01005, 0.3 mm (V) | Quote API via api.jlcpcb.com (approval) | Live | Yes | Our board (0402 both faces, 4L) fits Economic on paper; LGA/OLGA confirm |
| PCBWay Partner API (https://www.pcbway.com/api_cooperation.html) | PCB quote/order endpoints at api-partner.pcbway.com; Assembly API "under construction"; email approval (V) | Partner approval | Live, gated | No for now | No PCBA quote |
| OSH Park API (https://oshpark.com/developer) | REST JSON: uploads, projects, orders; session token (V) | Account | Live | Optional (US 4L) | No pricing endpoint seen |
| Aisler | No public quote API found (U) | — | — | No | — |
| Eurocircuits | No public API found (U) | — | — | No | — |
| DRU rule files: labtroll/KiCad-DesignRules, Cimos/KiCad-CustomDesignRules (fork, JLC + PCBWay, KiCad 8 syntax forward-compatible), ziteh/kicad-design-rules (V URLs) | `.kicad_dru` custom rules matching JLC caps, layer-aware | Files | Maintained | Yes, pin one, diff vs JLC page quarterly | Not auto-updated |

## 5. Bring-up and test

| Name | What | License | Take? | Gaps |
|---|---|---|---|---|
| probe-rs (https://github.com/probe-rs/probe-rs) | Flash, debug, `probe-rs run` streams RTT/defmt; nRF52840_xxAA supported (V) | Apache-2/MIT | Yes | Needs SWD probe |
| pyOCD | `pyocd flash -t nrf52840` (V) | Apache-2 | Backup | — |
| nrfutil | Nordic's CLI; DFU over USB/BLE; **5-clause Nordic license, not OSI** (V) | Nordic | Only for BLE DFU packaging (adafruit-nrfutil is MIT) | Not OSS |
| OpenHTF (https://github.com/google/openhtf) | Python HW test phases, plugs, measurements, JSON logs; 1.6.1 (2025-03), active (V) | Apache-2 | Yes for commissioning gates | No BLE plug, write one |
| Test-log capture | OpenHTF JSON output + probe-rs RTT; no dedicated OSS tool found (U) | — | Script it | — |

## 6. Documentation patterns

- ADRs: Nygard format, `docs/decisions.md` or `docs/adr/NNNN-*.md`; EQ Wave uses ADR-XXX for HW/FW decisions (V). Current repo's `decisions.md` + `changelog.md` matches.
- HackRF (https://github.com/greatscottgadgets/hackrf): `firmware/ hardware/ host/ docs/ tools/ ci-scripts/`, Sphinx docs on RTD (V).
- Open Book (https://github.com/joeycastillo/The-Open-Book): one dir per board revision (`OSO-BOOK-C1`, `-C2`), `Fabrication Files/`, separate JLC vs PCBWay variants, BOM in README (V).
- Pattern to adopt: `hardware/<board>-vN/`, `docs/decisions.md`, `docs/changelog.md`, `fab/<vendor>/` outputs generated by KiBot in CI, keep-a-changelog style.

## Parts we should take

DigiKey v4 + Mouser (1000/day each, cache per project); jlcparts/jlcsearch for assembly-stock search; apply for JLCPCB API; kicad-happy datasheet sync + extract (already present); KiBot as CI backbone with Fabrication Toolkit / kicad-jlcpcb-tools for LCSC assignment; iBoM from master; Cimos `.kicad_dru` for JLC; probe-rs + OpenHTF for bring-up; HackRF/Open Book directory conventions.

## Parts missing

- No open, redistributable parts database: DigiKey and Nexar terms forbid it (24 h cap at Nexar). Agent memory must store MPN + query, not cached pricing.
- No public PCBA quote API outside gated JLC/PCBWay; PCBWay assembly API unfinished. Fallback: Playwright against the quote form.
- No official LCSC API; jlcparts data has no license.
- Datasheet extraction tools are all LLM-based and young; no benchmark corpus for pin-table accuracy.
- iBoM KiCad 10 release pending; Fabrication Toolkit ignores variants.
- Rate limits for element14/Arrow/JLC API undocumented (U).
- No OSS BLE OTA DFU test harness; nrfutil is not OSS.
