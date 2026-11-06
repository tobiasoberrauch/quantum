"""Empirical probe of kickmix cost counters -> confirms the authoritative price list.

Run: .venv/bin/python work/cost_audit/probe_pricing.py
No secrets, no submissions. Read-only against the kickmix library.
"""
import kickmix as km


def stats_of(circuit_text: str) -> dict:
    c = km.Circuit(circuit_text)
    s = c.operation_statistics()
    return {
        "toffoli_like": int(s.num_toffoli_like),
        "t_like": int(s.num_t_like),                       # Z_POW level 3
        "zpow_ge4": int(s.num_z_pow(min_clifford_hierarchy_level=4)),  # rotations
        "zpow_le2": int(s.num_z_pow(max_clifford_hierarchy_level=2)),  # identity/Z/S (free)
        "levels": s.z_pow_clifford_hierarchy_counts,       # property, not method
    }


print("=== Static circuit counters (per op) ===")
ops = {
    "CCX":        "CCX q0 q1 q2",
    "CCZ":        "CCZ q0 q1 q2",
    "CSWAP":      "CSWAP q0 q1 q2",
    "CX":         "CX q0 q1",
    "CZ":         "CZ q0 q1",
    "SWAP":       "SWAP q0 q1",
    "X":          "X q0",
    "Z":          "Z q0",
    "R":          "R q0",
    "HMR":        "HMR q0 b0",
    "BIT_STORE0": "BIT_STORE0 b0",
    "BIT_STORE1": "BIT_STORE1 b0",
    "BIT_INVERT": "BIT_INVERT b0",
    "NEG":        "NEG",
    "INFO_TAG":   'INFO_TAG "t"',
}
for name, txt in ops.items():
    try:
        print(f"{name:12s} {stats_of(txt)}")
    except Exception as e:
        print(f"{name:12s} ERROR {e!r}")

print("\n=== Z_POW clifford-hierarchy levels (angle in half turns) ===")
for ht in ["0.0", "0.5", "1.0", "0.25", "-0.25", "0.125", "0.0625", "0.1"]:
    try:
        print(f"Z_POW {ht:>7s} half-turns -> {stats_of(f'Z_POW q0 {ht}')}")
    except Exception as e:
        print(f"Z_POW {ht:>7s} ERROR {e!r}")

print("\n=== Conditional (_IF) counting in the SIMULATOR (seeded) ===")
c0 = km.Circuit("BIT_STORE0 b0\nCCX q0 q1 q2 if b0")
c1 = km.Circuit("BIT_STORE1 b0\nCCX q0 q1 q2 if b0")
for label, circ in [("b0=0 (never fires)", c0), ("b0=1 (always fires)", c1)]:
    sim = km.Simulator(batch_size=1, debug_print=False, counting_operations=True, seed=12345)
    sim.use_same_registers_as(circ)
    sim.do(circ)
    st = sim.operation_statistics()
    print(f"{label:22s} sim num_toffoli_like={int(st.num_toffoli_like)}")

print("\n=== PUSH_CONDITION block: Toffolis inside count only where cond bit set ===")
cb = km.Circuit('BIT_STORE0 b0\nPUSH_CONDITION if b0\nCCX q0 q1 q2\nPOP_CONDITION')
sim = km.Simulator(batch_size=1, debug_print=False, counting_operations=True, seed=12345)
sim.use_same_registers_as(cb)
sim.do(cb)
st = sim.operation_statistics()
print(f"PUSH_CONDITION on b0=0 -> sim num_toffoli_like={int(st.num_toffoli_like)}")

print("\n=== Free-gate flood: 1000 CX + 1000 SWAP + 1000 HMR + 1000 R -> cost? ===")
lines = []
for i in range(1000):
    lines.append(f"CX q{i%8} q{(i+1)%8}")
    lines.append(f"SWAP q{i%8} q{(i+1)%8}")
flood = km.Circuit("\n".join(lines))
sf = flood.operation_statistics()
print(f"1000 CX + 1000 SWAP -> toffoli_like={int(sf.num_toffoli_like)} t_like={int(sf.num_t_like)} zpow_ge4={int(sf.num_z_pow(min_clifford_hierarchy_level=4))}")
