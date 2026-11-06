# AI Advisor Prompt — Google Quantum AI Verifiable Circuit Compilation (QVC)

> Self-contained brief. No internet access needed or assumed. Everything you need is below.
> If you need clarification, ask at most 5 questions BEFORE answering; otherwise answer directly.

---

## 1. YOUR ROLE AND TASK

You are advising a solo competitor in the Kaggle competition **"Google Quantum AI – Verifiable Quantum Circuit Compilation"** ($150k prize pool, deadline **2027-01-20 23:59 UTC**, 1,782 teams). We are currently ranked **~255th with score 23.91**; the leaderboard top is **27.996** and has been stagnant there since 2026-11-01. We have **~11 weeks** left.

Your task: generate **concrete, novel technical ideas** that could move us toward rank 1. Not generalities. For every idea give: mechanism, which benchmark it applies to, expected numeric effect (show your arithmetic), effort estimate (hours/days/weeks), the first validation step we could take locally, and the main failure mode. Rank all ideas by expected value = (impact × probability of success) / effort. Provide at least 10 ideas, of which at least 3 must lie OUTSIDE the "constant-seed invsqrt" direction described in §5 (to break groupthink). Include at least 2 meta-strategy ideas (team merger, timing, submission allocation). Finish with a "challenge" section: the 3 assumptions in this brief you think are most likely wrong, and what evidence would change your mind.

Do NOT propose anything that violates competition rules (§10). Do NOT re-suggest things already tried and ruled out (§6).

## 2. HOW THE COMPETITION WORKS

Teams submit, for each of three benchmarks, a quantum circuit in Google's **kickmix** format. The official verifier simulates the circuit classically for **every legal input** (this is possible because of the "verifiable structure" constraint below) and checks (a) correctness within a fixed tolerance and (b) cost.

**Verifiable structure:** the critical parts of circuits may only use *reversible classical logic* (Toffoli-type gates), *phasing operations* (rotations), and *measurement-based uncomputation* (HMR: measure an ancilla instead of uncomputing it, conditionally fixing phase). Such circuits are exactly simulable per classical input with Google's simulator `kickmix`, enabling fuzz-testing-style verification at scale.

**Scoring:**
```
Score = ( r_I · r_II · r_III )^(1/3)          # geometric mean of the three ratios
r_k   = reference_cost_k / our_cost_k
cost  = Q_peak · C                             # peak qubits × Toffoli-equivalent ops
C     = mean_executed_Toffolis + t_count/4 + Σ_rotations (0.56·log2(1/ε) + 5.3)
```
where ε is the rotation precision implied by the circuit's minimum error margin. Consequences:
- The geometric mean means **a ×factor improvement counts equally in any benchmark**. Improving the weakest task is as valuable as improving the strongest.
- Fewer qubits AND fewer gates both matter multiplicatively.
- Rotations are cheap only when the error margin allows coarse ε; a tighter margin forces finer (more expensive) rotations. **Error margin is a currency that buys circuit cost.**
- Max 5 submissions/day; scoring takes ~45 min; identical submission bytes → identical score (deterministic verifier seeds).

**Timeline:** mid-milestone prize (public research notebook) — ALREADY MET by us. Longest-leader bonus until 2027-01-04. Team mergers allowed from **2027-01-13** until deadline (merged teams combine their best circuits per benchmark). Final deadline 2027-01-20.

## 3. THE THREE BENCHMARKS (current state, 2026-11-02)

### Benchmark I — Invsqrt (ratio 20.65× for us)
The circuit must phase a qubit by **1/√x** (in turns) for every integer x = 1 … 3,133,452 (= 3·(2¹⁰−2)²), to relative tolerance 2⁻²⁴. Width 22 address bits, n_p = 10.
- Reference circuit (Google): 260 qubits, ~7,735 static CCX, cubic-Horner initial guess with 17-bit coefficients + one Newton step. Reference cost: 2,076,774.23.
- Current public SOTA (what we run): **62 qubits**, 1,497 static CCX, mean executed Toffolis 1,325.48, t_count 7, 41 fine rotations (ε ≈ 2.4·10⁻¹³), cost 100,568.50 → **ratio 20.6503**. Worst error/tolerance = **0.99932** (at x=161) → the error budget is essentially saturated; no approximation headroom left.
- Lineage: mrmeows/team-selenium 63Q → busyaprime → yoyobar 62Q cone rewrites → Ahmed Berat Özer phase patch → Ehan Mallick two 3-to-2 AND merges. All Apache-2.0 public.
- Structure: one-shot Newton–Raphson arithmetic, compute-once + clear-by-measurement throughout (897 HMR ops in the SOTA file).

