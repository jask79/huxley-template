# Advanced Data Structure Templates
> Curated from KACTL (MIT), AtCoder Library (CC0), cp-algorithms (CC BY-SA 4.0)
> Python implementations for competitive programming data structures.

## 1. Fenwick Tree (Binary Indexed Tree)

**When to use:** Point updates + prefix/range sum queries. Simpler and faster constant than segment tree when you only need sums.
**Complexity:** O(log N) update, O(log N) query. O(N) memory.
**Gotchas:** 0-indexed internally; `query(r) - query(l)` for range `[l, r)`. Cannot do range min/max (use sparse table or segtree).

```python
class FenwickTree:
    """Point update, prefix sum query. Sourced from KACTL FenwickTree.h + ACL fenwicktree.hpp."""
    def __init__(self, n):
        self.n = n
        self.tree = [0] * n

    def update(self, i, delta):          # a[i] += delta
        while i < self.n:
            self.tree[i] += delta
            i |= i + 1                   # next responsible index

    def query(self, r):                   # sum of [0, r)
        s = 0
        while r > 0:
            s += self.tree[r - 1]
            r &= r - 1                   # strip lowest set bit
        return s

    def range_query(self, l, r):          # sum of [l, r)
        return self.query(r) - self.query(l)
```

## 2. 2D Fenwick Tree

**When to use:** 2D point updates + 2D prefix sum queries (e.g. rectangle sum on a grid).
**Complexity:** O(log^2 N) update and query. O(N*M) memory.
**Gotchas:** Memory is N*M upfront. For sparse coordinates, compress first or use the KACTL approach with sorted y-lists per x-node.

```python
class FenwickTree2D:
    """2D point update, rectangle prefix sum. Sourced from KACTL FenwickTree2d.h."""
    def __init__(self, rows, cols):
        self.R, self.C = rows, cols
        self.tree = [[0] * cols for _ in range(rows)]

    def update(self, r, c, delta):
        i = r
        while i < self.R:
            j = c
            while j < self.C:
                self.tree[i][j] += delta
                j |= j + 1
            i |= i + 1

    def query(self, r, c):               # sum of [0,r) x [0,c)
        s = 0
        i = r
        while i > 0:
            j = c
            while j > 0:
                s += self.tree[i - 1][j - 1]
                j &= j - 1
            i &= i - 1
        return s

    def range_query(self, r1, c1, r2, c2):  # sum of [r1,r2) x [c1,c2)
        return (self.query(r2, c2) - self.query(r1, c2)
              - self.query(r2, c1) + self.query(r1, c1))
```

## 3. Lazy Propagation Segment Tree

**When to use:** Range updates + range queries (sum, max, min). The workhorse for interval problems.
**Complexity:** O(N) build, O(log N) update and query.
**Gotchas:** Push lazy before recursing into children. This template does range-add + range-sum; adapt `push`/`combine` for other operations (range-set, range-max, etc.). ACL uses `mapping`/`composition`/`id` abstraction for generality.

```python
class LazySegTree:
    """Range add, range sum query. Sourced from KACTL LazySegmentTree.h + ACL lazysegtree.hpp."""
    def __init__(self, data):
        self.n = len(data)
        self.tree = [0] * (4 * self.n)
        self.lazy = [0] * (4 * self.n)
        self._build(data, 1, 0, self.n - 1)

    def _build(self, a, v, tl, tr):
        if tl == tr:
            self.tree[v] = a[tl]
        else:
            tm = (tl + tr) // 2
            self._build(a, 2*v, tl, tm)
            self._build(a, 2*v+1, tm+1, tr)
            self.tree[v] = self.tree[2*v] + self.tree[2*v+1]

    def _push(self, v, tl, tr):
        if self.lazy[v]:
            tm = (tl + tr) // 2
            self._apply(2*v, tl, tm, self.lazy[v])
            self._apply(2*v+1, tm+1, tr, self.lazy[v])
            self.lazy[v] = 0

    def _apply(self, v, tl, tr, val):
        self.tree[v] += val * (tr - tl + 1)
        self.lazy[v] += val

    def update(self, l, r, val, v=1, tl=0, tr=None):  # add val to [l, r]
        if tr is None: tr = self.n - 1
        if l > tr or r < tl: return
        if l <= tl and tr <= r:
            self._apply(v, tl, tr, val); return
        self._push(v, tl, tr)
        tm = (tl + tr) // 2
        self.update(l, r, val, 2*v, tl, tm)
        self.update(l, r, val, 2*v+1, tm+1, tr)
        self.tree[v] = self.tree[2*v] + self.tree[2*v+1]

    def query(self, l, r, v=1, tl=0, tr=None):         # sum of [l, r]
        if tr is None: tr = self.n - 1
        if l > tr or r < tl: return 0
        if l <= tl and tr <= r: return self.tree[v]
        self._push(v, tl, tr)
        tm = (tl + tr) // 2
        return self.query(l, r, 2*v, tl, tm) + self.query(l, r, 2*v+1, tm+1, tr)
```

