"""
Verification of the integral result.
We calculate I = arctan(1/(a+1)) - arctan(1/(b+1)) for sample values.
Since scipy/numpy are not available, we use the math library.
"""
import math

def calc_I(a, b):
    return math.atan(1/(a+1)) - math.atan(1/(b+1))

# Test cases
cases = [
    (1.0, 2.0),
    (0.5, 1.5),
    (2.0, 10.0)
]

for a, b in cases:
    print(f"a={a}, b={b}: I = {calc_I(a, b)}")
    