### Benchmark II — DQI decoder (ratio ~64.5–64.8× for us)
Quantum Reed–Solomon MBUC syndrome decoder: m=4095 codeword positions, n=70 syndromes, degree 12, r=2016, over GF(2^b). Contract per shot: restore syndrome registers S0..S69, return all other qubits to |0>, multiply global phase by (−1)^Σ popcount(e_j & M_j).
- Verifier: 102,400 shots; requires **effective error rate ε₊ < 1/16 — NOT zero errors**. This budget is actively exploited: the current best public decoder contains *deliberate approximate rare branches* that save ~1,830 Toffolis/shot while keeping ε₊ far under budget (observed: 0 errors on default seed, 1 value error on a fresh-salt seed out of 102,400 shots).
- Reference cost: 24,439,463,583,672.93. Current public SOTA (what we run): **892 qubits**, mean Toffolis 398,138.69 (default seed) → cost 377,372,994,802.87 → ratio **64.76×** (64.47× if the official sample hits one rare branch).
- Lineage: iterative belief-propagation decoder; recent gains from (a) measurement-based uncomputation of 24 flag-clearing blocks, (b) **product caching**: a symbolic pass hashes the Boolean function on every wire at every gate; repeated AND products are cached on provably-idle wires and reused via CNOTs, with placement chosen by an exact linear program (free wires, not repeats, are the binding constraint). This removed ~2,800 Toffolis/shot.
- **The full decoder builder source code was made public on 2026-11-01** (`somejoint/qcc-dqi-892-q26` → `dqi-sources/`).

### Benchmark III — DFTHCOS chemistry (ratio 10.27× for us)
Ground-state energy of FeMoCo76o113e using a DF-THC (density-fitting tensor-hypercontraction) ansatz: Givens-rotation tree state prep + 15 angle circuits (k=0..14) + learned table weights.
- Cost = λ_eff × Toffolis × Qubits. Reference cost: 3,355,599,588.32. Current public SOTA (what we run): **428 qubits**, 16,233 Toffolis, **λ_eff = 47.037** → cost 326,800,030 → ratio **10.268×**.
- Hard limits: λ_eff has a **floor ≈ 46.79** for the current word/factorization family (we are at 47.037, i.e. 0.5% above floor). The energy-gap check passes with a margin of only **7·10⁻⁷** → saturated. Factorization: Lera's second (9, 143, 40) factorization; weights refined publicly by heliosli continuing Ahmed Berat Özer's line.

## 4. WHERE WE STAND AND WHERE THE GAP IS

- Our scores: 23.24970 (2026-10-31) → **23.91003** (2026-11-02, rank ~255/1782) → third submission pending, expected ~23.947.
- Leaderboard top: **27.996** (Breaking1800), unchanged since 2026-11-01 21:05 UTC. Next: 27.79, 27.32, 27.06.
- The public frontier (best adoptable public circuits) is 23.91–23.95. **We sit exactly on the public frontier.** The gap to the top is therefore almost certainly NON-PUBLIC work.
- Gap arithmetic: reaching 28.0 requires growing the PRODUCT of the three ratios by (28.0/23.91)³ = **×1.61**. Per-task requirements if only one task improved: invsqrt 20.65→33.2×, dqi 64.5→103.6×, chem 10.27→16.5×. Plausibility: chem is at its physical floor (improbable); dqi ×1.6 is aggressive but the community is pushing hard; **invsqrt ~30× is the known open direction** (§5). A plausible combination: invsqrt 30× + dqi 70× + chem 11× → GM 28.48.
- Working hypothesis: top teams have a **compiled constant-seed invsqrt at ~30–33×** (or equivalent non-public invsqrt work). Community intel: "grinding an incumbent circuit family yields ~11% in 3 weeks; switching families yields ~60% in 2 days" — family switches, not grinding, produce the big jumps.

## 5. THE KEY OPEN DIRECTION: CONSTANT-SEED INVSQRT (our original research)

A prominent community researcher (mrmeows, who publishes everything under Apache-2.0) described but did NOT compile a cheaper invsqrt model:

> "A constant-seed model (128 entry seed table, 8 fractional bits, degree 3, residual 24 plus 2 guard bits, output fraction 26) passes the full domain numerical check at worst error/tolerance 0.617. That margin is the asset: spend it on cheaper circuits."