## 4. Sparse Table (RMQ)

**When to use:** Static array, many range-min (or max/gcd) queries. O(1) per query after O(N log N) build.
**Complexity:** O(N log N) build, O(1) query. O(N log N) memory.
**Gotchas:** Only works for idempotent operations (min, max, gcd, OR, AND) -- NOT sum. Array must be immutable between queries. Uses overlapping intervals trick for O(1).

```python
from math import log2

class SparseTable:
    """O(1) range minimum query. Sourced from KACTL RMQ.h + cp-algorithms sparse-table."""
    def __init__(self, data):
        n = len(data)
        k = int(log2(n)) + 1 if n else 0
        self.table = [list(data)]
        for j in range(1, k):
            prev = self.table[j - 1]
            pw = 1 << (j - 1)
            self.table.append([min(prev[i], prev[i + pw])
                               for i in range(n - (1 << j) + 1)])
        self.log = [0] * (n + 1)
        for i in range(2, n + 1):
            self.log[i] = self.log[i // 2] + 1

    def query(self, l, r):               # min of [l, r] inclusive
        j = self.log[r - l + 1]
        return min(self.table[j][l], self.table[j][r - (1 << j) + 1])
```

## 5. Mo's Algorithm

**When to use:** Offline answering of range queries [l, r] when you can maintain a running answer by adding/removing single elements. Classic for distinct count, frequency queries.
**Complexity:** O((N + Q) * sqrt(N)) with block size ~ sqrt(N).
**Gotchas:** Offline only (all queries known upfront). Sort order matters: use alternating direction per block for ~2x speedup (as in KACTL). `add`/`remove` must be O(1) or very fast.

```python
from math import isqrt

def mo_algorithm(n, queries, add, remove, get_answer):
    """Offline range queries. Sourced from KACTL MoQueries.h.
    Args:
        n: array size
        queries: list of (l, r) half-open intervals [l, r)
        add(i): include index i in current window
        remove(i): exclude index i from current window
        get_answer(): return current answer
    Returns: list of answers in original query order.
    """
    block = max(1, isqrt(n))
    order = sorted(range(len(queries)),
                   key=lambda i: (queries[i][0] // block,
                                  queries[i][1] if (queries[i][0] // block) % 2 == 0
                                  else -queries[i][1]))
    cur_l, cur_r = 0, 0
    answers = [None] * len(queries)
    for qi in order:
        l, r = queries[qi]
        while cur_l > l: cur_l -= 1; add(cur_l)
        while cur_r < r: add(cur_r); cur_r += 1
        while cur_l < l: remove(cur_l); cur_l += 1
        while cur_r > r: cur_r -= 1; remove(cur_r)
        answers[qi] = get_answer()
    return answers
```

## 6. Implicit Treap (Randomized BST)

**When to use:** Sequence operations: insert/delete at any position, split/merge, reverse a subarray, kth element -- all in O(log N). Acts as a "super-array".
**Complexity:** O(log N) expected for split, merge, insert, delete, kth.
**Gotchas:** Randomized -- expected bounds not worst-case. Remember to push lazy before accessing children. Python recursion limit may need `sys.setrecursionlimit`. Sourced from KACTL Treap.h + cp-algorithms implicit treap.

