"""Grid A* router for the connections the autorouter left open.

    uv run --with numpy,scipy,shapely python3 grid_router.py geom.json plans.json --nets EC_A 5V ...
        [--inner] [--rip] [--step 0.05] [--via-cost 1.5] [--max-visit 4000000]

Reads the JSON from geom_export.py, builds per-net obstacle rasters (other-net
copper buffered by clearance + half width, KiCad pair clearances: 0.2 mm when
either net is an EC net, else 0.15), finds the connectivity islands of the net
(pads, tracks, vias and zone fills of that net) and joins the smallest island
to any other with an A* search over F.Cu/B.Cu (+In2 with --inner; In1 is the
ground plane and never routed). Through vias 0.6/0.3 only where a via clears
every other-net item on every layer and every no-via rule area.
--rip lets the path cross other signal tracks at a high cost; the crossed
tracks are listed in the plan's "remove" field and their nets must be routed
again afterwards. apply_plans.py puts the result on the board with KiCad's own
collision check and DRC stays authoritative.
"""
import json, sys, math, heapq, time, argparse
import numpy as np
from scipy import ndimage as ndi
from shapely import Polygon, Point, LineString, union_all, contains_xy, make_valid, STRtree

ap = argparse.ArgumentParser()
ap.add_argument('geom'); ap.add_argument('out'); ap.add_argument('--nets', nargs='+', required=True)
ap.add_argument('--inner', action='store_true'); ap.add_argument('--rip', action='store_true')
ap.add_argument('--step', type=float, default=0.05); ap.add_argument('--via-cost', type=float, default=1.5)
ap.add_argument('--rip-cost', type=float, default=1.5, help='extra cost per cell inside a rippable track')
ap.add_argument('--max-visit', type=int, default=4000000)
ap.add_argument('--width', type=float, default=0, help='force this track width (mm)')
ap.add_argument('--protect', nargs='*', default=[], help='extra nets that must not be ripped')
ap.add_argument('--layer-cost', nargs='*', default=[], help='LAYER=factor, e.g. F.Cu=3 to keep long runs off the top (0 F.Cu, 2 In2/PWR, 3 B.Cu)')
ap.add_argument('--ec-nets', nargs='*', default=None, help='nets that carry the larger pair clearance (default: the Water Puck EC set)')
ap.add_argument('--ec-clr', type=float, default=0.2); ap.add_argument('--clr', type=float, default=0.15)
ap.add_argument('--frozen', nargs='*', default=None, help='nets never ripped (default: GND, 3V3, power, sensor nets)')
ap.add_argument('--board-center', nargs=2, type=float, default=[150.0, 100.0]); ap.add_argument('--board-r', type=float, default=23.0)
ap.add_argument('--grid-origin', nargs=2, type=float, default=[127.0, 77.0]); ap.add_argument('--grid-size', type=float, default=46.0)
a = ap.parse_args()

CX, CY = a.board_center
STEP = a.step; X0, Y0 = a.grid_origin; N = int(round(a.grid_size / STEP)) + 1
X = X0 + np.arange(N) * STEP; Y = Y0 + np.arange(N) * STEP
EC = set(a.ec_nets) if a.ec_nets is not None else {'EC_A', 'EC_B', 'EC_SENSE_A', 'EC_SENSE_B', 'EC_BIAS', 'EC_BIAS_EN', 'EC_DRV_HI', 'EC_DRV_LO', '/EC_NODE_D', 'EXP_A4', 'EXP_A5'}
POWER = {'3V3', 'VBAT', 'VBUS', '5V', '/5V_RING', 'VSYS', '/BOOST_SW'}
FROZEN = (set(a.frozen) if a.frozen is not None else {'GND', '3V3', 'VBAT', 'VBUS', '5V', '/5V_RING', 'SHLD1', '/CIN1', '/CIN2', '/BOOST_SW', 'RING_DATA', 'VSYS'}) | set(a.protect)
ROUTABLE = [0, 3] + ([2] if a.inner else [])
M = 0.02                      # raster safety margin (mm)
VIA_D, VIA_R = 0.6, 0.3

