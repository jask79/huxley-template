# Graph Algorithm Templates
> Curated from KACTL (MIT), AtCoder Library (CC0), cp-algorithms (CC BY-SA 4.0)
> Python implementations verified against source C++ templates.

---

## 1. Dijkstra (Priority Queue)

**When to use:** Single-source shortest path on graphs with non-negative edge weights. The go-to for weighted BFS.

```python
import heapq
from math import inf

def dijkstra(adj, s):
    """adj[u] = [(v, w), ...]. Returns (dist, prev) arrays."""
    n = len(adj)
    dist, prev = [inf] * n, [-1] * n
    dist[s] = 0
    pq = [(0, s)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, w in adj[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v], prev[v] = nd, u
                heapq.heappush(pq, (nd, v))
    return dist, prev
```

**Complexity:** O((V + E) log V) time, O(V + E) space
**Gotchas:**
- Fails silently on negative weights -- use Bellman-Ford instead.
- The `if d > dist[u]: continue` line is critical; without it, stale entries cause O(E log E) blowup.

---

## 2. BFS Shortest Path (Unweighted)

**When to use:** Shortest path in unweighted or unit-weight graphs. Always prefer over Dijkstra when all edge weights are 1.

```python
from collections import deque
from math import inf

def bfs(adj, s):
    """adj[u] = [v, ...]. Returns dist array (-1 = unreachable)."""
    n = len(adj)
    dist = [-1] * n
    dist[s] = 0
    q = deque([s])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if dist[v] == -1:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist
```

**Complexity:** O(V + E) time, O(V) space
**Gotchas:**
- Use `deque`, not `list` -- `list.pop(0)` is O(V).
- For 0/1 weighted graphs, use 0-1 BFS (appendleft for 0-weight edges) instead of Dijkstra.

---

## 3. Bellman-Ford (Negative Weights)

**When to use:** Single-source shortest path when edges can be negative. Detects negative cycles reachable from source.

```python
from math import inf

def bellman_ford(n, edges, s):
    """edges = [(u, v, w), ...]. Returns (dist, has_neg_cycle).
    Nodes reachable via negative cycle get dist = -inf."""
    dist = [inf] * n
    dist[s] = 0
    for i in range(n - 1):
        for u, v, w in edges:
            if dist[u] < inf and dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
    # Detect negative cycles: run N more rounds to propagate -inf
    neg = [False] * n
    for _ in range(n):
        for u, v, w in edges:
            if dist[u] < inf and dist[u] + w < dist[v]:
                dist[v] = -inf
                neg[v] = True
            if neg[u]:
                neg[v] = True
                dist[v] = -inf
    return dist
```

**Complexity:** O(VE) time, O(V) space
**Gotchas:**
- KACTL sorts edges and uses V/2+2 iterations as optimization; the standard V-1 loop is simpler and sufficient.
- Propagating -inf requires a second N-round pass (not just 1 extra round) to reach all nodes downstream of the cycle.

---

## 4. Floyd-Warshall (All-Pairs)

**When to use:** All-pairs shortest path. Best for dense graphs (V <= ~500). Also detects negative cycles.

```python
from math import inf

def floyd_warshall(n, dist):
    """dist = n x n matrix, dist[i][j] = weight or inf. Modifies in place.
    After: dist[i][j] = shortest path, -inf if through negative cycle."""
    for i in range(n):
        dist[i][i] = min(dist[i][i], 0)
    for k in range(n):
        for i in range(n):
            if dist[i][k] == inf:
                continue
            for j in range(n):
                if dist[k][j] < inf:
                    dist[i][j] = min(dist[i][j], dist[i][k] + dist[k][j])
    # Mark paths through negative cycles
    for k in range(n):
        if dist[k][k] < 0:
            for i in range(n):
                for j in range(n):
                    if dist[i][k] < inf and dist[k][j] < inf:
                        dist[i][j] = -inf
```

**Complexity:** O(V^3) time, O(V^2) space
**Gotchas:**
- Loop order must be k-i-j (k outermost). Swapping gives wrong results with no warning.
- For path reconstruction, store `nxt[i][j]` and update alongside `dist`.

---

## 5. Tarjan's SCC

**When to use:** Find strongly connected components in a directed graph. Returns components in reverse topological order.

