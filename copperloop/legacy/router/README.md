# Router pipeline (2026-10-11)

Freerouting 2.5.0 driven from scripts, with KiCad 10 Python for board edits.
Set `ROUTE_WORK` (scratch dir with a `drc/` subdir holding a copy of
`puck-carrier.kicad_pro`, `fp-lib-table` and a `lib` symlink) and
`FREEROUTING_JAR` before use. Close KiCad first.

Order that worked best (see docs/changelog.md 2026-10-11 routing entry):

1. `fanout_planes.py` — one via per 3V3 pad into the In2 plane (and listed GND pads).
2. `route_manual.py` — hand routes under the FDC pads (no foreign via allowed there).
3. `router_export.py` — DSN "router view": no copper fills, outer-layer rule
   areas only, existing wiring protected, complete nets hidden, widths capped
   at 0.25 mm, In2 optionally routable (`--route-inner PWR`).
4. `freeroute.sh` — fan-out off, neck-down off, planes not obstacles.
5. `import.sh` — session import + DRC with the project file beside the board.
6. `round.sh` — stitch GND pads the pours lost, strip neck-downs, re-export
   with the still-open nets, route, import, DRC. Repeat while it improves.
7. `bridge.sh` / `net_islands.py` — expose one pin per GND/3V3 island so the
   router only bridges islands.

Freerouting ignores `class_class` clearance rules and does not count protected
wiring as connectivity, so the tool reports ~40 more opens than KiCad does.

## Grid router tools (2026-10-11 night)

For the last connections, where Freerouting stalls, a raster A* router with
KiCad's own clearances. Everything runs on scratch copies; DRC is authoritative.

1. `geom_export.py board out.json` (KiCad Python) — pads/tracks/vias/fills/keepouts.
2. `uv run --with numpy,scipy,shapely python3 grid_router.py geom.json plans.json --nets A B [--inner] [--rip]`
   — joins each net's connectivity islands; `--rip` lists crossed tracks in `remove`.
3. `apply_plans.py board plans.json out` (KiCad Python) — rips textually, adds with
   the `routelib` collision check, refills zones.
4. `gnd_stitch.py geom.json plans.json` — one via per orphan pour island, names the pads on it.
5. `plot_region.py geom.json out.png x0 y0 x1 y1 [--nets ..] [--plans ..]` — look before routing.
6. `riploop.sh start tag N` — the rip-up iteration; it diverged on this board (see changelog).
`strip_region.py` / `strip_nets_region.py` clear a box for a regional re-route; `pin_swap.py`
moves four module nets to spare pads (schematic + board, parity-checked, not applied).