def clr(n1, n2): return a.ec_clr if (n1 in EC or n2 in EC) else a.clr
def width(net): return a.width or (0.3 if net in POWER else 0.2)
def poly(rings): return make_valid(Polygon(rings[0], rings[1:]))
def arc_pts(s, m, e):
    ax, ay = s; bx, by = m; cx, cy = e
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-9: return [s, e]
    ux = ((ax*ax + ay*ay) * (by - cy) + (bx*bx + by*by) * (cy - ay) + (cx*cx + cy*cy) * (ay - by)) / d
    uy = ((ax*ax + ay*ay) * (cx - bx) + (bx*bx + by*by) * (ax - cx) + (cx*cx + cy*cy) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy); a0 = math.atan2(ay - uy, ax - ux); a1 = math.atan2(by - uy, bx - ux); a2 = math.atan2(cy - uy, cx - ux)
    def norm(t): return (t + 2 * math.pi) % (2 * math.pi)
    sweep = norm(a2 - a0); mid = norm(a1 - a0)
    if mid > sweep: sweep -= 2 * math.pi
    n = max(4, int(abs(sweep) * r / 0.1))
    return [(ux + r * math.cos(a0 + sweep * i / n), uy + r * math.sin(a0 + sweep * i / n)) for i in range(n + 1)]

D = json.load(open(a.geom))
items = []   # (rec, geometry, layers)
for q in D['items']:
    if q['kind'] == 'pad': g = union_all([poly(p) for p in q['polys']]); ls = [q['layer']]
    elif q['kind'] == 'via': g = Point(q['pos']).buffer(q['width'] / 2, quad_segs=16); ls = [0, 1, 2, 3]
    else:
        pts = arc_pts(q['start'], q['mid'], q['end']) if 'mid' in q else [q['start'], q['end']]
        g = LineString(pts).buffer(q['width'] / 2, quad_segs=8); ls = [q['layer']]
    items.append((q, g, ls))
fills = [(z, poly(p)) for z in D['fills'] for p in z['polys']]
keeps = [(k, union_all([poly(p) for p in k['polys']])) for k in D['keepouts']]

def draw(g):
    arr = np.zeros((N, N), dtype=bool)
    if g is None or g.is_empty: return arr
    x0, y0, x1, y1 = g.bounds
    i0 = max(0, int((x0 - X0) / STEP) - 1); i1 = min(N, int((x1 - X0) / STEP) + 2)
    j0 = max(0, int((y0 - Y0) / STEP) - 1); j1 = min(N, int((y1 - Y0) / STEP) + 2)
    if i1 > i0 and j1 > j0: arr[j0:j1, i0:i1] = contains_xy(g, X[None, i0:i1], Y[j0:j1, None])
    return arr
INSIDE_TRK = draw(Point(CX, CY).buffer(a.board_r - 0.8, quad_segs=128))
INSIDE_VIA = draw(Point(CX, CY).buffer(a.board_r - 1.2, quad_segs=128))
LCOST = {0: 1.0, 1: 1.0, 2: 1.3, 3: 1.0}
for spec_ in a.layer_cost:
    name, val = spec_.split('='); LCOST[{'F.Cu': 0, 'In1.Cu': 1, 'GND': 1, 'In2.Cu': 2, 'PWR': 2, 'B.Cu': 3}[name]] = float(val)

def rippable(q, net):
    return (a.rip and q['kind'] == 'track' and q.get('id') and q['net'] not in FROZEN and q['net'] != net
            and q['width'] <= 0.3 and q['net'] not in a.nets[:a.nets.index(net)])   # never rip a net routed earlier in this run