```python
from random import randint

class TreapNode:
    __slots__ = ('val', 'pri', 'sz', 'left', 'right', 'rev')
    def __init__(self, val):
        self.val = val; self.pri = randint(0, (1 << 62))
        self.sz = 1; self.left = self.right = None; self.rev = False

def _sz(t): return t.sz if t else 0

def _pull(t):
    if t: t.sz = 1 + _sz(t.left) + _sz(t.right)

def _push(t):
    if t and t.rev:
        t.left, t.right = t.right, t.left
        if t.left:  t.left.rev  ^= True
        if t.right: t.right.rev ^= True
        t.rev = False

def split(t, k):
    """Split first k elements into left tree, rest into right."""
    if not t: return None, None
    _push(t)
    left_sz = _sz(t.left)
    if left_sz >= k:
        l, t.left = split(t.left, k); _pull(t); return l, t
    else:
        t.right, r = split(t.right, k - left_sz - 1); _pull(t); return t, r

def merge(l, r):
    _push(l); _push(r)
    if not l or not r: return l or r
    if l.pri > r.pri:
        l.right = merge(l.right, r); _pull(l); return l
    else:
        r.left = merge(l, r.left); _pull(r); return r

def insert(root, pos, val):
    l, r = split(root, pos); return merge(merge(l, TreapNode(val)), r)

def erase(root, pos):
    l, r = split(root, pos); _, r = split(r, 1); return merge(l, r)

def reverse(root, l, r):   # reverse [l, r)
    a, b = split(root, l); b, c = split(b, r - l)
    if b: b.rev ^= True
    return merge(a, merge(b, c))
```

## 7. Heavy-Light Decomposition

**When to use:** Path queries/updates on trees (max, sum, etc.) by reducing to O(log N) segment tree queries per path. Also supports subtree queries.
**Complexity:** O(N) decomposition, O(log^2 N) per path query (log N chains * log N segtree).
**Gotchas:** Values on edges vs. nodes requires offsetting by 1 in the query range. Always swap so `a` is deeper. Sourced from KACTL HLD.h + cp-algorithms hld.

```python
import sys
sys.setrecursionlimit(300_000)

class HLD:
    """Heavy-Light Decomposition for path queries. Pair with any segment tree."""
    def __init__(self, adj, root=0):
        n = len(adj)
        self.par = [-1]*n; self.depth = [0]*n; self.sz = [1]*n
        self.heavy = [-1]*n; self.head = list(range(n)); self.pos = [0]*n
        self._timer = 0; self.n = n
        # iterative DFS for subtree sizes + heavy child
        order = []
        stack = [root]
        visited = [False]*n
        while stack:
            v = stack[-1]
            if not visited[v]:
                visited[v] = True
                for u in adj[v]:
                    if u != self.par[v]:
                        self.par[u] = v; self.depth[u] = self.depth[v]+1
                        stack.append(u)
                order.append(v)
            else:
                stack.pop()
        for v in reversed(order):
            for u in adj[v]:
                if u != self.par[v]:
                    self.sz[v] += self.sz[u]
                    if self.heavy[v] == -1 or self.sz[u] > self.sz[self.heavy[v]]:
                        self.heavy[v] = u
        # decompose
        stack = [(root, root)]
        while stack:
            v, h = stack.pop()
            self.head[v] = h; self.pos[v] = self._timer; self._timer += 1
            # process heavy child first (push light first so heavy pops first)
            children = [u for u in adj[v] if u != self.par[v] and u != self.heavy[v]]
            for u in children:
                stack.append((u, u))
            if self.heavy[v] != -1:
                stack.append((self.heavy[v], h))

    def path_ranges(self, u, v):
        """Yield (l, r) segtree ranges covering the u-v path. Nodes, inclusive."""
        res = []
        while self.head[u] != self.head[v]:
            if self.depth[self.head[u]] < self.depth[self.head[v]]:
                u, v = v, u
            res.append((self.pos[self.head[u]], self.pos[u]))
            u = self.par[self.head[u]]
        if self.depth[u] > self.depth[v]: u, v = v, u
        res.append((self.pos[u], self.pos[v]))
        return res  # query each (l, r) on your segment tree and combine
```

