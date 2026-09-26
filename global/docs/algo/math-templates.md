# Math & Number Theory Templates
> Curated from KACTL (MIT), AtCoder Library (CC0), cp-algorithms (CC BY-SA 4.0)
> Python implementations for competitive programming math.

## 1. Extended Euclidean Algorithm
Finds x, y such that ax + by = gcd(a, b). If coprime, x = modular inverse of a mod b.
```python
def extgcd(a, b):
    if not b: return a, 1, 0
    g, x1, y1 = extgcd(b, a % b)
    return g, y1, x1 - (a // b) * y1
```
**Use:** Mod inverse, Diophantine equations, CRT building block. **O(log min(a,b)).**
**Gotchas:** x,y can be negative -- for mod inverse do `x % m`.

## 2. Chinese Remainder Theorem
Solves x = a1 (mod m1), x = a2 (mod m2). Pairwise merge for k moduli.
```python
def crt(a1, m1, a2, m2):
    g, p, _ = extgcd(m1, m2)
    if (a2 - a1) % g: return None
    lcm = m1 // g * m2
    return (a1 + m1 * ((a2 - a1) // g) * p) % lcm, lcm

def crt_multi(rems, mods):
    r, m = rems[0], mods[0]
    for ri, mi in zip(rems[1:], mods[1:]):
        result = crt(r, m, ri, mi)
        if not result: return None
        r, m = result
    return r, m
```
**Use:** Systems of congruences, value reconstruction. **O(k log M).**
**Gotchas:** Handles non-coprime moduli (returns None if inconsistent).

## 3. FFT (Fast Fourier Transform)
Polynomial multiplication via complex roots of unity.
```python
from cmath import exp, pi

def fft(a, invert=False):
    n = len(a)
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit: j ^= bit; bit >>= 1
        j ^= bit
        if i < j: a[i], a[j] = a[j], a[i]
    length = 2
    while length <= n:
        ang = 2 * pi / length * (-1 if invert else 1)
        wn = exp(1j * ang)
        for i in range(0, n, length):
            w = 1
            for k in range(length // 2):
                u, v = a[i+k], a[i+k+length//2] * w
                a[i+k], a[i+k+length//2] = u+v, u-v
                w *= wn
        length <<= 1
    if invert:
        for i in range(n): a[i] /= n

def poly_mul(a, b):
    s = len(a) + len(b) - 1
    n = 1
    while n < s: n <<= 1
    fa = [complex(x) for x in a] + [0]*(n-len(a))
    fb = [complex(x) for x in b] + [0]*(n-len(b))
    fft(fa); fft(fb)
    fa = [fa[i]*fb[i] for i in range(n)]
    fft(fa, True)
    return [round(x.real) for x in fa[:s]]
```
**Use:** Polynomial/big-integer multiplication, counting convolutions. **O(n log n).**
**Gotchas:** Precision safe when sum(ai^2)*log(n) < ~9e14. Use NTT for mod arithmetic or large coefficients.

## 4. NTT (Number Theoretic Transform)
FFT over Z/pZ -- exact, no float error. Standard prime: 998244353 = 119*2^23+1, root 3.
```python
MOD = 998244353; ROOT = 3

def ntt(a, invert=False):
    n = len(a)
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit: j ^= bit; bit >>= 1
        j ^= bit
        if i < j: a[i], a[j] = a[j], a[i]
    length = 2
    while length <= n:
        w = pow(ROOT, (MOD-1)//length, MOD)
        if invert: w = pow(w, MOD-2, MOD)
        for i in range(0, n, length):
            wn = 1
            for k in range(length//2):
                u, v = a[i+k], a[i+k+length//2]*wn % MOD
                a[i+k] = (u+v) % MOD
                a[i+k+length//2] = (u-v) % MOD
                wn = wn*w % MOD
        length <<= 1
    if invert:
        inv_n = pow(n, MOD-2, MOD)
        for i in range(n): a[i] = a[i]*inv_n % MOD

def poly_mul_mod(a, b):
    s = len(a)+len(b)-1; n = 1
    while n < s: n <<= 1
    fa = list(a)+[0]*(n-len(a)); fb = list(b)+[0]*(n-len(b))
    ntt(fa); ntt(fb)
    fa = [fa[i]*fb[i] % MOD for i in range(n)]
    ntt(fa, True)
    return fa[:s]
```
**Use:** Polynomial multiplication mod prime, counting mod P. **O(n log n).**
**Gotchas:** Requires (MOD-1) % n == 0. Max n = 2^23 for 998244353. ACL uses 3 NTT primes + CRT for arbitrary-mod convolution.

