# DEEP-RESEARCH PROMPT — Google Quantum AI Verifiable Circuit Compilation (QVC)

> For an **all-powerful research agent WITH live web / paper / artifact access**.
> This is NOT an offline reasoning task. You are expected to GO FIND things:
> current leaderboard, named Kaggle datasets/kernels, arXiv papers, GitHub repos,
> forum threads. Cite every external claim (URL / arXiv ID / dataset slug / kernel ref / date).
> For each finding label it **PUBLIC** (we can adopt it ourselves) or **PRIVATE** (only reachable via merger/outreach).
> Answer in English. Be quantitative. Show arithmetic. Be honest about uncertainty and about what you could NOT verify.

---

## 0. YOUR JOB

Produce an **evidence-backed research report** identifying the concrete, ranked path(s) to raise our QVC score from **23.94667 (rank 355 / 2056)** toward the two real targets:

- **Target A — Top-170 threshold: 24.00057** (gap **+0.054 GM**, i.e. a **+0.67 % product** improvement). This is the nearest meaningful step.
- **Target B — Rank 1: 27.99617** (gap **+4.05 GM**, i.e. a **×1.60 product** improvement). Almost certainly non-public work.

Do not just reason from this brief. Verify current state (leaderboard, latest public releases, forum replies) as of today, then research the open technical questions in §4. Finish with a **ranked action list** (impact × probability / effort) and a **"challenge"** section (§6).

---

## 1. HOW THE COMPETITION WORKS

Solo/team Kaggle competition, $150k, deadline **2027-01-20 23:59 UTC**. Teams submit, for each of **three benchmarks**, a quantum circuit in Google's **kickmix** format. The official verifier classically simulates the circuit for **every legal input** (possible due to the "verifiable structure" constraint) and checks (a) correctness within a fixed tolerance and (b) cost.

**Verifiable structure:** critical parts may only use *reversible classical logic* (Toffoli-type gates), *phasing operations* (rotations), and *measurement-based uncomputation* (HMR: measure an ancilla instead of uncomputing, conditionally fixing phase). Such circuits are exactly simulable per classical input.

**Scoring (verify this against observed LB scores in §4-R6):**
```
Score = ( r_I · r_II · r_III )^(1/3)          # geometric mean of the three ratios
r_k   = reference_cost_k / our_cost_k
cost  = Q_peak · C                            # peak qubits × Toffoli-equivalent ops
C     = mean_executed_Toffolis + t_count/4 + Σ_rotations ( 0.56·log2(1/ε) + 5.3 )
```
where ε is the rotation precision implied by the circuit's minimum error margin. Consequences:
- Geometric mean ⇒ **a ×factor improvement counts equally in any benchmark**; improving the weakest task is as valuable as the strongest.
- Fewer qubits AND fewer gates both matter multiplicatively.
- **Error margin is a currency that buys circuit cost**: rotations are cheap only when the margin allows coarse ε; a tighter margin forces finer (more expensive) rotations.
- Max **5 submissions/day**; scoring ~45 min; identical bytes → identical score (deterministic verifier seeds).

**Timeline:** mid-milestone prize (public research notebook) — **already met by us**. Longest-leader bonus until **2027-01-04**. Team mergers allowed **2027-01-13 → deadline** (merged teams combine their best circuit per benchmark).

---

## 2. WHERE WE STAND (precise, 2026-11-02)

- **Rank 355 / 2056, score 23.94667** (team "Tobias Oberrauch", member `tobeetaylor`, 3 submissions, last 2026-11-02 08:59:33).
- **Field structure (from a full leaderboard download):**
  - Dense **public-frontier pack at ranks ~200–400+**, all within **23.94667–23.94721** (span only **0.00054 GM**). We sit at the **BOTTOM** of this pack; the pack's top (rank 200, 23.94721) has already edged past us by 0.00054. 17 teams share our exact score; 40 teams sit at 23.94695 (ranks 248–287).
  - **Elbow at rank ~170 = 24.00057.** Above it, scores open up: 24.43 (r50), 25.32 (r20), 26.81 (r5), 27.996 (r1).
  - So: 355→250 costs only +0.00028 (strategically irrelevant, still in-pack); the **real step is 355→Top-170 = +0.054 GM**; **rank 1 = +4.05 GM**.