def build(net):
    w = width(net)
    obs = [[] for _ in range(4)]; soft = [[] for _ in range(4)]; vblock = []; vsoft = []; cond = [[] for _ in range(4)]; samevia = []
    for q, g, ls in items:
        if q['net'] == net:
            for l in ls: cond[l].append(g)
            if q['kind'] == 'via' or q.get('through'): samevia.append(g)
            if q['kind'] == 'via': vblock.append(Point(q['pos']).buffer(0.55, quad_segs=8))   # hole-to-hole
            continue
        c = max(q.get('clearance', 0), clr(net, q['net']) if q['net'] else 0.25)
        if rippable(q, net):
            for l in ls: soft[l].append(g.buffer(c + w / 2 + M, quad_segs=8))
            vsoft.append(g.buffer(c + VIA_R + M, quad_segs=8)); continue
        for l in ls: obs[l].append(g.buffer(c + w / 2 + M, quad_segs=8))
        vblock.append(g.buffer(c + VIA_R + M, quad_segs=8))
    for z, g in fills:
        if z['net'] == net: cond[z['layer']].append(g)
        elif z['net'] not in ('GND', '3V3'):
            obs[z['layer']].append(g.buffer(clr(net, z['net']) + w / 2 + M)); vblock.append(g.buffer(clr(net, z['net']) + VIA_R + M))
    for k, g in keeps:
        if k['tracks']:
            for l in k['layers']: obs[l].append(g.buffer(w / 2 + M))
        if k['vias']: vblock.append(g.buffer(VIA_R + M))
    block = np.array([draw(union_all(o)) | ~INSIDE_TRK if o else ~INSIDE_TRK for o in obs])
    for l in range(4):
        if l not in ROUTABLE: block[l] = True
    softm = np.array([draw(union_all(s)) if s else np.zeros((N, N), bool) for s in soft])
    via_ok = INSIDE_VIA & ~draw(union_all(vblock))
    via_soft = draw(union_all(vsoft)) if vsoft else np.zeros((N, N), bool)
    # Establish electrical islands in exact geometry. Pixel adjacency can
    # falsely bridge sub-grid gaps in power pours (observed: 0.0347 mm).
    nodes=[]
    for l, shapes in enumerate(cond):
        g=union_all(shapes).buffer(.00001)
        parts=list(g.geoms) if hasattr(g,'geoms') else [g]
        nodes.extend((p,l) for p in parts if not p.is_empty)
    parent=list(range(len(nodes)))
    def root(i):
        while parent[i]!=i: parent[i]=parent[parent[i]]; i=parent[i]
        return i
    tree=STRtree([g for g,l in nodes])
    for via in samevia:
        ix=tree.query(via.buffer(.00001),predicate='intersects')
        for i in ix[1:]:parent[root(i)]=root(ix[0])
    labels=np.zeros((4,N,N),dtype=np.int32)
    for i,(g,l) in enumerate(nodes): labels[l][draw(g)]=root(i)+1
    samevia_m = draw(union_all(samevia)) if samevia else np.zeros((N, N), bool)
    return w, block, softm, via_ok, via_soft, labels, samevia_m