## 5. Miller-Rabin (Primality Test)
Deterministic for n < 3.3e24 with 12 witnesses.
```python
def is_prime(n):
    if n < 2: return False
    if n < 4: return True
    if n % 2 == 0 or n % 3 == 0: return False
    d, s = n-1, 0
    while d % 2 == 0: d //= 2; s += 1
    for a in [2,3,5,7,11,13,17,19,23,29,31,37]:
        if a >= n: continue
        x = pow(a, d, n)
        if x == 1 or x == n-1: continue
        for _ in range(s-1):
            x = x*x % n
            if x == n-1: break
        else: return False
    return True
```
**Use:** Fast primality check, prerequisite for Pollard's Rho. **O(12 log^2 n).**
**Gotchas:** KACTL uses witnesses {2,325,9375,28178,450775,9780504,1795265022} for C++ (needs modmul). In Python, the 12-small-prime set is simpler and covers a larger range.

## 6. Pollard's Rho (Integer Factorization)
Finds a non-trivial factor. Floyd's cycle detection; retry on failure.
```python
from math import gcd
from random import randint

def pollard_rho(n):
    if n % 2 == 0: return 2
    x = randint(2, n-1)
    y, c, d = x, randint(1, n-1), 1
    while d == 1:
        x = (x*x+c) % n
        y = (y*y+c) % n; y = (y*y+c) % n
        d = gcd(abs(x-y), n)
    return d if d != n else pollard_rho(n)

def factorize(n):
    if n <= 1: return []
    if is_prime(n): return [n]
    d = pollard_rho(n)
    return sorted(factorize(d) + factorize(n//d))
```
**Use:** Factor large composites up to ~2^62. **O(n^{1/4}) expected per factor.**
**Gotchas:** Always Miller-Rabin first (Rho loops on primes). Randomized -- may retry. Trial division faster for n < 10^6.

## 7. Euler's Totient (Phi Function)
Count of integers in [1,n] coprime to n.
```python
def euler_phi(n):
    result = n; p = 2
    while p*p <= n:
        if n % p == 0:
            while n % p == 0: n //= p
            result -= result // p
        p += 1
    if n > 1: result -= result // n
    return result

def euler_phi_sieve(lim):
    phi = list(range(lim))
    for i in range(2, lim):
        if phi[i] == i:
            for j in range(i, lim, i): phi[j] -= phi[j]//i
    return phi
```
**Use:** Euler's theorem (a^phi(m)=1 mod m), coprime counting. **O(sqrt n) single; O(n log log n) sieve.**
**Gotchas:** phi(1)=1. Euler's theorem needs gcd(a,m)=1. Generalized: a^k = a^(k mod phi(m) + phi(m)) mod m for k >= log2(m).

## 8. Burnside's Lemma (Counting Under Symmetry)
Distinct objects = (1/|G|) * sum(|Fix(g)| for g in G), where Fix(g) = configurations unchanged by g.
```python
def burnside(fix_counts):
    """fix_counts[i] = number of configurations fixed by the i-th symmetry."""
    return sum(fix_counts) // len(fix_counts)

def necklace_colors(n, k):
    """Distinct necklaces of n beads, k colors (rotations only)."""
    from math import gcd
    return sum(k**gcd(n, r) for r in range(n)) // n
```
**Use:** Necklaces/bracelets, grid colorings mod rotation/reflection, Polya enumeration. **O(|G| * cost-of-Fix).**

