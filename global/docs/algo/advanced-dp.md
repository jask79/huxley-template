# Advanced Dynamic Programming Templates
> Curated from KACTL (MIT), cp-algorithms (CC BY-SA 4.0)
> Python implementations for DP optimization techniques.

---

## 1. Convex Hull Trick (CHT)

**When to use:** Recurrence `dp[i] = min/max(dp[j] + b[j]*a[i])` -- add lines `y = b[j]*x + dp[j]`, query at `x = a[i]`. Requires slopes `b[j]` monotone (sorted insert) or queries `a[i]` monotone (pointer). Arbitrary order: Li Chao tree or KACTL `LineContainer`.

**Complexity:** O(n) amortized with monotone slopes/queries; O(n log n) with sorted container.

```python
from collections import deque

def cht_min(a, b, base_dp):
    """dp[i] = min over j<i of (base_dp[j] + b[j]*a[i]). Needs b[j] decreasing."""
    hull = deque()
    def bad(l1, l2, l3):
        return (l3[1]-l1[1])*(l1[0]-l2[0]) <= (l2[1]-l1[1])*(l1[0]-l3[0])
    def add(m, b_val):
        line = (m, b_val)
        while len(hull) >= 2 and bad(hull[-2], hull[-1], line): hull.pop()
        hull.append(line)
    def query(x):
        while len(hull) >= 2 and hull[0][0]*x+hull[0][1] >= hull[1][0]*x+hull[1][1]:
            hull.popleft()
        return hull[0][0]*x + hull[0][1]
    dp = [0]*len(a)
    for j in range(len(a)):
        add(b[j], base_dp[j]); dp[j] = query(a[j])
    return dp
```

**Gotchas:**
- **min** = upper hull (slopes desc); **max** = lower hull (slopes asc).
- Non-monotone slopes/queries: use Li Chao segment tree instead.

---

## 2. Divide & Conquer DP Optimization

**When to use:** Recurrence `dp[i][j] = min_k(dp[i-1][k-1] + C(k,j))` where `opt[i][j] <= opt[i][j+1]` (monotone minima). Holds when `C` satisfies quadrangle inequality. Reduces O(mn^2) to O(mn log n).

**Complexity:** O(m * n * log n).

```python
def dc_dp(m, n, cost):
    """cost(k, j) -> number. Returns dp[m-1][n-1]."""
    INF = float('inf')
    dp_prev = [cost(0, j) for j in range(n)]
    for i in range(1, m):
        dp_cur = [INF]*n
        def solve(lo, hi, opt_lo, opt_hi):
            if lo > hi: return
            mid = (lo+hi)//2
            best_val, best_k = INF, opt_lo
            for k in range(opt_lo, min(mid, opt_hi)+1):
                val = (dp_prev[k-1] if k else 0) + cost(k, mid)
                if val < best_val: best_val, best_k = val, k
            dp_cur[mid] = best_val
            solve(lo, mid-1, opt_lo, best_k)
            solve(mid+1, hi, best_k, opt_hi)
        solve(0, n-1, 0, n-1)
        dp_prev = dp_cur
    return dp_prev[n-1]
```

**Gotchas:**
- Proving monotonicity of `opt` is the hard part; QI on `C` is sufficient, not necessary.
- Many CHT problems are solvable with D&C DP and vice versa.

---

## 3. Knuth's Optimization

**When to use:** Interval DP `dp[i][j] = min_{i<=k<j}(dp[i][k] + dp[k+1][j] + C(i,j))` where `C` satisfies: (1) `C(b,c) <= C(a,d)` for a<=b<=c<=d, and (2) QI `C(a,c)+C(b,d) <= C(a,d)+C(b,c)`. Reduces O(n^3) to O(n^2).

**Complexity:** O(n^2).

```python
def knuth_dp(n, cost):
    """cost(i,j) -> number. Returns dp[0][n-1]."""
    INF = float('inf')
    dp = [[0]*n for _ in range(n)]
    opt = [[0]*n for _ in range(n)]
    for i in range(n): opt[i][i] = i
    for length in range(2, n+1):
        for i in range(n-length+1):
            j = i+length-1
            dp[i][j] = INF
            lo, hi = opt[i][j-1], opt[i+1][j] if i+1 < n else j-1
            for k in range(lo, min(j, hi+1)):
                val = dp[i][k] + dp[k+1][j] + cost(i, j)
                if val < dp[i][j]: dp[i][j] = val; opt[i][j] = k
    return dp[0][n-1]
```

**Gotchas:**
- Classic apps: optimal BST, cutting sticks, matrix chain (with QI cost).
- Initialize `opt[i][i] = i` carefully; wrong init = wrong bounds.

---

## 4. SOS DP (Sum over Subsets)

**When to use:** Given `f[mask]` for all 2^n masks, compute `g[mask] = sum(f[s])` for all submasks `s` of `mask`. Brute-force submask enumeration is O(3^n); SOS DP is O(n * 2^n).

**Complexity:** O(n * 2^n).

