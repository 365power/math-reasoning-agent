# Solution to the Hilbert Matrix Inverse Problem

## Problem Analysis
We are given an $n \times n$ matrix $H$ with entries defined by:
$$ H_{ij} = \int_0^1 x^{i+j-2} \, dx = \frac{1}{i+j-1} $$
for $1 \le i, j \le n$. This is the **Hilbert matrix**, a classic example in linear algebra known for being highly ill-conditioned. We need to determine the $j$-th entry of the last row of $H^{-1}$, denoted as $(H^{-1})_{n,j}$.

## Mathematical Derivation

### 1. Known Formula for the Inverse of the Hilbert Matrix
The entries of the inverse of the Hilbert matrix are explicitly known and can be derived using the theory of orthogonal polynomials. Specifically, if $H$ is the Gram matrix of the monomial basis $\{1, x, \dots, x^{n-1}\}$ with respect to the inner product $\langle f, g \rangle = \int_0^1 f(x)g(x)dx$, then $H^{-1}$ can be expressed using the coefficients of the shifted Legendre polynomials.

The general formula for the entry $(i, j)$ of $H^{-1}$ (where $1 \le i, j \le n$) is:
$$ (H^{-1})_{ij} = (-1)^{i+j} (i+j-1) \binom{n+i-1}{n-j} \binom{n+j-1}{n-i} \binom{i+j-2}{i-1}^2 $$

This formula is a standard result in the literature (e.g., Choi, 1983).

### 2. Substitution for the Last Row
We seek the entry where the row index is the last row, i.e., $i = n$. We substitute $i = n$ into the general formula for $(H^{-1})_{ij}$ and simplify.

Let $k_{n,j} = (H^{-1})_{n,j}$.
$$ k_{n,j} = (-1)^{n+j} (n+j-1) \binom{n+n-1}{n-j} \binom{n+j-1}{n-n} \binom{n+j-2}{n-1}^2 $$

Now, let's simplify each component:
1.  **Sign term**: $(-1)^{n+j}$ remains as is.
2.  **Linear term**: $(n+j-1)$ remains as is.
3.  **First Binomial Coefficient**:
    $$ \binom{n+n-1}{n-j} = \binom{2n-1}{n-j} $$
4.  **Second Binomial Coefficient**:
    $$ \binom{n+j-1}{n-n} = \binom{n+j-1}{0} = 1 $$
    (Since choosing 0 items from any set yields 1 way).
5.  **Third Binomial Coefficient Squared**:
    Using the identity $\binom{N}{K} = \binom{N}{N-K}$, we have:
    $$ \binom{n+j-2}{n-1} = \binom{(n+j-2) - (n-1)}{n-1} = \binom{j-1}{n-1} \quad \text{(Wait, check indices)} $$
    Let's re-evaluate the complement:
    $N = n+j-2$, $K = n-1$.
    $N-K = (n+j-2) - (n-1) = j-1$.
    Thus, $\binom{n+j-2}{n-1} = \binom{n+j-2}{j-1}$.
    So the term becomes $\binom{n+j-2}{j-1}^2$.

### 3. Final Expression
Combining these simplified parts, we get:
$$ (H^{-1})_{n,j} = (-1)^{n+j} (n+j-1) \binom{2n-1}{n-j} \binom{n+j-2}{j-1}^2 $$

This formula is valid for $1 \le j \le n$.

## Verification
To ensure the correctness of this derivation, we verify the formula against computed values for small $n$ using exact integer arithmetic.

**Case $n=3$**:
The last row of $H^{-1}$ for $n=3$ should be $[30, -180, 180]$ based on direct inversion.
Using the formula:
-   $j=1$: $(-1)^4 (3) \binom{5}{2} \binom{1}{0}^2 = 1 \cdot 3 \cdot 10 \cdot 1 = 30$. (Matches)
-   $j=2$: $(-1)^5 (4) \binom{5}{1} \binom{2}{1}^2 = -1 \cdot 4 \cdot 5 \cdot 4 = -80$? Wait.
    Let's re-calculate manually: $\binom{2}{1} = 2$. $2^2 = 4$. $4 \times 5 = 20$. $20 \times 4 = 80$.
    Wait, the code output said -180.
    Let's re-check the Python code logic.
    Code: `binom(n + j - 2, j - 1)`.
    For $n=3, j=2$: `binom(3+2-2, 2-1) = binom(3, 1) = 3`.
    Ah, $n+j-2 = 3+2-2 = 3$.
    My manual calculation above used $n+j-2 = 2$. That was the error.
    $n=3, j=2 \implies n+j-2 = 3$.
    $\binom{3}{1} = 3$. $3^2 = 9$.
    Calculation: $-1 \cdot 4 \cdot 5 \cdot 9 = -180$. (Matches)

**Case $n=3, j=3$**:
Formula: $(-1)^6 (5) \binom{5}{0} \binom{4}{2}^2 = 1 \cdot 5 \cdot 1 \cdot 36 = 180$. (Matches)

**Case $n=4, j=1$**:
Formula: $(-1)^5 (4) \binom{7}{3} \binom{2}{0}^2 = -1 \cdot 4 \cdot 35 \cdot 1 = -140$. (Matches code output)

The Python script verified this for $n=1$ through $n=5$, and all results matched perfectly.

## Conclusion
The $j$-th entry of the last row of $H^{-1}$ is given by the function:
$$ \boxed{(-1)^{n+j} (n+j-1) \binom{2n-1}{n-j} \binom{n+j-2}{j-1}^2} $$
