"""CRITICAL CHECK: does P-A 'pure-dyadic kickback' really give n_rot = 0?

P-A streams y-bits i=4..39 with weight 2^(i-40) turns each, applied as a single
Z_POW on the accumulator (same mechanism as the existing taps). The verifier counts
n_rot = num_z_pow(min_clifford_hierarchy_level=4). Hierarchy rule (from kickmix docs):
  k=1: 1.0 half-turn (Z); k=2: 0.5 half-turn (S); k=3: odd*0.25 (T);
  k>=4: odd multiples of 2**(1-k) half-turns  =>  a pure power 2**(i-39) half-turns
  has level k = 40 - i.
So bits i<=36 are level >=4 (rotations); only i=37,38,39 are free.
Build the actual circuit and let kickmix count it.
"""
import kickmix as km

def half_turns_str(i):
    # weight 2^(i-40) turns = 2^(i-39) half-turns, exact binary rational
    e = i - 39
    if e >= 0:
        return f"{2**e}.0"
    # 2**-k = 5**k / 10**k  ->  "0." + str(5**k).zfill(k)
    k = -e
    return "0." + str(5**k).zfill(k)

lines = ["APPEND_TO_REGISTER q0 r0"]
q = "q0"
for i in range(4, 40):
    lines.append(f"Z_POW {q} {half_turns_str(i)}")
circ = km.Circuit("\n".join(lines))
stats = circ.operation_statistics()
n_rot = stats.num_z_pow(min_clifford_hierarchy_level=4)
n_t   = stats.num_z_pow(min_clifford_hierarchy_level=3, max_clifford_hierarchy_level=3)
n_clf = stats.num_z_pow(max_clifford_hierarchy_level=2)
print("bits streamed (i=4..39):", 36)
print("kickmix counts -> n_rot(level>=4):", n_rot, " n_t(level3):", n_t, " n_clifford(<=2):", n_clf)
print("hierarchy counts:", stats.z_pow_clifford_hierarchy_counts)
# per-bit level table
print("\nper-bit:  i  weight(turns)  halfturns  level")
for i in range(4, 40):
    ht = 2**(i-39)
    lvl = 40 - i if i <= 37 else (3 if i == 37 else (2 if i == 38 else 1))
    # recompute properly: level of pure power 2**(i-39) half-turns
    e = i - 39
    if e == 0: lvl = 1
    elif e == -1: lvl = 2
    elif e == -2: lvl = 3
    else: lvl = 40 - i
    print(f"  i={i:2d}  2^{i-40:>3d}  {ht:.6g}  k={lvl}  {'FREE' if lvl<=3 else 'ROTATION'}")
