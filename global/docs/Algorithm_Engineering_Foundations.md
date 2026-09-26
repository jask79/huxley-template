# Algorithm Engineering Foundations

Fundamentals reference — paradigm decision trees, classic patterns, and complexity quick-reference.

> **For advanced templates** (68 templates across 9 topics): see `global/docs/algo/index.md`

---

## Paradigm Decision Tree

```
Problem arrives → Read constraints (N, M, K)

Is it a GRAPH problem? (nodes, edges, paths, connectivity)
├─ Shortest path?
│  ├─ Unweighted → BFS
│  ├─ Non-negative weights → Dijkstra O(E log V)
│  ├─ Negative weights → Bellman-Ford O(VE)
│  └─ All pairs → Floyd-Warshall O(V³)
├─ Connectivity / components?
│  ├─ Static → DFS / Union-Find
│  └─ Dynamic → Union-Find with path compression
├─ Minimum spanning tree?
│  ├─ Dense graph → Prim O(V²) or O(E log V) with heap
│  └─ Sparse graph → Kruskal O(E log E)
├─ Topological order?
│  └─ Kahn's BFS or DFS-based
├─ Maximum flow / matching?
│  ├─ Max flow → Dinic's O(V²E)
│  └─ Bipartite matching → Hopcroft-Karp O(E√V)
└─ Cycle detection?
   ├─ Directed → DFS with colors (white/gray/black)
   └─ Undirected → Union-Find or DFS with parent tracking

Is it an OPTIMIZATION problem? (maximize, minimize, best, optimal)
├─ Overlapping subproblems + optimal substructure?
│  └─ Dynamic Programming
│     ├─ Sequence → 1D/2D DP
│     ├─ Knapsack → 0/1 or unbounded DP
│     ├─ Interval → Interval DP O(N³)
│     ├─ Tree → Tree DP (post-order)
│     ├─ Bitmask → Bitmask DP O(2^N * N)
│     └─ Digit → Digit DP
├─ Greedy choice property?
│  └─ Greedy (prove with exchange argument)
└─ Neither? → Consider reduction to known NP-hard problem

Is it a SEARCH problem? (find, exists, count)
├─ Sorted data → Binary search
├─ String pattern → KMP / Rabin-Karp / trie
├─ Range queries → Segment tree / BIT
├─ Subset enumeration → Backtracking / bitmask
└─ Constraint satisfaction → Backtracking with pruning

Is it a MATH problem?
├─ Counting → Combinatorics (C(n,k), inclusion-exclusion, generating functions)
├─ Modular arithmetic → Fermat's little theorem, CRT
├─ Primality / factoring → Sieve, Miller-Rabin
├─ Linear recurrence → Matrix exponentiation
├─ Geometry → Convex hull, sweep line, cross product
└─ Probability → Expected value, linearity of expectation
```

---

## Classic Problem Patterns

### Two Pointers
**When:** Sorted array, find pair with target sum, merge operations
**Template:**
```python
left, right = 0, len(arr) - 1
while left < right:
    current = arr[left] + arr[right]
    if current == target:
        return (left, right)
    elif current < target:
        left += 1
    else:
        right -= 1
```
**Complexity:** O(N) time, O(1) space

### Sliding Window
**When:** Subarray/substring with condition (max sum of size K, smallest window containing X)
**Template:**
```python
left = 0
for right in range(len(arr)):
    # expand: add arr[right] to window state
    while window_is_invalid():
        # shrink: remove arr[left] from window state
        left += 1
    # update answer
```
**Complexity:** O(N) time (each element enters/leaves window once)

### Binary Search on Answer
**When:** "Find minimum X such that condition(X) is true" — monotonic predicate
**Template:**
```python
lo, hi = min_possible, max_possible
while lo < hi:
    mid = (lo + hi) // 2
    if condition(mid):
        hi = mid  # mid could be the answer
    else:
        lo = mid + 1
# lo == hi == answer
```
**Complexity:** O(log(range) * check_cost)

### Monotonic Stack
**When:** Next greater/smaller element, histogram problems, stock span
**Template:**
```python
stack = []
result = [-1] * len(arr)
for i in range(len(arr)):
    while stack and arr[stack[-1]] < arr[i]:
        idx = stack.pop()
        result[idx] = arr[i]  # next greater element
    stack.append(i)
```
**Complexity:** O(N) time

