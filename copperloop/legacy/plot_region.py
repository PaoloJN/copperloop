"""Draw a window of the board from geom_export.py JSON (and optional router plans).

    uv run --with matplotlib,shapely python3 plot_region.py geom.json out.png x0 y0 x1 y1 [--plans plans.json] [--nets NET ...] [--layers 0 3]
F.Cu red, B.Cu blue, In2 orange, In1 grey; pads labelled ref.pad; vias as circles; --nets highlighted in green.
"""
import json, argparse, math
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly, Circle
ap = argparse.ArgumentParser(); ap.add_argument('geom'); ap.add_argument('out'); ap.add_argument('x0', type=float); ap.add_argument('y0', type=float); ap.add_argument('x1', type=float); ap.add_argument('y1', type=float)
ap.add_argument('--plans'); ap.add_argument('--nets', nargs='*', default=[]); ap.add_argument('--layers', nargs='*', type=int, default=[0, 2, 3]); ap.add_argument('--dpi', type=int, default=150)
a = ap.parse_args()
D = json.load(open(a.geom)); COL = {0: 'red', 1: 'grey', 2: 'orange', 3: 'blue'}
fig, ax = plt.subplots(figsize=((a.x1 - a.x0) * 0.9 + 1, (a.y1 - a.y0) * 0.9 + 1)); ax.set_xlim(a.x0, a.x1); ax.set_ylim(a.y1, a.y0); ax.set_aspect('equal')
def inwin(x, y, m=1): return a.x0 - m <= x <= a.x1 + m and a.y0 - m <= y <= a.y1 + m
for k in D['keepouts']:
    if k['tracks'] or k['vias']:
        for p in k['polys']: ax.add_patch(MPoly(p[0], closed=True, fill=False, ls='--', lw=0.6, ec='purple'))
for q in D['items']:
    hi = q['net'] in a.nets
    if q['kind'] == 'pad':
        if q['layer'] not in a.layers and not q['through']: continue
        if not inwin(*q['pos']): continue
        for p in q['polys']:
            ax.add_patch(MPoly(p[0], closed=True, fc='green' if hi else ('lightgrey' if q['through'] else COL[q['layer']]), alpha=0.35 if not q['through'] else 0.6, ec='k', lw=0.3))
        if q['layer'] == min(l for l in a.layers) or q['through']:
            ax.text(q['pos'][0], q['pos'][1], f"{q['ref']}.{q['num']}\n{q['net']}", fontsize=3.5, ha='center', va='center')
    elif q['kind'] == 'via':
        if not inwin(*q['pos']): continue
        ax.add_patch(Circle(q['pos'], q['width'] / 2, fc='green' if hi else 'white', ec='k', lw=0.5))
        ax.text(q['pos'][0], q['pos'][1] - 0.35, q['net'], fontsize=3, ha='center', color='darkgreen')
    else:
        if q['layer'] not in a.layers: continue
        (x1, y1), (x2, y2) = q['start'], q['end']
        if not (inwin(x1, y1) or inwin(x2, y2)): continue
        ax.plot([x1, x2], [y1, y2], color='green' if hi else COL[q['layer']], lw=q['width'] * 72 * 0.9 / 2.54 * 0.95, solid_capstyle='round', alpha=0.7)
        if hi or q['width'] >= 0.3:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2, q['net'], fontsize=2.5, color='k', alpha=0.6)
if a.plans:
    for p in json.load(open(a.plans)):
        pts = p['path']
        for s, e in zip(pts, pts[1:]):
            if s[0] == e[0]: ax.plot([s[1], e[1]], [s[2], e[2]], color='magenta' if s[0] == 0 else ('cyan' if s[0] == 3 else 'gold'), lw=1.5, alpha=0.9)
            else: ax.add_patch(Circle((s[1], s[2]), 0.3, fc='magenta', ec='k', lw=0.5, alpha=0.8))
        ax.text(pts[0][1], pts[0][2], p['net'], fontsize=4, color='magenta', weight='bold')
ax.grid(True, lw=0.2); ax.set_xticks(range(int(a.x0), int(a.x1) + 1)); ax.set_yticks(range(int(a.y0), int(a.y1) + 1)); ax.tick_params(labelsize=5)
fig.savefig(a.out, dpi=a.dpi, bbox_inches='tight'); print('wrote', a.out)
