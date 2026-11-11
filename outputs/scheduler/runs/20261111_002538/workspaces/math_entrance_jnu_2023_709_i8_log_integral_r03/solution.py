# Final verification of the symbolic result
import math

def check_identity():
    # Check if arctan(1/k) == pi/2 - arctan(k)
    k = 2.5
    lhs = math.atan(1/k)
    rhs = math.pi/2 - math.atan(k)
    print(f"Identity check: {abs(lhs-rhs) < 1e-15}")
    
    # Check final result
    a, b = 1, 2
    res = math.atan(b+1) - math.atan(a+1)
    res2 = math.atan(1/(a+1)) - math.atan(1/(b+1))
    print(f"Results match: {abs(res-res2) < 1e-15}, val={res}")

check_identity()