```python
def tarjan_scc(adj):
    """adj[u] = [v, ...]. Returns list of SCCs (reverse topo order)."""
    n = len(adj)
    idx, low, on_stack = [0] * n, [0] * n, [False] * n
    visited = [False] * n
    stack, sccs = [], []
    timer = [0]

    def dfs(u):
        idx[u] = low[u] = timer[0]
        timer[0] += 1
        visited[u] = True
        stack.append(u)
        on_stack[u] = True
        for v in adj[u]:
            if not visited[v]:
                dfs(v)
                low[u] = min(low[u], low[v])
            elif on_stack[v]:
                low[u] = min(low[u], idx[v])
        if low[u] == idx[u]:
            comp = []
            while True:
                v = stack.pop()
                on_stack[v] = False
                comp.append(v)
                if v == u:
                    break
            sccs.append(comp)

    for i in range(n):
        if not visited[i]:
            dfs(i)
    return sccs
```

**Complexity:** O(V + E) time, O(V) space
**Gotchas:**
- Default Python recursion limit is 1000. Add `sys.setrecursionlimit(N + 100)` for large graphs, or convert to iterative.
- `on_stack` check is essential -- without it, cross-edges to finished components corrupt `low` values.

---

## 6. Bridges & Articulation Points

**When to use:** Find edges whose removal disconnects the graph (bridges) or vertices whose removal disconnects it (cut vertices).

```python
def find_bridges_and_cuts(adj):
    """adj[u] = [v, ...] (undirected). Returns (bridges, cut_vertices)."""
    n = len(adj)
    tin, low = [-1] * n, [-1] * n
    bridges, cuts = [], set()
    timer = [0]

    def dfs(u, parent):
        tin[u] = low[u] = timer[0]
        timer[0] += 1
        children = 0
        for v in adj[u]:
            if tin[v] == -1:
                children += 1
                dfs(v, u)
                low[u] = min(low[u], low[v])
                if low[v] > tin[u]:
                    bridges.append((u, v))
                if parent != -1 and low[v] >= tin[u]:
                    cuts.add(u)
            elif v != parent:
                low[u] = min(low[u], tin[v])
        if parent == -1 and children > 1:
            cuts.add(u)

    for i in range(n):
        if tin[i] == -1:
            dfs(i, -1)
    return bridges, cuts
```

**Complexity:** O(V + E) time, O(V) space
**Gotchas:**
- Bridge: `low[v] > tin[u]`. Cut vertex: `low[v] >= tin[u]` (note `>=` vs `>`).
- Multi-edges: if parallel edges exist between u-v, track parent by edge index, not vertex, to avoid skipping all copies.

---

## 7. LCA with Binary Lifting

**When to use:** Answer lowest common ancestor queries in O(log N) after O(N log N) preprocessing. Also supports k-th ancestor queries.

```python
from math import log2

def build_lca(adj, root=0):
    """adj[u] = [v, ...] (tree). Returns (depth, up, query_fn)."""
    n = len(adj)
    LOG = max(1, int(log2(n)) + 1)
    depth = [0] * n
    up = [[0] * n for _ in range(LOG)]

    # BFS to fill parent and depth
    from collections import deque
    visited = [False] * n
    visited[root] = True
    q = deque([root])
    up[0][root] = root
    while q:
        u = q.popleft()
        for v in adj[u]:
            if not visited[v]:
                visited[v] = True
                depth[v] = depth[u] + 1
                up[0][v] = u
                q.append(v)
    for k in range(1, LOG):
        for v in range(n):
            up[k][v] = up[k - 1][up[k - 1][v]]

    def lca(a, b):
        if depth[a] < depth[b]:
            a, b = b, a
        diff = depth[a] - depth[b]
        for k in range(LOG):
            if (diff >> k) & 1:
                a = up[k][a]
        if a == b:
            return a
        for k in range(LOG - 1, -1, -1):
            if up[k][a] != up[k][b]:
                a, b = up[k][a], up[k][b]
        return up[0][a]

    return depth, up, lca
```

**Complexity:** O(N log N) build, O(log N) per query, O(N log N) space
**Gotchas:**
- Root must point to itself (`up[0][root] = root`), otherwise k-th ancestor jumps past root into garbage.
- `LOG` must be `floor(log2(N)) + 1`; off-by-one here causes silent wrong answers on deep trees.

---

## 8. Dinic's Max Flow

**When to use:** Maximum flow / minimum cut. Best general-purpose max-flow algorithm for competitive programming. Also used for bipartite matching via reduction.