## 8. Centroid Decomposition

**When to use:** Divide-and-conquer on trees. Builds a O(log N)-depth "centroid tree" where every path passes through an ancestor. Classic for distance queries, counting paths with property X.
**Complexity:** O(N log N) build. Queries depend on application.
**Gotchas:** The centroid tree is a NEW tree (not a subtree of the original). Each node appears exactly once. Mark removed centroids to avoid revisiting. Recursive `get_subtree_size` needs the `removed` guard.

```python
class CentroidDecomposition:
    """Builds the centroid tree from an adjacency list."""
    def __init__(self, adj):
        n = len(adj)
        self.adj = adj; self.removed = [False]*n
        self.sub_sz = [0]*n; self.cpar = [-1]*n
        self.root = self._build(0, n)

    def _get_sz(self, v, p):
        self.sub_sz[v] = 1
        for u in self.adj[v]:
            if u != p and not self.removed[u]:
                self._get_sz(u, v); self.sub_sz[v] += self.sub_sz[u]
        return self.sub_sz[v]

    def _get_centroid(self, v, p, tree_sz):
        for u in self.adj[v]:
            if u != p and not self.removed[u] and self.sub_sz[u] > tree_sz // 2:
                return self._get_centroid(u, v, tree_sz)
        return v

    def _build(self, v, n):
        sz = self._get_sz(v, -1)
        c = self._get_centroid(v, -1, sz)
        self.removed[c] = True
        for u in self.adj[c]:
            if not self.removed[u]:
                child_root = self._build(u, n)
                self.cpar[child_root] = c
        self.removed[c] = False   # optional: unmark if reusing
        return c
```

## 9. Persistent Segment Tree

**When to use:** Versioned segtree -- keep all historical versions after point updates. Classic for kth smallest in range `[l, r]` by differencing prefix versions.
**Complexity:** O(N log N) build, O(log N) per update (creates log N new nodes), O(log N) query. O(N log N + Q log N) memory.
**Gotchas:** Memory-heavy -- each update creates O(log N) new nodes. Never mutate old nodes. For kth-smallest, coordinate-compress values first. Sourced from cp-algorithms persistent segment tree.

```python
class PersistentNode:
    __slots__ = ('left', 'right', 'val')
    def __init__(self, val=0, left=None, right=None):
        self.val = val; self.left = left; self.right = right

class PersistentSegTree:
    """Persistent segment tree for kth smallest in range. Point increment + prefix version."""
    def __init__(self, max_val):
        self.lo, self.hi = 0, max_val
        self.roots = [self._build(self.lo, self.hi)]

    def _build(self, tl, tr):
        if tl == tr: return PersistentNode()
        tm = (tl + tr) // 2
        return PersistentNode(0, self._build(tl, tm), self._build(tm+1, tr))

    def _update(self, prev, tl, tr, pos):
        if tl == tr: return PersistentNode(prev.val + 1)
        tm = (tl + tr) // 2
        if pos <= tm:
            return PersistentNode(prev.val+1, self._update(prev.left, tl, tm, pos), prev.right)
        return PersistentNode(prev.val+1, prev.left, self._update(prev.right, tm+1, tr, pos))

    def add(self, val):
        """Insert val, creating a new version."""
        self.roots.append(self._update(self.roots[-1], self.lo, self.hi, val))

    def kth(self, l, r, k):
        """kth smallest (1-indexed) among elements added in versions (l, r]."""
        def walk(vl, vr, tl, tr, k):
            if tl == tr: return tl
            tm = (tl + tr) // 2
            left_count = vr.left.val - vl.left.val
            if left_count >= k:
                return walk(vl.left, vr.left, tl, tm, k)
            return walk(vl.right, vr.right, tm+1, tr, k - left_count)
        return walk(self.roots[l], self.roots[r], self.lo, self.hi, k)
```
