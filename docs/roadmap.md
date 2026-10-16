# Roadmap

Driven by the Water Puck carrier (sensei-cup). A feature is added when that board needs it.

## Milestone 1 — the loop exists (Oct 2026)
- [x] Landscape survey (docs/landscape)
- [ ] `cl connect`: find the open board over IPC, print name, layers, net count
- [ ] `cl see X Y W H [--layers F.Cu,B.Cu,...]`: region PNG per layer via kicad-cli svg + crop
- [ ] `cl gate`: kicad-cli DRC json + schematic parity, one-line verdict, diff vs last run
- [ ] `cl fanout NET`: stub + via per pad into a plane, one IPC commit per pad, gate after
- [ ] Prove: 3V3 fully fanned out on the puck, live, 0 new errors, no file copying

## Milestone 2 — per-net routing transactions
- [ ] `cl route NET`: plan (collision-checked, our routelib / KiCadRoutingTools) → IPC commit → gate → keep/drop
- [ ] `cl stitch`: GND via fence/array with the same gate
- [ ] Freerouting rounds with per-net acceptance for the easy leftovers (nexatech pattern)
- [ ] Violation → picture: render the region around each DRC item

## Milestone 3 — package and stages
- [ ] Skills: one per stage (research, schematic review, routing, fab), kicad-happy style
- [ ] Thin MIT MCP wrapping the same commands with mutation gating (kipilot pattern)
- [ ] Fab stage: gerbers/drill/pos, JLC .kicad_dru, DFM diff vs JLC capabilities
- [ ] Research stage: DigiKey/Mouser/jlcparts lookups, reference-design import
- [ ] Bring-up stage: probe-rs flash, OpenHTF test log

## Later
- KiCad 11: headless IPC, IPC DRC/plot, schematic API → drop SWIG adapter and most file surgery
- Second board (not the puck) to prove generality