```python
def sos_dp(f, n):
    """g[mask] = sum of f[s] for all submasks s of mask."""
    g = f[:]
    for bit in range(n):
        for mask in range(1 << n):
            if mask & (1 << bit):
                g[mask] += g[mask ^ (1 << bit)]
    return g
```

**Gotchas:**
- **Superset** sums: flip condition -- iterate masks where bit is **off**, add from version with bit **on**.
- Mobius inverse (inclusion-exclusion): subtract instead of add in the same loop.

---

## 5. Profile DP (Broken Profile)

**When to use:** Filling N x M grid with tiles (dominoes, L-shapes). State = bitmask of width M for the boundary ("profile") between filled and unfilled cells. Always bitmask the **smaller** dimension.

**Complexity:** O(N * 2^M * M); exponential in min(N, M).

```python
def domino_tiling(N, M):
    """Count ways to tile N x M grid with 1x2 dominoes."""
    if N < M: N, M = M, N
    dp = [0]*(1 << M); dp[0] = 1
    def fill(col, mask, nmask):
        if col == M:
            dp_next[nmask] += dp[mask]; return
        if mask & (1 << col):
            fill(col+1, mask, nmask)
        else:
            fill(col+1, mask, nmask | (1 << col))  # vertical
            if col+1 < M and not (mask & (1 << (col+1))):
                fill(col+2, mask, nmask)            # horizontal
    for _ in range(N):
        dp_next = [0]*(1 << M)
        for mask in range(1 << M):
            if dp[mask]: fill(0, mask, 0)
        dp = dp_next
    return dp[0]
```

**Gotchas:**
- Bitmask the smaller dimension (M <= ~20); iterate the larger.
- "Broken profile" = jagged boundary between processed/unprocessed cells, not a full row.

---

## 6. DP on DAGs

**When to use:** DP where the state graph is acyclic. Process in topological order. Covers longest/shortest path, path counting on explicit graphs.

**Complexity:** O(V + E).

```python
from collections import deque

def dag_longest_path(adj, indeg, n, weights):
    """Longest path from any source. adj: adjacency list, weights: node values."""
    dp = [0]*n
    q = deque(v for v in range(n) if indeg[v] == 0)
    topo = []
    while q:
        u = q.popleft(); topo.append(u)
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0: q.append(v)
    for u in topo:
        for v in adj[u]:
            dp[v] = max(dp[v], dp[u] + weights[v])
    return dp
```

**Gotchas:**
- Cycles: contract SCCs first (Tarjan/Kosaraju), then DP on the DAG of components.
- Implicit DAGs (grid, intervals, subsets): topological order = your natural loop order.

---

## 7. Connected Component DP (Tree Partitioning)

**When to use:** DP on a tree tracking component sizes -- partitioning into subtrees of bounded size, counting forests, minimizing cuts. Bottom-up DFS, merge child knapsacks.

**Complexity:** O(n * S) per node; O(n^2) total via small-to-large merging.

```python
def tree_partition(adj, root, max_sz):
    """Count ways to cut edges so every component has size <= max_sz."""
    n = len(adj)
    dp = [[0]*(max_sz+1) for _ in range(n)]  # dp[v][s] = ways with v's component size s
    def dfs(v, par):
        dp[v][1] = 1
        for u in adj[v]:
            if u == par: continue
            dfs(u, v)
            new = [0]*(max_sz+1)
            child_total = sum(dp[u])
            for sv in range(1, max_sz+1):
                if not dp[v][sv]: continue
                new[sv] += dp[v][sv] * child_total  # cut edge v-u
                for su in range(1, max_sz+1-sv):     # merge child
                    new[sv+su] += dp[v][sv] * dp[u][su]
            dp[v] = new
    dfs(root, -1)
    return sum(dp[root])
```

**Gotchas:**
- Naive merge looks O(n^2) per node but telescopes to O(n^2) total (convolution size argument).
- Rerooting technique: compute DP from every root in O(n) extra after one bottom-up pass.

---

## 8. Probability DP (Expected Value)

**When to use:** Expected values via backward induction. Define absorbing states with known values, compute E[state] from transitions. Games, random walks, coupon collector.

**Complexity:** O(states * transitions), problem-dependent.

```python
def coupon_collector(n):
    """Expected steps to collect all n distinct items."""
    return sum(n / (n - i) for i in range(n))

def prob_dp_grid(R, C, p_right):
    """P(reach (R-1,C-1) from (0,0)). Move right w.p. p_right, down w.p. 1-p_right."""
    dp = [[0.0]*C for _ in range(R)]
    dp[0][0] = 1.0
    for r in range(R):
        for c in range(C):
            if r == c == 0: continue
            if r > 0: dp[r][c] += dp[r-1][c] * (1-p_right)
            if c > 0: dp[r][c] += dp[r][c-1] * p_right
    return dp[R-1][C-1]
```

**Gotchas:**
- Cyclic dependencies (random walks with return) need linear system solving, not plain DP.
- Floating-point drift: use `fractions.Fraction` or modular inverse for exact answers.
