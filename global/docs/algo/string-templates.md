# String Algorithm Templates
> Curated from KACTL (MIT), cp-algorithms (CC BY-SA 4.0)
> Python implementations verified against source C++ templates.

---

## 1. KMP (Knuth-Morris-Pratt)

**When to use:** All occurrences of pattern in text. Period detection: shortest
period of `s` is `n - pi[n-1]`. | **O(N+M) time, O(M) space.**

**Gotchas:** Sentinel in `pat + '\0' + s` must not appear in either string.

```python
def kmp_prefix(s: str) -> list[int]:
    """pi[i] = longest proper prefix of s[0..i] that is also a suffix."""
    p = [0] * len(s)
    for i in range(1, len(s)):
        g = p[i - 1]
        while g and s[i] != s[g]:
            g = p[g - 1]
        p[i] = g + (s[i] == s[g])
    return p

def kmp_search(text: str, pat: str) -> list[int]:
    p = kmp_prefix(pat + '\0' + text)
    m = len(pat)
    return [i - 2 * m for i in range(2 * m, len(p)) if p[i] == m]
```

---

## 2. Z-Algorithm

**When to use:** z[i] = longest common prefix of s and s[i:]. Alternative to
KMP; simpler for period and wildcard problems. Match via `pat+'$'+text`,
check `z[i] == len(pat)`. | **O(N) time, O(N) space.**

**Gotchas:** z[0] = 0 by convention. Sentinel must not appear in input.

```python
def z_function(s: str) -> list[int]:
    n = len(s)
    z = [0] * n
    l = r = 0
    for i in range(1, n):
        if i < r:
            z[i] = min(r - i, z[i - l])
        while i + z[i] < n and s[z[i]] == s[i + z[i]]:
            z[i] += 1
        if i + z[i] > r:
            l, r = i, i + z[i]
    return z
```

---

## 3. Rolling Hash / Rabin-Karp

**When to use:** O(1) substring equality after O(N) build. Longest duplicate
substring (binary search + hash set), multi-pattern search, suffix array
verification. | **O(N) build, O(1) query.**

**Gotchas:** Single mod is hackable. Use mod 2^61-1 (Mersenne prime) or double
hash. Base must exceed alphabet size.

```python
class RollingHash:
    MOD = (1 << 61) - 1  # Mersenne prime, anti-hack
    BASE = 131

    def __init__(self, s: str):
        n = len(s)
        self.h = h = [0] * (n + 1)
        self.pw = pw = [1] * (n + 1)
        for i in range(n):
            h[i + 1] = (h[i] * self.BASE + ord(s[i])) % self.MOD
            pw[i + 1] = pw[i] * self.BASE % self.MOD

    def query(self, l: int, r: int) -> int:
        """Hash of s[l:r] (half-open)."""
        return (self.h[r] - self.h[l] * self.pw[r - l]) % self.MOD
```

---

## 4. Suffix Array

**When to use:** Sorted suffixes for longest common substring (concatenate
strings with unique separators), distinct substring count, longest repeated
substring. Pair with LCP array. | **O(N log N) time, O(N) space.**

**Gotchas:** Append sentinel `chr(0)` smaller than all chars. sa[0] = N (empty
suffix). LCP: lcp[i] = LCP(sa[i], sa[i-1]).

```python
def suffix_array(s: str) -> tuple[list[int], list[int]]:
    """Returns (sa, lcp), both length N+1. Doubling + Kasai's LCP."""
    s += '\0'; n = len(s)
    sa, rank, tmp = list(range(n)), [ord(c) for c in s], [0] * n
    k = 1
    while k < n:
        key = lambda i: (rank[i], rank[i + k] if i + k < n else -1)
        sa.sort(key=key); tmp[sa[0]] = 0
        for i in range(1, n):
            tmp[sa[i]] = tmp[sa[i - 1]] + (key(sa[i]) != key(sa[i - 1]))
        rank = tmp[:]
        if rank[sa[-1]] == n - 1: break
        k <<= 1
    lcp, inv = [0] * n, [0] * n  # Kasai's algorithm
    for i in range(n): inv[sa[i]] = i
    h = 0
    for i in range(n):
        if inv[i]:
            j = sa[inv[i] - 1]
            while i + h < n and j + h < n and s[i + h] == s[j + h]: h += 1
            lcp[inv[i]] = h; h = max(h - 1, 0)
        else: h = 0
    return sa, lcp
```

---

## 5. Aho-Corasick

**When to use:** Multi-pattern search in one text scan. Keyword filtering, DNA
motifs. Trie + failure links (KMP generalized to a trie). |
**O(sum|P|*K) build, O(|text|+matches) search.**

**Gotchas:** Empty patterns disallowed. For large alphabets use dict transitions
(as below). Output list merges suffix link outputs during BFS.

```python
from collections import deque

class AhoCorasick:
    def __init__(self, patterns: list[str]):
        self.go, self.fail, self.out = [{}], [0], [[]]
        for i, pat in enumerate(patterns):
            cur = 0
            for ch in pat:
                if ch not in self.go[cur]:
                    self.go[cur][ch] = len(self.go)
                    self.go.append({}); self.fail.append(0); self.out.append([])
                cur = self.go[cur][ch]
            self.out[cur].append(i)
        q = deque(self.go[0].values())
        while q:
            u = q.popleft()
            for ch, v in self.go[u].items():
                q.append(v); f = self.fail[u]
                while f and ch not in self.go[f]: f = self.fail[f]
                self.fail[v] = self.go[f].get(ch, 0)
                if self.fail[v] == v: self.fail[v] = 0
                self.out[v] = self.out[v] + self.out[self.fail[v]]

    def search(self, text: str) -> list[tuple[int, int]]:
        """Returns (end_pos, pattern_index) for every match."""
        cur, res = 0, []
        for i, ch in enumerate(text):
            while cur and ch not in self.go[cur]: cur = self.fail[cur]
            cur = self.go[cur].get(ch, 0)
            for pid in self.out[cur]: res.append((i, pid))
        return res
```

---

## 6. Manacher's Algorithm

**When to use:** All palindromic substrings in linear time. d1[i] = radius of
longest odd palindrome at i; d2[i] = half-length of longest even palindrome
centered between i-1 and i. Longest palindrome = max(2*d1[i]+1, 2*d2[i]).
| **O(N) time, O(N) space.**

**Gotchas:** Odd/even handled separately. Odd length 2k+1 at center i means
s[i-k..i+k] is palindrome.

```python
def manacher(s: str) -> tuple[list[int], list[int]]:
    """Returns (d1, d2). d1[i]=odd radius, d2[i]=even half-length."""
    n = len(s); d1, d2 = [0] * n, [0] * n
    l = r = 0
    for i in range(n):  # odd
        d1[i] = max(0, min(r - i, d1[l + (r - i)])) if i < r else 0
        while i - d1[i] - 1 >= 0 and i + d1[i] + 1 < n \
                and s[i - d1[i] - 1] == s[i + d1[i] + 1]: d1[i] += 1
        if i + d1[i] > r: l, r = i - d1[i], i + d1[i]
    l = r = 0
    for i in range(n):  # even
        d2[i] = max(0, min(r - i + 1, d2[l + (r - i) + 1])) if i < r else 0
        while i - d2[i] - 1 >= 0 and i + d2[i] < n \
                and s[i - d2[i] - 1] == s[i + d2[i]]: d2[i] += 1
        if i + d2[i] - 1 > r: l, r = i - d2[i], i + d2[i] - 1
    return d1, d2
```