plans = []
def route(net):
    t0 = time.time(); w, block, soft, via_ok, via_soft, lab, samevia = build(net)
    roots, cnt = np.unique(lab[lab > 0], return_counts=True)
    print(f'{net}: {len(roots)} islands, w={w}', flush=True)
    if len(roots) <= 1: return 'connected'
    for r in roots[np.argsort(cnt)]:
        src = (lab == r) & ~block; dst = (lab != r) & (lab > 0) & ~block
        if not src.any() or not dst.any(): continue
        goal2 = dst.any(axis=0); h = ndi.distance_transform_edt(~goal2).astype(np.float32) * STEP
        src &= ~np.array([ndi.binary_erosion(s) for s in src])
        seeds = np.flatnonzero(src); dist = {int(s): 0.0 for s in seeds}; prev = {}
        heap = [(float(h.flat[int(s) % (N * N)]), 0.0, int(s)) for s in seeds]; heapq.heapify(heap)
        closed = set(); found = None
        MOVES = ((0, 1, 1.0), (0, -1, 1.0), (1, 0, 1.0), (-1, 0, 1.0), (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142))
        while heap and len(closed) < a.max_visit:
            _, cost, i = heapq.heappop(heap)
            if i in closed: continue
            closed.add(i); l, rem = divmod(i, N * N); y, x = divmod(rem, N)
            if dst[l, y, x]: found = i; break
            for dy, dx, dc in MOVES:
                xx, yy = x + dx, y + dy
                if xx < 0 or yy < 0 or xx >= N or yy >= N or block[l, yy, xx]: continue
                if dx and dy and (block[l, y, xx] or block[l, yy, x]): continue
                add = dc * STEP * LCOST[l] + (a.rip_cost if soft[l, yy, xx] else 0.0)
                ii = l * N * N + yy * N + xx; nc = cost + add
                if nc < dist.get(ii, 1e20): dist[ii] = nc; prev[ii] = i; heapq.heappush(heap, (nc + float(h[yy, xx]), nc, ii))
            if via_ok[y, x] or samevia[y, x]:
                for ll in ROUTABLE:
                    if ll == l or block[ll, y, x]: continue
                    add = 0.0 if samevia[y, x] else a.via_cost + (a.rip_cost * 10 if via_soft[y, x] else 0.0)
                    ii = ll * N * N + y * N + x; nc = cost + add
                    if nc < dist.get(ii, 1e20): dist[ii] = nc; prev[ii] = i; heapq.heappush(heap, (nc + float(h[y, x]), nc, ii))
        if found is None: print(f'  island {int(r)} ({int(cnt[list(roots).index(r)])} cells): no path, visited {len(closed)}', flush=True); continue
        path = []; i = found
        while True:
            l, rem = divmod(i, N * N); y, x = divmod(rem, N); path.append((l, round(float(X[x]), 3), round(float(Y[y]), 3)))
            if i not in prev: break
            i = prev[i]
        path.reverse()
        smooth = [path[0]]
        for k in range(1, len(path) - 1):
            p, q, s = path[k - 1:k + 2]
            if p[0] == q[0] == s[0] and abs((q[1] - p[1]) * (s[2] - q[2]) - (q[2] - p[2]) * (s[1] - q[1])) < 1e-9: continue
            smooth.append(q)
        smooth.append(path[-1])
        plan = {'net': net, 'width': w, 'path': smooth, 'remove': []}
        for p, q in zip(smooth, smooth[1:]):
            if p[0] != q[0]: g = Point(p[1:]).buffer(VIA_R, quad_segs=16); ls = [0, 1, 2, 3]; rec = dict(kind='via', net=net, pos=list(p[1:]), width=VIA_D)
            else: g = LineString([p[1:], q[1:]]).buffer(w / 2, quad_segs=8); ls = [p[0]]; rec = dict(kind='track', net=net, layer=p[0], width=w)
            items.append((rec, g, ls))
            for qq, gg, lls in items:
                if rippable(qq, net) and (set(lls) & set(ls)) and gg.distance(g) < clr(net, qq['net']) + 0.01:
                    if qq['id'] not in [x['id'] for x in plan['remove']]: plan['remove'].append({'id': qq['id'], 'net': qq['net']})
        plans.append(plan); json.dump(plans, open(a.out, 'w'), indent=1)
        print(f'  routed: cost {dist[found]:.2f}, {len(smooth)} points, {sum(1 for p, q in zip(smooth, smooth[1:]) if p[0] != q[0])} vias, rip {sorted(set(x["net"] for x in plan["remove"]))}, {time.time() - t0:.0f}s', flush=True)
        return 'routed'
    return 'failed'

summary = {}
for net in a.nets:
    res = route(net)
    while res == 'routed': res = route(net)    # keep joining until one island or stuck
    summary[net] = res
json.dump(plans, open(a.out, 'w'), indent=1)
print('SUMMARY', {k: v for k, v in summary.items()})
print('failed:', [k for k, v in summary.items() if v == 'failed'])