- **Our component ratios (best submission qvc-003):**
  | bench | ratio | Q | C detail | reference cost | our cost |
  |---|---|---|---|---|---|
  | I invsqrt | **20.6503** | 62 | 1,497 static CCX, 1,325.48 mean Toffolis, t_count 7, 41 fine rotations, ε≈2.4·10⁻¹³, err/tol **0.99932** (saturated) | 2,076,774.23 | 100,568.50 |
  | II dqi | **~64.76** | 892 | 398,138.69 mean Toffolis, **R(ε₊)=1.19126**, ε₊ budget <1/16 (heavily under-used) | 24,439,463,583,672.93 | 377,372,994,802.87 |
  | III chem | **10.268** | 428 | 16,233 Toffolis, **λ_eff 47.037** (floor 46.79), E_gap margin **7·10⁻⁷** (saturated) | 3,355,599,588.32 | 326,800,030 |
- **Gap arithmetic:**
  - To **24.0** by improving ONE benchmark only (+0.67 %): invsqrt 20.65→**20.79**, OR dqi 64.76→**65.19**, OR chem 10.268→**10.34**.
  - To **28.0** (×1.60) by improving ONE benchmark only: invsqrt →**33.0**, OR dqi →**103.6**, OR chem →**16.4**. Plausible combo: invsqrt 30× + dqi 70× + chem 11× → GM ≈ 28.5.
- **Working hypothesis:** the >24.0 tier is **non-public work**, most likely a **compiled constant-seed invsqrt at ~30×** (or equivalent private invsqrt/dqi). Community intel: *"grinding an incumbent circuit family yields ~11 % in 3 weeks; switching families yields ~60 % in 2 days"* — family switches, not grinding, produce the big jumps.

---

## 3. WHAT IS ALREADY DEAD (do not re-derive; build on these conclusions)