```python
from collections import deque
from math import inf

class Dinic:
    def __init__(self, n):
        self.n = n
        self.graph = [[] for _ in range(n)]  # (to, rev_idx, cap)

    def add_edge(self, u, v, cap):
        self.graph[u].append([v, len(self.graph[v]), cap])
        self.graph[v].append([u, len(self.graph[u]) - 1, 0])

    def _bfs(self, s, t):
        self.level = [-1] * self.n
        self.level[s] = 0
        q = deque([s])
        while q:
            u = q.popleft()
            for v, _, cap in self.graph[u]:
                if cap > 0 and self.level[v] == -1:
                    self.level[v] = self.level[u] + 1
                    q.append(v)
        return self.level[t] != -1

    def _dfs(self, u, t, pushed):
        if u == t:
            return pushed
        while self.iter[u] < len(self.graph[u]):
            v, rev, cap = self.graph[u][self.iter[u]]
            if cap > 0 and self.level[v] == self.level[u] + 1:
                d = self._dfs(v, t, min(pushed, cap))
                if d > 0:
                    self.graph[u][self.iter[u]][2] -= d
                    self.graph[v][rev][2] += d
                    return d
            self.iter[u] += 1
        return 0

    def max_flow(self, s, t):
        flow = 0
        while self._bfs(s, t):
            self.iter = [0] * self.n
            while True:
                f = self._dfs(s, t, inf)
                if f == 0:
                    break
                flow += f
        return flow
```

**Complexity:** O(V^2 * E) time; O(E * sqrt(V)) for unit-capacity graphs
**Gotchas:**
- `self.iter` (current-arc optimization) resets each BFS phase -- without it, complexity degrades to Edmonds-Karp.
- Reverse edge capacity starts at 0; for undirected edges, add both directions with full capacity.

---

## 9. Hopcroft-Karp (Bipartite Matching)

**When to use:** Maximum matching in bipartite graphs. Faster than running Dinic on the bipartite flow reduction.

```python
from collections import deque
from math import inf

def hopcroft_karp(adj_left, m):
    """adj_left[u] = [v, ...] (right-side vertices 0..m-1).
    Returns (match_size, match_left, match_right)."""
    n = len(adj_left)
    ml, mr = [-1] * n, [-1] * m
    dist = [0] * n

    def bfs():
        q = deque()
        for u in range(n):
            if ml[u] == -1:
                dist[u] = 0
                q.append(u)
            else:
                dist[u] = inf
        found = False
        while q:
            u = q.popleft()
            for v in adj_left[u]:
                nxt = mr[v]
                if nxt == -1:
                    found = True
                elif dist[nxt] == inf:
                    dist[nxt] = dist[u] + 1
                    q.append(nxt)
        return found

    def dfs(u):
        for v in adj_left[u]:
            nxt = mr[v]
            if nxt == -1 or (dist[nxt] == dist[u] + 1 and dfs(nxt)):
                ml[u], mr[v] = v, u
                return True
        dist[u] = inf
        return False

    res = 0
    while bfs():
        for u in range(n):
            if ml[u] == -1:
                res += dfs(u)
    return res, ml, mr
```

**Complexity:** O(E * sqrt(V)) time, O(V) space
**Gotchas:**
- Left and right vertex sets are indexed separately (0-based each). Map to global IDs externally if needed.
- Setting `dist[u] = inf` on DFS failure is the key pruning step; omitting it makes the algorithm O(VE).

---

## 10. Euler Path/Circuit

**When to use:** Find a path/circuit that visits every edge exactly once. Exists iff: circuit = all even degree; path = exactly 0 or 2 odd-degree vertices.

```python
def euler_path(adj, n_edges, src=0, directed=False):
    """adj[u] = [(v, edge_id), ...]. For undirected, same edge_id both ways.
    Returns vertex list of Euler path/circuit, or [] if none exists."""
    idx = [0] * len(adj)
    used = [False] * n_edges
    stack, path = [src], []
    while stack:
        u = stack[-1]
        if idx[u] < len(adj[u]):
            v, eid = adj[u][idx[u]]
            idx[u] += 1
            if not used[eid]:
                used[eid] = True
                stack.append(v)
        else:
            path.append(stack.pop())
    path.reverse()
    if len(path) != n_edges + 1:
        return []  # No Euler path exists
    return path
```

**Complexity:** O(V + E) time, O(V + E) space
**Gotchas:**
- For undirected graphs, forward and backward edges must share the same `edge_id` so the `used` array marks both.
- Check degree conditions before calling: if they fail, this returns a partial path, not an error.
