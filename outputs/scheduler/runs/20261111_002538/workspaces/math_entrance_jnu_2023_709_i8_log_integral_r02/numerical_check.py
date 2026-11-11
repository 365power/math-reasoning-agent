import numpy as np
from scipy import integrate

def integrand_t(t, a, b):
    if t == 0:
        return 0  # limit sin(t)/t -> 1, but multiplied by (e^{-(a+1)t} - e^{-(b+1)t}) which is 0, so 0
    return np.sin(t)/t * (np.exp(-(a+1)*t) - np.exp(-(b+1)*t))

# Test for a=1, b=2
a, b = 1.0, 2.0
result, error = integrate.quad(integrand_t, 0, np.inf, args=(a, b))
print(f"Numerical integral for a={a}, b={b}: {result}")
print(f"Analytical result: {np.arctan(1/(a+1)) - np.arctan(1/(b+1))}")

# Also compute original integral directly with substitution handling
def integrand_original(x, a, b):
    if x == 0 or x == 1:
        return 0.0
    log_x = np.log(x)
    sin_arg = np.log(1/x)  # = -log_x
    return np.sin(sin_arg) * (x**b - x**a) / log_x

# Use quad on [0,1], but avoid singularities by splitting or using limit
# From 0 to 1, but near 0 and 1 it's okay? Near 1: (x^b - x^a)/log(x) ~ b-a, sin(log(1/x)) ~ log(1/x) = -log x, so product ~ (b-a)(-log x)/log x = -(b-a), finite.
# Near 0: with substitution it's fine, but direct might have issues. Let's try with points avoiding 0.
try:
    result_orig, err_orig = integrate.quad(integrand_original, 0, 1, args=(a, b))
    print(f"Direct numerical integral: {result_orig}")
except Exception as e:
    print(f"Direct integration failed: {e}")
    # Try splitting interval
    result_orig, err_orig = integrate.quad(lambda x: integrand_original(x,a,b), 0.0001, 1.0, args=(a,b))
    print(f"Direct numerical integral (from 0.0001 to 1): {result_orig}")
