# Approximation Algorithm Templates
> For NP-hard problems where exact solutions are infeasible.
> Python implementations with approximation guarantees.

## 1. 2-Approximation for Vertex Cover

Greedily pick both endpoints of uncovered edges. Returns a vertex set at most 2x optimal.

```python
def vertex_cover_2approx(n, edges):
    """2-approximation for minimum vertex cover."""
    cover = set()
    used = [False] * len(edges)
    for i, (u, v) in enumerate(edges):
        if u not in cover and v not in cover:
            cover.add(u)
            cover.add(v)
            used[i] = True
    return cover
```

- **When to use:** Minimum vertex cover is NP-hard. Use when you need a guaranteed small cover fast.
- **Ratio:** 2-approximation (at most 2x the optimal).
- **Complexity:** O(E).

## 2. Christofides-like for Metric TSP

MST-based tour for metric (triangle inequality) TSP. Full Christofides adds minimum-weight perfect matching on odd-degree MST vertices for 1.5x ratio; this simplified DFS-walk version gives 2x.

```python
import heapq
from collections import defaultdict

def tsp_mst_approx(n, dist):
    """2-approximation for metric TSP via MST + DFS walk."""
    # Prim's MST
    adj = defaultdict(list)
    visited = [False] * n
    visited[0] = True
    heap = [(dist[0][j], 0, j) for j in range(1, n)]
    heapq.heapify(heap)
    while heap:
        w, u, v = heapq.heappop(heap)
        if visited[v]:
            continue
        visited[v] = True
        adj[u].append(v)
        adj[v].append(u)
        for nxt in range(n):
            if not visited[nxt]:
                heapq.heappush(heap, (dist[v][nxt], v, nxt))
    # DFS preorder walk = shortcut tour
    tour, stack = [], [0]
    seen = [False] * n
    while stack:
        node = stack.pop()
        if seen[node]:
            continue
        seen[node] = True
        tour.append(node)
        for nb in reversed(adj[node]):
            if not seen[nb]:
                stack.append(nb)
    return tour
```

- **When to use:** TSP with triangle inequality (Euclidean, graph shortest paths). Exact TSP is O(2^N * N).
- **Ratio:** 2-approximation (1.5x with full Christofides matching step).
- **Complexity:** O(N^2 log N) for Prim's MST.

## 3. FPTAS for 0/1 Knapsack

Scale profits down to reduce DP state space. Achieves (1-e)-optimal solution in polynomial time.

```python
def knapsack_fptas(weights, profits, capacity, epsilon):
    """(1+epsilon)-approximation for 0/1 knapsack."""
    n = len(weights)
    p_max = max(profits)
    if p_max == 0:
        return 0, []
    scale = (epsilon * p_max) / n
    scaled = [int(p / scale) for p in profits]
    P = sum(scaled)
    # DP: dp[j] = min weight to achieve profit exactly j
    INF = float('inf')
    dp = [INF] * (P + 1)
    dp[0] = 0
    parent = [[] for _ in range(P + 1)]
    for i in range(n):
        for j in range(P, scaled[i] - 1, -1):
            if dp[j - scaled[i]] + weights[i] < dp[j]:
                dp[j] = dp[j - scaled[i]] + weights[i]
                parent[j] = parent[j - scaled[i]] + [i]
    best = max(j for j in range(P + 1) if dp[j] <= capacity)
    return sum(profits[i] for i in parent[best]), parent[best]
```

- **When to use:** Knapsack with large weights/profits where exact DP is too slow. Set epsilon to control accuracy vs speed.
- **Ratio:** (1 - epsilon)-optimal. E.g., epsilon=0.1 guarantees >= 90% of optimal profit.
- **Complexity:** O(N^3 / epsilon) -- polynomial in N and 1/epsilon.

## 4. Greedy Set Cover

Pick the set covering the most uncovered elements each round. Logarithmic approximation ratio.

```python
def greedy_set_cover(universe, sets):
    """O(log N)-approximation for minimum set cover."""
    uncovered = set(universe)
    chosen = []
    available = list(range(len(sets)))
    while uncovered:
        # Pick set covering the most uncovered elements
        best = max(available, key=lambda i: len(sets[i] & uncovered))
        if not (sets[i := best] & uncovered):
            break  # no progress possible
        chosen.append(best)
        uncovered -= sets[best]
        available.remove(best)
    return chosen
```

- **When to use:** Set cover is NP-hard. Common in resource allocation, test coverage, facility placement.
- **Ratio:** O(log N) where N = |universe|. Provably optimal unless P=NP.
- **Complexity:** O(|sets| * |universe|) per round, O(|universe|) rounds worst case.

## 5. When to Use Approximation -- Decision Guide

```
Problem is NP-hard?
  |-- No  --> Use exact algorithm (DP, greedy, flow, etc.)
  |-- Yes --> Is there a known approximation algorithm?
        |-- No  --> Heuristic / metaheuristic (SA, GA) or exact with pruning
        |-- Yes --> What ratio is acceptable?
              |-- Constant ratio OK (2x, 1.5x) --> Use fixed-ratio approx
              |-- Need (1+e) --> Look for PTAS / FPTAS
              |-- Need exact --> Branch & bound / ILP solver
```

| Problem | Best Known Ratio | Algorithm |
|---------|-----------------|-----------|
| Vertex Cover | 2 | Edge matching |
| Metric TSP | 1.5 | Christofides |
| Set Cover | O(log N) | Greedy |
| Knapsack | (1-e) | FPTAS |
| Max-Cut | 0.878 | SDP relaxation |
| Bin Packing | 1.5 | First Fit Decreasing |
