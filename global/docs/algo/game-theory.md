# Game Theory Templates
> Curated from cp-algorithms (CC BY-SA 4.0)
> Python implementations for competitive programming game theory.

## Decision Guide

| Pattern | Technique |
|---------|-----------|
| Two players, alternating, optimal play, pile-based | Nim (XOR) |
| Two players, alternating, optimal play, general moves | Sprague-Grundy |
| Multiple independent sub-games combined | XOR of Grundy values |
| Win/lose/draw from each state on directed graph | BFS game on graph |
| Score maximization, two-player zero-sum | Minimax + Alpha-Beta |
| Graph with edges removed each turn | Green Hackenbush |

## 1. Nim Game

XOR of all pile sizes. Non-zero = first player wins.
**When to use:** Piles of objects, remove any amount from one pile, last-move-wins.
Triggers: "stones", "piles", "take from one pile", "who wins".

```python
def nim_winner(piles: list[int]) -> bool:
    """True if the current player wins."""
    xor = 0
    for p in piles:
        xor ^= p
    return xor != 0

def nim_winning_move(piles: list[int]) -> tuple[int, int] | None:
    """Return (pile_index, new_size) for a winning move, or None."""
    xor = 0
    for p in piles:
        xor ^= p
    if xor == 0: return None
    for i, p in enumerate(piles):
        if p ^ xor < p: return (i, p ^ xor)
    return None
```

**Complexity:** O(n) per query.
**Gotchas:** Misere Nim (last move loses) uses same XOR except when all piles
are 0 or 1 -- then invert the answer.

## 2. Sprague-Grundy Theorem

Every impartial game state has a Grundy number = mex of reachable Grundy values.
Combined independent games: XOR their Grundy numbers.
**When to use:** Any impartial game (both players have same moves), game splits
into independent parts. Triggers: "mex", "Grundy", "nimber", "game decomposes".

```python
def mex(s: set[int]) -> int:
    """Minimum excludant: smallest non-negative int not in s."""
    i = 0
    while i in s:
        i += 1
    return i

def grundy_values(max_state: int, moves_fn) -> list[int]:
    """Compute Grundy numbers for states 0..max_state.
    moves_fn(state) -> list of reachable states."""
    g = [0] * (max_state + 1)
    for s in range(max_state + 1):
        g[s] = mex({g[ns] for ns in moves_fn(s)})
    return g

def combined_winner(*grundy_vals: int) -> bool:
    """XOR Grundy values of independent sub-games. Non-zero = win."""
    xor = 0
    for v in grundy_vals:
        xor ^= v
    return xor != 0
```

**Complexity:** O(S * M) where S = states, M = max moves per state.
**Gotchas:** Impartial games only (same moves for both players). Partizan games
(chess) need different theory. Check for periodic Grundy patterns -- many games
have short periods after some offset.

## 3. Minimax with Alpha-Beta Pruning

Two-player zero-sum with score maximization, not just win/lose.
**When to use:** States have numeric evaluation. One player maximizes, other
minimizes. Triggers: "optimal score", "best play", "evaluate position".

```python
INF = float('inf')

def minimax(state, depth, maximizing, evaluate, get_moves, do_move, undo_move,
            alpha=-INF, beta=INF) -> float:
    if depth == 0 or not get_moves(state):
        return evaluate(state)
    best = -INF if maximizing else INF
    for m in get_moves(state):
        do_move(state, m)
        val = minimax(state, depth-1, not maximizing, evaluate,
                      get_moves, do_move, undo_move, alpha, beta)
        undo_move(state, m)
        if maximizing:
            best = max(best, val); alpha = max(alpha, val)
        else:
            best = min(best, val); beta = min(beta, val)
        if alpha >= beta:
            break
    return best
```

**Complexity:** O(b^d) worst, O(b^(d/2)) with good move ordering (b=branching, d=depth).
**Gotchas:** Move ordering is critical for pruning. Transposition tables (memo on
state hash) help with repeated positions. For draws, use three-valued logic.

## 4. Green Hackenbush

Players alternate removing edges; disconnected components vanish. Reduces to Nim.
**When to use:** Graph edge-removal games. Triggers: "Hackenbush", "remove edge",
"connected to ground", "tree game".

```python
def hackenbush_tree_grundy(adj: list[list[int]], root: int) -> int:
    """Grundy value for Green Hackenbush on a tree rooted at ground."""
    visited = [False] * len(adj)
    def dfs(v: int) -> int:
        visited[v] = True
        g = 0
        for u in adj[v]:
            if not visited[u]:
                g ^= (dfs(u) + 1)
        return g
    return dfs(root)

def hackenbush_winner(trees: list[tuple[list[list[int]], int]]) -> bool:
    """XOR Grundy values across multiple trees. Non-zero = win."""
    xor = 0
    for adj, root in trees:
        xor ^= hackenbush_tree_grundy(adj, root)
    return xor != 0
```

**Complexity:** O(V + E) per tree.
**Gotchas:** Tree formula: `g(v) = XOR(g(child) + 1)` per child. For graphs with
cycles, use Colon Principle: odd-length cycle = Grundy 1, even = Grundy 0.

## 5. Game on Graph (BFS Win/Lose/Draw)

Classify every vertex of a directed game graph as Win, Lose, or Draw in O(E).
**When to use:** Game states form a directed graph, possibly cyclic. Need outcome
from each state. Triggers: "game on graph", "who wins from vertex X", "draw possible".

```python
from collections import deque

def game_on_graph(adj: list[list[int]], n: int) -> list[str]:
    """Classify each vertex as 'W' (win), 'L' (lose), or 'D' (draw)."""
    out_deg = [len(adj[v]) for v in range(n)]
    adj_rev = [[] for _ in range(n)]
    for v in range(n):
        for u in adj[v]:
            adj_rev[u].append(v)
    res, q = ['D'] * n, deque()
    for v in range(n):
        if out_deg[v] == 0:
            res[v] = 'L'; q.append(v)
    cnt = out_deg[:]  # unresolved successor count
    while q:
        v = q.popleft()
        for u in adj_rev[v]:
            if res[u] != 'D': continue
            if res[v] == 'L':
                res[u] = 'W'; q.append(u)
            else:
                cnt[u] -= 1
                if cnt[u] == 0:
                    res[u] = 'L'; q.append(u)
    return res
```

**Complexity:** O(V + E).
**Gotchas:** Vertices left as 'D' are genuine draws (cycles, neither player forces
a win). `cnt` tracks unresolved successors -- only when ALL lead to 'W' is
a vertex marked 'L'. Unlike Sprague-Grundy, this handles cycles and draws.
