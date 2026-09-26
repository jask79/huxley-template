# Stress Testing & Verification Templates
> Systematic debugging for algorithm correctness.
> Python implementations for competitive programming verification.

## 1. Random Test Case Generator

Configurable generators for common data structures.

```python
import random

def rand_array(n, lo=-10**9, hi=10**9):
    return [random.randint(lo, hi) for _ in range(n)]

def rand_string(n, charset='abcdefghijklmnopqrstuvwxyz'):
    return ''.join(random.choice(charset) for _ in range(n))

def rand_permutation(n):
    p = list(range(1, n + 1))
    random.shuffle(p)
    return p

def rand_matrix(rows, cols, lo=0, hi=10**9):
    return [[random.randint(lo, hi) for _ in range(cols)] for _ in range(rows)]

def rand_sorted_array(n, lo=0, hi=10**9):
    return sorted(random.randint(lo, hi) for _ in range(n))
```

- **When to use:** Generating random inputs for any stress test. Parameterize `n`, `lo`, `hi` to cover small and large cases.

## 2. Brute Force Verifier Pattern

Write the simplest O(N^2) or O(N^3) solution you are certain is correct, then compare against optimized code.

```python
def brute_force(arr):
    """O(N^2) brute force -- guaranteed correct, too slow for large N."""
    n = len(arr)
    best = float('-inf')
    for i in range(n):
        total = 0
        for j in range(i, n):
            total += arr[j]
            best = max(best, total)
    return best

def optimized(arr):
    """O(N) Kadane's -- fast but might have a bug."""
    best = cur = arr[0]
    for x in arr[1:]:
        cur = max(x, cur + x)
        best = max(best, cur)
    return best
```

- **When to use:** When your optimized solution gives WA on unknown test cases. The brute force is your oracle.

## 3. Stress Test Loop

Core pattern: generate random input, run both solutions, compare, report first mismatch.

```python
def stress_test(iterations=10000, max_n=20):
    for test in range(1, iterations + 1):
        n = random.randint(1, max_n)
        arr = rand_array(n, lo=-100, hi=100)

        expected = brute_force(arr)
        actual = optimized(arr)

        if expected != actual:
            print(f"MISMATCH on test {test}!")
            print(f"  Input: {arr}")
            print(f"  Expected: {expected}")
            print(f"  Actual:   {actual}")
            return False

        if test % 1000 == 0:
            print(f"  Passed {test} tests...")

    print(f"All {iterations} tests passed.")
    return True
```

- **When to use:** After every non-trivial implementation. Keep `max_n` small (10-20) so brute force runs fast; the goal is catching logic errors, not performance testing.

## 4. Random Graph Generator

Trees, connected graphs, and DAGs.

```python
def rand_tree(n):
    """Random labeled tree via Prufer sequence. Returns edge list."""
    if n == 1:
        return []
    seq = [random.randint(0, n - 1) for _ in range(n - 2)]
    degree = [1] * n
    for v in seq:
        degree[v] += 1
    edges = []
    ptr = min(v for v in range(n) if degree[v] == 1)
    leaf = ptr
    for v in seq:
        edges.append((leaf, v))
        degree[leaf] -= 1
        degree[v] -= 1
        if degree[v] == 1 and v < ptr:
            leaf = v
        else:
            ptr += 1
            while ptr < n and degree[ptr] != 1:
                ptr += 1
            leaf = ptr
    edges.append((leaf, n - 1 if leaf != n - 1 else n - 2))
    return edges

def rand_connected_graph(n, extra_edges=0):
    """Random tree + extra random edges."""
    edges = set()
    for u, v in rand_tree(n):
        edges.add((min(u, v), max(u, v)))
    while len(edges) < n - 1 + extra_edges:
        u, v = random.randint(0, n - 1), random.randint(0, n - 1)
        if u != v:
            edges.add((min(u, v), max(u, v)))
    return list(edges)

def rand_dag(n, m):
    """Random DAG: edges only go from lower to higher index."""
    edges = set()
    while len(edges) < m:
        u = random.randint(0, n - 2)
        v = random.randint(u + 1, n - 1)
        edges.add((u, v))
    return list(edges)
```

- **When to use:** Graph algorithm stress tests. Trees for tree DP, connected graphs for shortest path / MST, DAGs for topological sort / DP on DAG.

## 5. Time Profiling Pattern

Measure wall-clock execution time to detect TLE before submitting.

```python
import time

def time_it(func, *args, label=""):
    start = time.perf_counter()
    result = func(*args)
    elapsed = time.perf_counter() - start
    print(f"  {label or func.__name__}: {elapsed:.4f}s")
    return result, elapsed

def performance_test(max_n=200000, time_limit=2.0):
    """Generate worst-case-size input and check if solution runs in time."""
    arr = rand_array(max_n, lo=-10**9, hi=10**9)

    result, elapsed = time_it(optimized, arr, label=f"N={max_n}")

    if elapsed > time_limit:
        print(f"  TLE RISK: {elapsed:.2f}s > {time_limit}s limit")
    else:
        print(f"  OK: {elapsed:.2f}s within {time_limit}s limit")
    return elapsed <= time_limit
```

- **When to use:** Before submitting. Run with the maximum N from the problem constraints. If it takes > 50% of the time limit in Python, consider optimizing or switching to C++.

## 6. Common Edge Cases Checklist

Always test these before submitting. Generate them programmatically.

```python
def edge_cases_for_array(func, expected_func):
    """Run solution against common edge cases."""
    cases = [
        ("empty",           []),
        ("single",          [42]),
        ("two elements",    [1, 2]),
        ("all same",        [7] * 100),
        ("all negative",    [-i for i in range(1, 101)]),
        ("sorted asc",      list(range(100))),
        ("sorted desc",     list(range(99, -1, -1))),
        ("alternating",     [(-1)**i * i for i in range(100)]),
        ("max value",       [10**9] * 100),
        ("min value",       [-10**9] * 100),
        ("single negative", [-1]),
        ("zeros",           [0] * 100),
    ]
    for name, arr in cases:
        if not arr and not expected_func.__code__.co_varnames:
            continue  # skip empty if func doesn't handle it
        exp = expected_func(arr) if arr else None
        got = func(arr) if arr else None
        status = "PASS" if exp == got else "FAIL"
        if status == "FAIL":
            print(f"  {status} [{name}]: expected={exp}, got={got}, input={arr[:10]}...")
        else:
            print(f"  {status} [{name}]")
```

- **When to use:** Before stress testing. These catch off-by-one errors, empty input crashes, and overflow issues that random tests may miss.

**Full checklist by data type:**

| Type | Edge Cases |
|------|-----------|
| Array | empty, single, all same, sorted, reverse sorted, all negative, max/min values |
| String | empty, single char, all same char, palindrome, max length |
| Graph | single node, no edges, complete graph, disconnected, self-loops, tree |
| Tree | single node, line/chain, star, balanced, left-skewed |
| Integer | 0, 1, -1, MAX_INT, MIN_INT, powers of 2 |
| Coordinates | origin, negative quadrants, collinear points, duplicates |