### Union-Find (Disjoint Set)
**When:** Dynamic connectivity, component counting, cycle detection in undirected graphs
**Template:**
```python
parent = list(range(n))
rank = [0] * n

def find(x):
    if parent[x] != x:
        parent[x] = find(parent[x])  # path compression
    return parent[x]

def union(x, y):
    px, py = find(x), find(y)
    if px == py:
        return False
    if rank[px] < rank[py]:
        px, py = py, px
    parent[py] = px
    if rank[px] == rank[py]:
        rank[px] += 1
    return True
```
**Complexity:** O(α(N)) per operation (effectively constant)

### Segment Tree
**When:** Range queries with point updates (range sum, range min/max)
**Template (iterative):**
```python
class SegTree:
    def __init__(self, n):
        self.n = n
        self.tree = [0] * (2 * n)

    def update(self, i, val):
        i += self.n
        self.tree[i] = val
        while i > 1:
            i //= 2
            self.tree[i] = self.tree[2*i] + self.tree[2*i+1]

    def query(self, l, r):  # [l, r)
        res = 0
        l += self.n
        r += self.n
        while l < r:
            if l & 1:
                res += self.tree[l]
                l += 1
            if r & 1:
                r -= 1
                res += self.tree[r]
            l //= 2
            r //= 2
        return res
```
**Complexity:** O(log N) per operation

### Topological Sort (Kahn's)
**When:** Dependency ordering, course scheduling, build systems
**Template:**
```python
from collections import deque

def topo_sort(n, edges):
    adj = [[] for _ in range(n)]
    indegree = [0] * n
    for u, v in edges:
        adj[u].append(v)
        indegree[v] += 1

    queue = deque(i for i in range(n) if indegree[i] == 0)
    order = []
    while queue:
        u = queue.popleft()
        order.append(u)
        for v in adj[u]:
            indegree[v] -= 1
            if indegree[v] == 0:
                queue.append(v)
    return order if len(order) == n else []  # empty = cycle
```
**Complexity:** O(V + E)

### Trie
**When:** Prefix queries, autocomplete, word dictionaries, XOR maximum
**Template:**
```python
class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end = False

class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word):
        node = self.root
        for ch in word:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
        node.is_end = True

    def search(self, word):
        node = self.root
        for ch in word:
            if ch not in node.children:
                return False
            node = node.children[ch]
        return node.is_end

    def starts_with(self, prefix):
        node = self.root
        for ch in prefix:
            if ch not in node.children:
                return False
            node = node.children[ch]
        return True
```

### Dynamic Programming Patterns
**When to use:** Overlapping subproblems + optimal substructure

| Pattern | State | Recurrence | Example |
|---------|-------|------------|---------|
| Linear | dp[i] | dp[i] = f(dp[i-1], dp[i-2], ...) | Fibonacci, climbing stairs |
| Knapsack 0/1 | dp[i][w] | dp[i][w] = max(dp[i-1][w], dp[i-1][w-wi] + vi) | Subset sum, partition |
| Unbounded Knapsack | dp[w] | dp[w] = max(dp[w], dp[w-wi] + vi) for all i | Coin change, rod cutting |
| LCS | dp[i][j] | dp[i][j] = dp[i-1][j-1]+1 if match else max(dp[i-1][j], dp[i][j-1]) | Diff, edit distance |
| LIS | dp[i] | dp[i] = 1 + max(dp[j] for j<i if a[j]<a[i]) | Patience sorting (O(N log N)) |
| Interval | dp[i][j] | dp[i][j] = min/max over split k in [i,j) | Matrix chain, burst balloons |
| Tree DP | dp[node] | dp[node] = f(dp[children]) | Tree diameter, max path sum |
| Bitmask | dp[mask] | dp[mask] = f(dp[mask without bit]) | TSP, assignment problem |
| Digit | dp[pos][tight][state] | Process digits left to right | Count numbers with property |

---

## Complexity Quick-Reference

### Sorting Algorithms
| Algorithm | Best | Average | Worst | Space | Stable |
|-----------|------|---------|-------|-------|--------|
| Merge Sort | O(N log N) | O(N log N) | O(N log N) | O(N) | Yes |
| Quick Sort | O(N log N) | O(N log N) | O(N²) | O(log N) | No |
| Heap Sort | O(N log N) | O(N log N) | O(N log N) | O(1) | No |
| Tim Sort | O(N) | O(N log N) | O(N log N) | O(N) | Yes |
| Counting Sort | O(N+K) | O(N+K) | O(N+K) | O(K) | Yes |
| Radix Sort | O(d(N+K)) | O(d(N+K)) | O(d(N+K)) | O(N+K) | Yes |