1. **Constseed as a rank-1 vehicle — PARKED.** We built both raw variants full-domain PASS: two-Newton raw = 509Q/9434CCX/**0.42×**; lookup-seed (QROM 512×8) = 384Q/8581CCX/**0.614×**. Both are **wider AND more expensive than the official reference raw** (260Q/7735). Root cause: a cheap seed (2⁻⁸, small ROM) forces **two** Newton steps (wide); one Newton step needs a precise seed (2⁻¹², not cheap). Projection: even a *perfect* transfer of the incumbent's optimization gains (4.19× on Q, 5.17× on CCX) → ~91Q/~1660CCX ≈ **12.7× < SOTA 20.65×**. So constant-seed cannot beat the current invsqrt SOTA unless the optimization transfer itself is broken. **Reopen only if you find a compiled constant-seed ≥25× OR a one-Newton-cheap-seed construction.**
2. **DQI width lever — CLOSED.** 892Q is a strict renumbering floor: the working set of 52 qubits (ids 840–891) is held simultaneously at every binding peak (interval-graph clique, rigorously checked); break-even ≈ 893 Toffolis per freed qubit; all multi-qubit scenarios net-negative. 892→860 infeasible from public source. ΔGM ≈ 0.
3. **Product-caching / HMR port onto the 62Q invsqrt — CLOSED.** Exact GF(2)-ANF symbolic pass found **zero genuine repeated products** (invsqrt is one-shot Newton arithmetic, compute-once/clear-by-measurement; DQI's caching wins came from an *iterative* decoder's repeated flags).
4. **Chemistry angle-loader / shape-truncation — PARKED.** Loader is HMR-based with cost-free uncomputation; SOTA 126Q layout is co-designed with RM(1)-coded words; shape-truncation fails energy checks. We ride public weight/factorization releases instead.
5. **One-Newton numerical probe:** current seeds too coarse (table 2⁻⁷, cubic 2⁻⁹ → FAIL); viable only with deg-5/4-int or deg-3/8-int seed (output 2⁻²⁹…2⁻³⁶) — marginal CCX, not pursued.
6. **Dead micro-ideas:** x→4x/odd-s 1/√2 (false premise — pair-normalization = even shifts, no 1/√2 factor); two-level-linear seed; generic caching port.

**Our assets (why some findings are executable for us):** full local verification loop (unmodified official verifiers + kickmix run in minutes; any idea can be numerically prototyped with exact integer models and circuit-verified before spending a submission); fastest public-adoption loop in the community (hours, automated monitoring of datasets/kernels/LB); original constant-seed numerical model with a **better margin than the published spec** ("pwq3" piecewise-cubic: 0.5577 worst err/tol vs published 0.617, published as notebook `tobeetaylor/constseed-invsqrt-reconstruction`); full public source access (somejoint DQI builder, mrmeows 32-stage optimization pipeline incl. Z3-SAT scripts, busyaprime method notes, all circuit files).

**Outreach already sent (2026-11-02):** comment to somejoint (ask for the private `exp/` DQI core / merger), comment to mrmeows (ask for private constseed research package / merger), and a public QVC-forum thread `…/discussion/755075` ("Seeking collaboration / merger"). **Check this thread and those comments for replies as part of your research.**

---

## 4. RESEARCH OBJECTIVES (prioritized — the core of the task)

### R1 — Close the Top-170 gap (+0.054 GM → 24.0). NEAREST WIN.
- Enumerate **every public portfolio scoring ≥ 24.0** (if any exist publicly). If none, **confirm the >24.0 tier is entirely non-public** (this decides whether Target A is reachable by adoption alone or needs private work).
- Find the **single cheapest ~0.7 % improvement available publicly** in any one benchmark: a newer kernel/dataset we haven't adopted, a parameter tweak, a rotation-count reduction, a t_count cut. We are currently at the *bottom* of the public pack — someone has already passed us; identify what they did.
- Determine **which benchmark has the thinnest public margin to +0.7 %** right now (i.e., where is the next public release most likely to land, and can we grab it same-day?).

### R2 — Invsqrt: beat 20.65× (toward 30×+).
- **Lower-bound analysis:** what is the theoretical minimum Q·C for phasing 1/√x over x = 1…3,133,452 (= 3·(2¹⁰−2)²) at relative tolerance 2⁻²⁴? Is 62Q/1495CCX near-optimal, or is there a fundamentally cheaper family? Cite any complexity/lower-bound results.
- **Alternative circuit families / arithmetic cores:** Halley iteration; different normalization schemes; CORDIC-style; table+refine; piecewise polynomials of other degree/partition; exploiting the *specific* domain (not all integers up to 2²² — it's 3·(2¹⁰−2)² structured); periodicity/symmetry/piecewise structure of 1/√x here.
- **Constant-seed:** independently confirm or refute the §3 projection. Has **anyone published a compiled constant-seed invsqrt ≥ 25×**? Is there an optimization method better than Z3-SAT-per-round (which took the incumbent weeks and still missed its ≤86,532-cost target)? Co-design of arithmetic core + layout?
- **Search all public kernels/datasets** for anything beating 62Q or 1,495CCX on invsqrt. Report the current true public SOTA and its lineage.

### R3 — DQI: beat 64.76×.
- **Width:** independently confirm/refute the 892Q floor (§3). Any published **<892Q** decoder? (Note cost ∝ Q²·T ⇒ a width cut is worth ~2× linear — prioritize any credible width idea.)
- **R(ε₊) frontier:** what determines R=1.19126? Can it go below ~1.19? What is the R floor and what drives it?
- **Toffoli (398,138.69/shot):** reduction paths — better belief-propagation schedule, **more aggressive but budget-safe approximation** (we are far under the ε₊<1/16 budget — quantify how much more error we can spend and what it buys), the technique inside somejoint's private `exp/` builder (infer from the public `dqi-sources/` deltas + any documentation).
- Identify the current true public SOTA decoder, its lineage, and the delta to the top private decoders (infer from LB spacing).

### R4 — Chemistry (DFTHCOS): beat 10.26×.
- **λ_eff floor 46.79:** is it family-specific (Lera's second (9,143,40) factorization) or fundamental to DF-THC for FeMoCo76o113e? Is a **different word/factorization family** realistic in ~11 weeks, and what would it require?
- **E_gap margin 7·10⁻⁷ (saturated):** any way to buy margin back without raising cost? (Trade-off between λ_eff coarseness and the energy-gap check.)
- **16,233 Toffolis / 428Q:** reduction paths? The "round29 re-pairing" gap (planner 4874 vs SOTA 4168 CCX) — what closes it?

### R5 — Merger intelligence: who holds the private work.
- **Profile the top-170 teams** (start: Breaking1800, jackvd, pjmathematician, jsday96/tonylica/yeoyunsianggeremie, massasato1999/paritoshtripathi/ttyn4519/yash9439, and the rest down to rank 170). From their **public kernels/datasets/submission cadence**, infer **which benchmark each is privately strong in**.
- Identify **complementary merger candidates**: teams strong where we are weak (ideally strong **invsqrt** or strong **chem**), with a public presence we can reach. Rank them by (complementarity × reachability × likelihood to merge before 2027-01-13).
- **Timing strategy:** interplay of longest-leader (ends 2027-01-04), merger window (opens 2027-01-13), deadline (2027-01-20). When to approach, when to submit safe-best, how to preserve credit chains (Apache-2.0).

### R6 — Structural / rules / cross-benchmark.
- **Verify the exact scoring formula** (§1) by reproducing 23.94667 from our known component costs, and reproduce a few other teams' scores from any public data you find. Flag any discrepancy (e.g., is it truly a plain geometric mean, or weighted? is Q the peak or something else? is there a per-benchmark cap?).
- Any **unused rule, edge case, or cross-benchmark technique transfer** we are missing? Systematic **error-margin-as-currency** exploitation across all three benchmarks (where is margin currently "wasted" that could be spent to cut cost)?
- Re-examine the **"verifiable structure"** constraint for any under-used primitive (e.g., measurement-based uncomputation patterns, phase tricks) that the top teams might exploit.

---

## 5. SPECIFIC SOURCES TO MINE (start here; expand as needed)

**Kaggle datasets (public):**
- `somejoint/qcc-dqi-892-q26` (DQI 892Q decoder + `dqi-sources/`; the private `exp/` core is the key unknown)
- `mrmeows` code: `qcc-14-50-everything-i-learned-open-circuits`, `21-0-circuits-let-s-all-reach-the-plateau` (constseed spec + open directions)
- `busyaprime/33-qcc-v8-members`, `yoyobar/qcc-local-sota-20261031`, `heliosli/qcc-circuits-live`
- `manwithacat/vqcc-apache-public-circuits`, `dmitriigluzdov/vqcc-femoco-public-factorization`
- `atakanaldemir/qcc-native-chemistry-and-888q-source-bank`
- `tobeetaylor/constseed-invsqrt-reconstruction` (our own published model)

**Papers / docs:** arXiv:2610.23832 (competition paper); Google Quantum AI **kickmix** + verifiable-compilation documentation; any Google/QAI blog posts on reversible circuit optimization, HMR, product caching.

**Leaderboard / forum:** current public leaderboard (all 2056 teams); QVC discussion forum, **especially thread `…/discussion/755075` (ours) and the somejoint/mrmeows comment threads** — report any replies.

**GitHub:** any public repos behind the named kernels (optimization pipelines, Z3-SAT scripts, decoder builders).

---

## 6. OUTPUT FORMAT (strict)

1. **Current-state verification** (as of today): our exact rank/score, the true public SOTA per benchmark, whether any public portfolio ≥24.0 exists, and any new replies to our outreach. Cite sources + dates.
2. **Findings** — one block each:
   - **Claim** · **Benchmark** (I/II/III/meta) · **PUBLIC or PRIVATE**
   - **Evidence + citation** (URL / arXiv / slug / kernel ref / date)
   - **Numeric impact** with shown arithmetic (Δratio, ΔGM, resulting rank band)
   - **Effort** (h/d/wk) · **First local validation step** (concrete, runnable in our loop) · **Confidence** (high/med/low) · **Main failure mode**
3. **Ranked action list**: top 10 by (impact × probability) / effort, each tagged with which target it serves (A=24.0, B=28.0, or both).
4. **Merger shortlist**: top 3 complementary teams with reachability + a suggested first message.
5. **"Could not verify / open questions"**: be explicit about gaps and what would fill them.
6. **Challenge**: the 3 assumptions in this brief you believe are most likely wrong (candidates: "the >24.0 gap is mainly invsqrt"; "constant-seed is the right family switch"; "the public frontier will keep rising without us"; "pwq3's better margin translates into a better compiled circuit"; "892Q is the DQI floor"), and the **single piece of evidence** that would flip each.

---

## 7. HARD CONSTRAINTS (competition rules — do not violate)

- Circuits must be expressible in kickmix and respect the verifiable-structure constraint (reversible classical logic + phasing + measurement-based uncomputation).
- Verifier parameters are fixed (domains, tolerances, shot counts, seeds/salts, register conventions). Ideas may exploit **allowed** budgets (e.g., DQI's ε₊<1/16) but never change the rules.
- Adopted third-party circuits require preserved credit chains (Apache-2.0) — shapes collaboration strategy.
- Submission format: `submission.zip` containing `invsqrt.kmb`, `dqi.kmb`, `dfthcsos/angle_k_{0..14}.kmb`, `dfthcsos/submission.npz`.