**We independently reconstructed this numerical model** with exact integer truncation (bit-for-bit what a kickmix circuit computes) and validated it over the full domain x=1..3,133,452:

Pipeline: normalize (count leading zero pairs s; M = x_norm/2²⁰ ∈ [1,4)) → **seed** ≈ 1/√M at 8 fractional bits → **Newton step 1** (16 frac bits) → **Newton step 2** (residual kept at 24+2 guard bits) → **output at 26 frac bits** → denormalize → phase.

Our verified results (worst error/tolerance over full domain):
- Official reference model reproduced: 2.84·10⁻⁸ ✓ (harness validated)
- 128-entry seed table (his spec): **0.6434** (his claimed: 0.617)
- **Piecewise-cubic seed (our improvement, "pwq3"): 4 intervals, cubic in u=(M−m0)/w evaluated at k=floor(u·128) (7 address bits, free from input), LSQ-fit coefficients → 0.5577** — better margin than his spec, and cheaper to load (Horner over 4 muxed constants vs 128-entry table lookup).
- Width sweep done: n1=16/guard=24/out=26 is the spec corner (0.6434); alternatives map out (n1=18→0.6026, guard=26→0.5703, out=28→0.5543, n1=14→0.7431, guard=22→FAIL).

**Interpretation of "output fraction 26" (ours, consistent with all numbers):** only the TOP ~26 output bits are phased as rotations; bits below 2⁻²⁵ turns are under tolerance for every x and need no gates. Dropping them adds ≤0.25 margin units of quantization error; the arithmetic margin pays for it: 0.5577 + 0.25 = 0.81 < 1 ✓. This saves ~15 fine rotations vs the current SOTA (~400 Toffoli-equivalents) plus enables narrower multipliers.

