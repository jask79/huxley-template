# Computational Geometry Templates
> Curated from KACTL (MIT), cp-algorithms (CC BY-SA 4.0)
> Python implementations for competitive programming geometry.

## 1. Point Class
**When to use:** Foundation for all geometry. Import into every geo problem. | **O(1)**
**Gotchas:** Use `float` for intersection problems; `int` for combinatorial. Cross product sign = left/right test.

```python
from math import sqrt, atan2, cos, sin

class P:
    __slots__ = ('x', 'y')
    def __init__(self, x=0, y=0): self.x, self.y = x, y
    def __add__(s, o):  return P(s.x+o.x, s.y+o.y)
    def __sub__(s, o):  return P(s.x-o.x, s.y-o.y)
    def __mul__(s, t):  return P(s.x*t, s.y*t) if not isinstance(t, P) else NotImplemented
    def __truediv__(s, t): return P(s.x/t, s.y/t)
    def __lt__(s, o):   return (s.x, s.y) < (o.x, o.y)
    def __eq__(s, o):   return s.x == o.x and s.y == o.y
    def __hash__(s):    return hash((s.x, s.y))
    def __repr__(s):    return f'({s.x},{s.y})'
    def dot(s, o):      return s.x*o.x + s.y*o.y
    def cross(s, o):    return s.x*o.y - s.y*o.x
    def dist2(s):       return s.x*s.x + s.y*s.y
    def dist(s):        return sqrt(s.dist2())
    def angle(s):       return atan2(s.y, s.x)
    def perp(s):        return P(-s.y, s.x)
    def unit(s):        d = s.dist(); return P(s.x/d, s.y/d)
    def rot(s, a):      return P(s.x*cos(a)-s.y*sin(a), s.x*sin(a)+s.y*cos(a))
```

## 2. Line-Line Intersection
**When to use:** Where two infinite lines meet (half-plane intersection, Voronoi). | **O(1)**
**Gotchas:** Returns `(flag, point)` -- 1=unique, 0=parallel, -1=collinear. Watch overflow with int coords (products of 3 values).

```python
def line_inter(s1, e1, s2, e2):
    d = (e1-s1).cross(e2-s2)
    if d == 0:
        return (-(((s2-s1).cross(e1-s1)) == 0), P(0, 0))
    p = (s2-s1).cross(e2-s2)          # s2.cross(e1,e2) expanded
    q = (s2-e1).cross(s1-e1)          # s2.cross(e2,s1) expanded
    return (1, (s1*p + e1*q) / d)
```

## 3. Segment-Segment Intersection
**When to use:** Polygon clipping, sweep-line detection, visibility. | **O(1)**
**Gotchas:** Collinear overlaps return both shared endpoints. Use EPS for float coords. `on_seg` needed for endpoint-touching.

```python
def sgn(x): return (x > 0) - (x < 0)

def on_seg(s, e, p):
    return (p-s).cross(e-s) == 0 and (s-p).dot(e-p) <= 0

def seg_inter(a, b, c, d):
    oa = (c-a).cross(d-a)            # a.cross(c,d) equivalent
    ob = (c-b).cross(d-b)
    oc = (a-c).cross(b-c)
    od = (a-d).cross(b-d)
    if sgn(oa)*sgn(ob) < 0 and sgn(oc)*sgn(od) < 0:
        return [(a*ob - b*oa) / (ob - oa)]
    pts = []
    for p in [a, b]:
        if on_seg(c, d, p) and p not in pts: pts.append(p)
    for p in [c, d]:
        if on_seg(a, b, p) and p not in pts: pts.append(p)
    return pts
```

## 4. Point in Polygon (Ray Casting)
**When to use:** Containment queries on arbitrary (not necessarily convex) polygons. | **O(N)**
**Gotchas:** `strict=True` excludes boundary. Winding-number variant handles self-intersecting polygons. Integer coords avoid EPS.

```python
def in_polygon(poly, a, strict=True):
    n, cnt = len(poly), 0
    for i in range(n):
        q = poly[(i+1) % n]
        if on_seg(poly[i], q, a):
            return not strict
        cnt ^= int(((a.y < poly[i].y) - (a.y < q.y)) * (a-poly[i]).cross(q-poly[i]) > 0)
    return bool(cnt)
```

## 5. Closest Pair of Points
**When to use:** Nearest-neighbor in 2D, clustering bounds, geometry optimization. | **O(N log N)**
**Gotchas:** Sort by x, merge by y. Strip check is O(1) amortized (at most 7 neighbors). Use `dist2` to avoid sqrt until end.

```python
def closest_pair(pts):
    def rec(ps):
        if len(ps) <= 3:
            ps.sort(key=lambda p: p.y)
            return min(((ps[i]-ps[j]).dist2(), i, j)
                       for i in range(len(ps)) for j in range(i+1, len(ps)))
        mid = len(ps) // 2
        mx = ps[mid].x
        best = min(rec(ps[:mid]), rec(ps[mid:]))
        ps.sort(key=lambda p: p.y)                  # merge step
        strip = [p for p in ps if (p.x - mx)**2 < best[0]]
        for i in range(len(strip)):
            j = i + 1
            while j < len(strip) and (strip[j].y - strip[i].y)**2 < best[0]:
                d = (strip[i]-strip[j]).dist2()
                if d < best[0]: best = (d, -1, -1)
                j += 1
        return best
    pts = sorted(pts)
    return sqrt(rec(pts)[0])
```