**Pattern:** (1) Identify symmetry group G. (2) For each g in G, count configs unchanged by g. (3) Sum and divide by |G|.

**Gotchas:** For bracelets add n reflection symmetries. Fix(g) counts unchanged configs, not equivalence classes. The necklace formula uses the identity: configs fixed by rotation-by-r = k^gcd(n,r).

## 9. Matrix Exponentiation
M^k in O(n^3 log k). Essential for linear recurrences at huge k with small state.
```python
def mat_mul(A, B, mod):
    n, m, p = len(A), len(B[0]), len(B)
    C = [[0]*m for _ in range(n)]
    for i in range(n):
        for k in range(p):
            if not A[i][k]: continue
            for j in range(m):
                C[i][j] = (C[i][j] + A[i][k]*B[k][j]) % mod
    return C

def mat_pow(M, k, mod):
    n = len(M)
    R = [[int(i==j) for j in range(n)] for i in range(n)]
    while k:
        if k & 1: R = mat_mul(R, M, mod)
        M = mat_mul(M, M, mod); k >>= 1
    return R
```
**Use:** Linear recurrences, graph path counting (A^k[i][j]), Markov chains. **O(n^3 log k).**
**Gotchas:** Keep n small (n<=10 ideal for k~10^18). Companion matrix maps f(i)=c1*f(i-1)+...+cn*f(i-n). For large n, prefer Kitamasa (O(n^2 log k)).

## 10. Linear Recurrence (Berlekamp-Massey + Kitamasa)
Recover order-n recurrence from 2n terms (BM), then evaluate k-th term in O(n^2 log k).
```python
def berlekamp_massey(s, mod):
    """Returns recurrence coeffs c: s[i] = sum(c[j]*s[i-j-1])."""
    C, B = [1], [1]; L, m, b = 0, 1, 1
    for i in range(len(s)):
        d = s[i]
        for j in range(1, L+1): d = (d + C[j]*s[i-j]) % mod
        m += 1
        if not d: continue
        T = C[:]; coef = d*pow(b, mod-2, mod) % mod
        while len(C) < len(B)+m: C.append(0)
        for j in range(len(B)): C[j+m] = (C[j+m] - coef*B[j]) % mod
        if 2*L <= i: L, B, b, m = i+1-L, T, d, 0
    return [(-C[i]) % mod for i in range(1, L+1)]

def linear_rec(S, tr, k, mod):
    """k-th term of S[i] = sum(tr[j]*S[i-j-1]). O(n^2 log k)."""
    n = len(tr)
    def combine(a, b):
        res = [0]*(2*n+1)
        for i in range(n+1):
            for j in range(n+1):
                res[i+j] = (res[i+j] + a[i]*b[j]) % mod
        for i in range(2*n, n, -1):
            for j in range(n): res[i-1-j] = (res[i-1-j] + res[i]*tr[j]) % mod
            res[i] = 0
        return res[:n+1]
    pol = [0]*(n+1); e = [0]*(n+1); pol[0] = 1; e[1] = 1
    k += 1
    while k:
        if k & 1: pol = combine(pol, e)
        e = combine(e, e); k >>= 1
    return sum(pol[i+1]*S[i] for i in range(n)) % mod
```
**Use:** Any recurrence at huge index (k up to 10^18). BM discovers the recurrence; Kitamasa evaluates it.
**BM: O(n^2). Kitamasa: O(n^2 log k).** Faster than matrix exp when n is large.
**Gotchas:** Provide >= 2*order terms to BM. All arithmetic mod prime p. If BM returns [], sequence is all zeros.

**Example -- Fibonacci F(10^18) mod 998244353:**
```python
terms = [0, 1, 1, 2, 3, 5, 8, 13]
tr = berlekamp_massey(terms, 998244353)  # => [1, 1]
print(linear_rec(terms, tr, 10**18, 998244353))
```
