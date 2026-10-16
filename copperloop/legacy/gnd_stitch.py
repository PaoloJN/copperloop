"""Stitch isolated pieces of the GND pours to the In1 ground plane with one via each.

    uv run --with numpy,scipy,shapely python3 gnd_stitch.py geom.json plans.json [--net GND] [--step 0.05]

Finds every connectivity island of the net (pads, tracks, vias, fills) that has
no copper on In1, and drops a 0.6/0.3 via at the island cell farthest from any
obstacle, where the via clears every other-net item (KiCad pair clearances) and
every no-via rule area. Output is an apply_plans.py plan file (via only).
"""
import json, sys, argparse
import numpy as np
from scipy import ndimage as ndi
from shapely import Polygon, Point, LineString, union_all, contains_xy, make_valid
ap = argparse.ArgumentParser(); ap.add_argument('geom'); ap.add_argument('out'); ap.add_argument('--net', default='GND'); ap.add_argument('--step', type=float, default=0.05)
a = ap.parse_args()
CX, CY = 150.0, 100.0; STEP = a.step; X0, Y0 = 127.0, 77.0; N = int(round(46.0 / STEP)) + 1
X = X0 + np.arange(N) * STEP; Y = Y0 + np.arange(N) * STEP
EC = {'EC_A', 'EC_B', 'EC_SENSE_A', 'EC_SENSE_B', 'EC_BIAS', 'EC_BIAS_EN', 'EC_DRV_HI', 'EC_DRV_LO', '/EC_NODE_D', 'EXP_A4', 'EXP_A5'}
M = 0.03; VIA_R = 0.3; net = a.net
def clr(n1, n2): return 0.2 if (n1 in EC or n2 in EC) else 0.15
def poly(r): return make_valid(Polygon(r[0], r[1:]))
D = json.load(open(a.geom))
def draw(g):
    arr = np.zeros((N, N), dtype=bool)
    if g is None or g.is_empty: return arr
    x0, y0, x1, y1 = g.bounds
    i0 = max(0, int((x0 - X0) / STEP) - 1); i1 = min(N, int((x1 - X0) / STEP) + 2); j0 = max(0, int((y0 - Y0) / STEP) - 1); j1 = min(N, int((y1 - Y0) / STEP) + 2)
    if i1 > i0 and j1 > j0: arr[j0:j1, i0:i1] = contains_xy(g, X[None, i0:i1], Y[j0:j1, None])
    return arr
vblock = []; cond = [[] for _ in range(4)]; samevia = []
for q in D['items']:
    if q['kind'] == 'pad': g = union_all([poly(p) for p in q['polys']]); ls = [q['layer']]
    elif q['kind'] == 'via': g = Point(q['pos']).buffer(q['width'] / 2, quad_segs=16); ls = [0, 1, 2, 3]
    else: g = LineString([q['start'], q['end']]).buffer(q['width'] / 2, quad_segs=8); ls = [q['layer']]
    if q['net'] == net:
        for l in ls: cond[l].append(g)
        if q['kind'] == 'via' or q.get('through'): samevia.append(g)
        if q['kind'] == 'via': vblock.append(Point(q['pos']).buffer(0.55))
    else:
        vblock.append(g.buffer((clr(net, q['net']) if q['net'] else 0.25) + VIA_R + M, quad_segs=8))
for z in D['fills']:
    for p in z['polys']:
        g = poly(p)
        if z['net'] == net: cond[z['layer']].append(g)
        elif z['net'] != '3V3': vblock.append(g.buffer(clr(net, z['net']) + VIA_R + M))
for k in D['keepouts']:
    if k['vias']: vblock.append(union_all([poly(p) for p in k['polys']]).buffer(VIA_R + M))
via_ok = draw(Point(CX, CY).buffer(21.8, quad_segs=128)) & ~draw(union_all(vblock))
cu = np.array([draw(union_all(c).buffer(0.001)) if c else np.zeros((N, N), bool) for c in cond])
labels = np.zeros_like(cu, dtype=np.int32); total = 0
for l in range(4):
    lab, n = ndi.label(cu[l], np.ones((3, 3), int)); labels[l] = np.where(lab, lab + total, 0); total += n
parent = list(range(total + 1))
def root(x):
    while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
    return x
for g in samevia:
    m = draw(g); ns = [int(v) for l in range(4) for v in np.unique(labels[l][m]) if v]
    for n in ns[1:]: parent[root(n)] = root(ns[0])
labels = np.array([root(i) for i in range(total + 1)])[labels]
roots = np.unique(labels[labels > 0]); plans = []; failed = 0
# the via must also sit fully inside the island's own copper (pour) so the plane connection is real
for r in roots:
    if (labels[1] == r).any(): continue          # already on the plane
    isl = (labels == r); cells = isl.sum()
    pads = sorted({f"{q['ref']}.{q['num']}" for q in D['items'] if q['kind'] == 'pad' and q['net'] == net and 0 <= int(round((q['pos'][0]-X0)/STEP)) < N and 0 <= int(round((q['pos'][1]-Y0)/STEP)) < N and isl[:, int(round((q['pos'][1]-Y0)/STEP)), int(round((q['pos'][0]-X0)/STEP))].any()})
    print(f'island {r}: pads {pads}')
    inside = (isl[0] | isl[3])
    cand = inside & via_ok
    if not cand.any(): failed += 1; print(f'island {r} ({cells} cells): no via spot'); continue
    edt = ndi.distance_transform_edt(inside); score = np.where(cand, edt, 0); j, i = np.unravel_index(np.argmax(score), score.shape)
    if edt[j, i] * STEP < VIA_R + 0.05: failed += 1; print(f'island {r} ({cells} cells): copper too narrow for a via'); continue
    x, y = round(float(X[i]), 3), round(float(Y[j]), 3)
    plans.append({'net': net, 'width': 0.3, 'path': [[3, x, y], [0, x, y]], 'remove': []}); print(f'island {r} ({cells} cells): via at ({x},{y})')
json.dump(plans, open(a.out, 'w'), indent=1); print(f'{len(plans)} vias planned, {failed} islands without a spot ->', a.out)