## 6. Sweep Line -- Rectangle Union Area
**When to use:** 2D area union, geometry sweeps, interval scheduling in 2D. | **O(N^2)** simple; O(N log N) w/ seg tree
**Gotchas:** Coordinate-compress y-values. Process open before close at same x. Float rects need EPS-free comparison.

```python
def rect_union_area(rects):
    """rects: list of (x1, y1, x2, y2) with x1<x2, y1<y2."""
    events = []
    for x1, y1, x2, y2 in rects:
        events.append((x1, 0, y1, y2))   # 0 = open
        events.append((x2, 1, y1, y2))   # 1 = close
    events.sort()
    ys = sorted({y for r in rects for y in (r[1], r[3])})
    area, cnt = 0, [0]*len(ys)
    for i in range(len(events)):
        if i > 0:
            dx = events[i][0] - events[i-1][0]
            covered = sum(ys[j+1]-ys[j] for j in range(len(ys)-1) if cnt[j] > 0)
            area += dx * covered
        _, typ, y1, y2 = events[i]
        for j in range(len(ys)-1):
            if ys[j] >= y1 and ys[j+1] <= y2:
                cnt[j] += 1 if typ == 0 else -1
    return area
```

## 7. Polygon Area (Shoelace)
**When to use:** Area computation, orientation detection, centroid calculation. | **O(N)**
**Gotchas:** `polygon_area2` returns *2x signed area* (divide by 2). Positive = CCW. Integer coords keep it exact.

```python
def polygon_area2(poly):
    """Returns 2x signed area. Divide by 2 for actual area."""
    a = poly[-1].cross(poly[0])
    for i in range(len(poly)-1):
        a += poly[i].cross(poly[i+1])
    return a

def polygon_area(poly):
    return abs(polygon_area2(poly)) / 2
```

## 8. Minimum Enclosing Circle (Welzl)
**When to use:** Bounding circle, facility location, clustering radius. | **O(N) expected**
**Gotchas:** Shuffle first (required for expected linear). Multiplicative EPS `1+1e-8` for containment. Near-collinear triples degrade circumcircle precision.

```python
from random import shuffle

def cc_center(a, b, c):
    """Circumcenter of triangle abc."""
    bv, cv = c-a, b-a
    return a + (bv*cv.dist2() - cv*bv.dist2()).perp() / (bv.cross(cv)*2)

def mec(pts):
    """Returns (center, radius)."""
    pts = pts[:]
    shuffle(pts)
    EPS = 1 + 1e-8
    o, r = pts[0], 0.0
    for i in range(len(pts)):
        if (o-pts[i]).dist() > r * EPS:
            o, r = pts[i], 0.0
            for j in range(i):
                if (o-pts[j]).dist() > r * EPS:
                    o = (pts[i]+pts[j]) / 2
                    r = (o-pts[i]).dist()
                    for k in range(j):
                        if (o-pts[k]).dist() > r * EPS:
                            o = cc_center(pts[i], pts[j], pts[k])
                            r = (o-pts[i]).dist()
    return o, r
```

## 9. Half-Plane Intersection
**When to use:** LP in 2D, convex polygon intersection, star-polygon kernel, visibility. | **O(N log N)**
**Gotchas:** Bounding box (4 half-planes) guarantees bounded result. Same-direction parallel: keep leftmost. Opposite-direction: empty. Deque pops from both ends.

```python
from math import atan2
from collections import deque

INF = 1e9

def hp_inter_pt(h1, h2):
    """Intersection of lines of two half-planes. h = (point, direction)."""
    p1, d1 = h1
    p2, d2 = h2
    alpha = (p2-p1).cross(d2) / d1.cross(d2)
    return p1 + d1 * alpha

def hp_out(hp, r):
    p, d = hp
    return d.cross(r - p) < -1e-9

def halfplane_intersection(hps):
    """hps: list of (point, direction). Left side of direction is kept.
    Returns list of vertices of convex intersection polygon, or []."""
    box = [P(INF,INF), P(-INF,INF), P(-INF,-INF), P(INF,-INF)]
    for i in range(4):
        hps.append((box[i], box[(i+1)%4] - box[i]))
    hps.sort(key=lambda h: atan2(h[1].y, h[1].x))
    dq = deque()
    for hp in hps:
        while len(dq)>1 and hp_out(hp, hp_inter_pt(dq[-1], dq[-2])): dq.pop()
        while len(dq)>1 and hp_out(hp, hp_inter_pt(dq[0],  dq[1])):  dq.popleft()
        if dq and abs(hp[1].cross(dq[-1][1])) < 1e-9:
            if hp[1].dot(dq[-1][1]) < 0: return []
            if hp_out(hp, dq[-1][0]): dq.pop()
            else: continue
        dq.append(hp)
    while len(dq)>2 and hp_out(dq[0],  hp_inter_pt(dq[-1], dq[-2])): dq.pop()
    while len(dq)>2 and hp_out(dq[-1], hp_inter_pt(dq[0],  dq[1])):  dq.popleft()
    if len(dq) < 3: return []
    pts = [hp_inter_pt(dq[i], dq[(i+1)%len(dq)]) for i in range(len(dq))]
    return pts
```