**Why it's worth ~30×:** the seed costs ~450 ANDs/direction vs ~1,074 for the reference's cubic-Horner guess; the two Newton steps use narrow registers. Raw unoptimized pipeline estimate: ~235 qubits, ~4,800 static CCX → only ~1.8×. **The value exists only after SOTA-grade optimization** (the community's 62Q/1,497-CCX circuit was reached from a similar starting point via 32 rounds of exact Boolean rewrites found by Z3-SAT search, reverse Gaussian elimination, and hand-crafted factorization — tailored to THAT arithmetic core, not portable). mrmeows himself notes his incumbent needs cost ≤ 86,532 for 24× and "the target has not been achieved."

Status on our side: numerical model ✓ (published as a public Kaggle notebook), raw kickmix circuit build in progress (foundation only), competitive compilation = the open multi-week engineering problem. We have asked mrmeows (via Discord, pending) for his private research package (model + parameter sweep).

## 6. WHAT WE HAVE TRIED AND RULED OUT (do not re-suggest)

1. **Product caching / HMR clearing on the 62Q invsqrt** (porting the fresh DQI techniques): exact GF(2)-ANF symbolic pass over the whole circuit found **zero genuine repeated products** (19 control-pair groups, all size 1; 309 repeated wire-name pairs are pebbling/reuse, verified by exact ANF comparison + simulation spot-checks with positive/negative controls; CSWAP candidates are flag-controlled rotations). Structural reason: invsqrt is one-shot Newton arithmetic with compute-once/clear-by-measurement; DQI's gains came from an *iterative* decoder's repeated flags. Closed.
2. **Chemistry angle-loader optimization** (our earlier deep dive): the loader is HMR-based with cost-free uncomputation; SOTA layout 126Q is co-designed with RM(1)-coded words; shape-truncation is a dead end (fails energy checks). Track parked; we now ride the public weight/factorization releases instead.
3. **Exploiting approximation budgets elsewhere**: invsqrt margin 0.99932 (saturated), chemistry E_gap margin 7·10⁻⁷ (saturated). Only DQI has a usable ε₊ budget, and the community already exploits it.
4. **Naive adoption gaps**: we already reproduce every public release byte-exactly locally (SHA-pinned) and submit within hours; our score tracks the public frontier exactly (we scored 23.91003, identical to the reference team's LB score for the same bytes).

## 7. OUR ASSETS (what makes some ideas executable for us specifically)

- **Full local verification loop**: unmodified official verifiers + kickmix run in minutes per circuit on our machine. Any idea can be numerically prototyped (exact integer models) and circuit-verified before consuming a submission.
- **Fastest adoption loop in the community** (hours, automated monitoring of datasets/kernels/leaderboard).
- **Original constant-seed numerical model with a BETTER margin than the published spec** (pwq3: 0.5577 vs 0.617) — if we compile constant-seed ourselves, we can potentially beat teams compiling mrmeows' exact spec.
- **Full public source access**: SomeJoint's DQI decoder builder, mrmeows' 32-stage optimization pipeline source (Python, with Z3-SAT scripts), busyaprime's method descriptions, all circuit files.
- Community visibility: published research notebook + active Discord presence (building).

## 8. WHAT WE SPECIFICALLY WANT FROM YOU

1. **Invsqrt beyond constant-seed**: alternative circuit families or arithmetic cores for phasing 1/√x that could reach 30×+ after optimization — e.g., different iteration structures (Halley? different normalization?), different seed representations, phase-factorization tricks, exploiting the specific domain x=1..3,133,452 (not all integers up to 2²²), or structural properties of 1/√x on this domain (periodicity, symmetry, piecewise structure).
2. **Making constant-seed compilation tractable**: better optimization algorithms than Z3-SAT-per-round (which took the incumbent team weeks and still hasn't hit its target), different gate-level representations, automated discovery of the exact Boolean rewrites, or ways to design the arithmetic core so it optimizes well (co-design of algorithm and layout).
3. **DQI improvements** given the now-public decoder source: what would a strong reversible-circuit researcher attack first? (decoder algorithm changes, smaller equivalent decoders, more aggressive but budget-safe approximation, qubit-count reduction below 892.)
4. **Chemistry beyond the λ_eff floor**: is a different word/factorization family realistic in 11 weeks? What would it require?
5. **Meta-strategy**: merger targets and approach (which profile of team complements us — e.g., strong dqi/chem, weak invsqrt?), timing around longest-leader (ends 2027-01-04) and merger window (opens 2027-01-13), allocation of our 5 submissions/day between exploration and safe-best, and how to use our public notebook + Discord presence to get access to others' private work.
6. **Anything we're structurally missing**: a different decomposition of the problem, an unused rule of the competition, a cross-benchmark technique transfer, or a completely different angle on "verifiable structure."

## 9. CHALLENGE US

After your idea list, name the 3 assumptions in this brief you believe are most likely wrong (candidates: "the top-team gap is mainly invsqrt"; "constant-seed is the right family switch"; "the public frontier will keep rising without us"; "pwq3's better margin translates into a better compiled circuit"), and say what single piece of evidence would flip each.

## 10. HARD CONSTRAINTS (rules of the competition)

- Circuits must be expressible in kickmix and respect the verifiable-structure constraint (reversible classical logic + phasing + measurement-based uncomputation).
- Verifier parameters are fixed: domains, tolerances, shot counts, seeds/salts, register conventions. Ideas may exploit ALLOWED budgets (e.g., DQI's ε₊ < 1/16) but never change the rules.
- Adopted third-party circuits require preserved credit chains (Apache-2.0) — not a technical constraint, but it shapes collaboration strategy.
- Submission format: zip named `submission.zip` containing `invsqrt.kmb`, `dqi.kmb`, `dfthcsos/angle_k_{0..14}.kmb`, `dfthcsos/submission.npz`.

## APPENDIX — KEY NUMBERS (for your arithmetic)

| quantity | value |
|---|---|
| our score (best) | 23.91003 (rank ~255/1782) |
| our pending submission | expected 23.9467 |
| LB top | 27.99617 (stagnant since 2026-11-01) |
| reference costs (I, II, III) | 2,076,774.23 · 24,439,463,583,672.93 · 3,355,599,588.32 |
| our costs (I, II, III) | 100,568.50 · 377,372,994,802.87 · 326,800,030 |
| our ratios (I, II, III) | 20.6503 · 64.76 · 10.268 |
| product factor needed for 28.0 | ×1.61 |
| invsqrt SOTA | 62Q, 1,497 static CCX, 1,325.48 mean Toffolis, 41 rotations, err/tol 0.99932 |
| constant-seed raw estimate | ~235Q, ~4,800 static CCX (~1.8× unoptimized) |
| constant-seed margins (ours) | table 0.6434 · pwq3 0.5577 (published spec: 0.617) |
| dqi SOTA | 892Q, 398,138.69 mean Toffolis, ε₊ budget 1/16 (used: ~0.0009–0.034 effective) |
| chem SOTA | 428Q, 16,233 Toffolis, λ_eff 47.037 (floor 46.79), E_gap margin 7·10⁻⁷ |
| timeline | today 2026-11-02 · longest-leader ends 2027-01-04 · mergers open 2027-01-13 · deadline 2027-01-20 |

Answer in English. Be specific, quantitative, and honest about uncertainty.
