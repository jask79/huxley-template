# Algorithm Reference Index

Modular, on-demand algorithm templates for the Algo Wizard agent.
Load specific topic files as needed — don't load all at once.

## Topic Map

| Topic | File | Templates | Lines | Load When |
|-------|------|-----------|-------|-----------|
| Graph Algorithms | `graph-templates.md` | 10 | ~440 | Shortest path, flow, SCC, bridges, LCA, Euler |
| Advanced DP | `advanced-dp.md` | 8 | ~250 | CHT, D&C DP, Knuth, SOS, profile/bitmask DP |
| String Algorithms | `string-templates.md` | 6 | ~200 | Pattern matching, suffix arrays, palindromes |
| Math & Number Theory | `math-templates.md` | 10 | ~275 | Modular arithmetic, FFT/NTT, primality, CRT |
| Game Theory | `game-theory.md` | 5 | ~180 | Nim, Sprague-Grundy, minimax, combinatorial games |
| Computational Geometry | `geometry-templates.md` | 9 | ~230 | Convex hull, sweep line, point-in-polygon, MEC |
| Advanced Data Structures | `advanced-data-structures.md` | 9 | ~400 | Segment tree, Fenwick, treap, HLD, centroid decomp |
| Approximation Algorithms | `approximation.md` | 5 | ~150 | NP-hard problems, vertex cover, TSP, set cover |
| Stress Testing | `stress-testing.md` | 6 | ~215 | Random generators, brute force verification, profiling |

**Total: 68 templates across 9 files (~2,330 lines)**

## Sources

All templates curated from authoritative open-source repositories:
- **KACTL** (MIT) — KTH Algorithm Competition Template Library
- **AtCoder Library** (CC0) — Official AtCoder contest library
- **cp-algorithms** (CC BY-SA 4.0) — Competitive programming reference

Source repos cloned to `.claude/skills/community/{kactl,atcoder-ac-library,cp-algorithms}`.

## Loading Protocol

1. Read this index to identify which topic file(s) are relevant
2. Load only the specific topic file(s) needed for the current problem
3. Each file is self-contained with implementations, complexity analysis, and usage notes
4. For problems spanning multiple topics, load multiple files as needed

## Quick Pattern Matching

**"Shortest path"** → `graph-templates.md` (Dijkstra, BFS, Bellman-Ford, Floyd-Warshall)
**"Maximum flow / matching"** → `graph-templates.md` (Dinic's, Hopcroft-Karp)
**"Range query / update"** → `advanced-data-structures.md` (Fenwick, segment tree, sparse table)
**"Substring / pattern"** → `string-templates.md` (KMP, Z, Aho-Corasick, suffix array)
**"Convex hull trick / DP optimization"** → `advanced-dp.md` (CHT, D&C DP, Knuth)
**"Modular inverse / primality"** → `math-templates.md` (ExtGCD, Miller-Rabin, NTT)
**"Polygon area / intersection"** → `geometry-templates.md` (Shoelace, half-plane, sweep line)
**"Nim / game value"** → `game-theory.md` (Sprague-Grundy, minimax)
**"NP-hard approximation"** → `approximation.md` (vertex cover, TSP, knapsack FPTAS)
**"Wrong answer debugging"** → `stress-testing.md` (random gen, brute force, stress loop)