### Data Structure Operations
| Structure | Search | Insert | Delete | Space |
|-----------|--------|--------|--------|-------|
| Array | O(N) | O(1)* | O(N) | O(N) |
| Sorted Array | O(log N) | O(N) | O(N) | O(N) |
| Linked List | O(N) | O(1) | O(1)** | O(N) |
| Hash Table | O(1) avg | O(1) avg | O(1) avg | O(N) |
| BST (balanced) | O(log N) | O(log N) | O(log N) | O(N) |
| Heap | O(N) | O(log N) | O(log N) | O(N) |
| Trie | O(L) | O(L) | O(L) | O(ALPHABET * L * N) |
| Segment Tree | O(log N) | O(log N) | - | O(N) |
| Union-Find | - | O(α(N)) | - | O(N) |

*amend: append. **with pointer to node.

### Graph Algorithm Complexities
| Algorithm | Time | Space | Notes |
|-----------|------|-------|-------|
| BFS/DFS | O(V+E) | O(V) | Adjacency list |
| Dijkstra (heap) | O(E log V) | O(V) | Non-negative weights |
| Bellman-Ford | O(VE) | O(V) | Handles negative |
| Floyd-Warshall | O(V³) | O(V²) | All pairs |
| Kruskal | O(E log E) | O(V) | With union-find |
| Prim (heap) | O(E log V) | O(V) | Dense: O(V²) |
| Topo Sort | O(V+E) | O(V) | DAG only |
| Tarjan SCC | O(V+E) | O(V) | Strongly connected |
| Dinic's Flow | O(V²E) | O(V+E) | Max flow |
| Hopcroft-Karp | O(E√V) | O(V) | Bipartite matching |

---

## Number Theory Essentials

### GCD / Modular Arithmetic
```python
from math import gcd

def mod_pow(base, exp, mod):
    result = 1
    base %= mod
    while exp > 0:
        if exp & 1:
            result = result * base % mod
        exp >>= 1
        base = base * base % mod
    return result

def mod_inverse(a, mod):
    # mod must be prime
    return mod_pow(a, mod - 2, mod)

# Precompute factorials and inverse factorials for nCr
MOD = 10**9 + 7
MAX_N = 200001
fact = [1] * MAX_N
for i in range(1, MAX_N):
    fact[i] = fact[i-1] * i % MOD
inv_fact = [1] * MAX_N
inv_fact[MAX_N-1] = mod_inverse(fact[MAX_N-1], MOD)
for i in range(MAX_N-2, -1, -1):
    inv_fact[i] = inv_fact[i+1] * (i+1) % MOD

def nCr(n, r):
    if r < 0 or r > n:
        return 0
    return fact[n] * inv_fact[r] % MOD * inv_fact[n-r] % MOD
```

### Sieve of Eratosthenes
```python
def sieve(n):
    is_prime = [True] * (n + 1)
    is_prime[0] = is_prime[1] = False
    for i in range(2, int(n**0.5) + 1):
        if is_prime[i]:
            for j in range(i*i, n+1, i):
                is_prime[j] = False
    return [i for i in range(n+1) if is_prime[i]]
```

---

## Geometry Essentials

### Cross Product & Orientation
```python
def cross(o, a, b):
    """Positive = counter-clockwise, Negative = clockwise, 0 = collinear"""
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
```

### Convex Hull (Andrew's Monotone Chain)
```python
def convex_hull(points):
    points = sorted(set(points))
    if len(points) <= 1:
        return points
    lower = []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]
```

---

## Common Pitfalls

1. **Integer overflow** — Use `long long` in C++, Python handles natively
2. **Off-by-one errors** — Clarify: is it `[l, r]` or `[l, r)`?
3. **Forgetting base cases** — DP needs initial values
4. **Not handling disconnected graphs** — Run BFS/DFS from all unvisited nodes
5. **Floating point comparison** — Use epsilon: `abs(a - b) < 1e-9`
6. **TLE from wrong I/O** — Use `sys.stdin` in Python, `ios_base::sync_with_stdio(false)` in C++
7. **MLE from adjacency matrix** — Use adjacency list for sparse graphs
8. **Not reading the problem** — Re-read constraints, they tell you the expected complexity
9. **Modular arithmetic mistakes** — `(a - b) % MOD` can be negative in some languages; use `((a - b) % MOD + MOD) % MOD`
10. **Greedy without proof** — If you can't prove the greedy choice, it's probably wrong; use DP
