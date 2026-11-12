# RANK-1 PROMPT — Google Quantum AI · Verifiable Quantum Circuit Compilation

> **Nutzung:** Alles ab der Linie `PROMPT START` kopieren und an die KI schicken (ChatGPT / Claude / Gemini / DeepSeek — je eine Instanz pro Anbieter für unabhängige Zweitmeinungen).
> Der Prompt ist **self-contained**: alle Fakten, Zahlen, Stand, Negativ-Ergebnisse und die komplette Dateimap des Repos sind drin. KIs mit Repo-Zugriff können über die Dateimap (§9) tiefer graben; ohne Zugriff reicht der Text.
> Stand: **2026-11-03 ~17:45 UTC**. Deadline: 2027-01-20.

---

## PROMPT START

You are advising a solo Kaggle competitor in **"Google Quantum AI – Verifiable Quantum Circuit Compilation"** ($150k pool, deadline **2027-01-20 23:59 UTC**). We are at **rank ~95–99 / 2169 teams with score 24.45812**; rank 1 is **28.82853**. Your task: generate **concrete, novel, quantitative ideas that could get us to rank 1** — not generalities. For every idea give: mechanism, which benchmark it applies to, expected numeric effect (show your arithmetic against the numbers in §10), effort estimate (hours/days/weeks), the first local validation step, and the main failure mode. Rank all ideas by expected value = (impact × probability) / effort. Provide at least 12 ideas, of which at least 4 must lie OUTSIDE the directions already explored (§4). Include at least 3 meta-strategy ideas (merger/collaboration, timing, submission allocation). Finish with the challenge section (§7). Do NOT re-suggest anything ruled out in §4. Answer in English. Be specific, quantitative, and honest about uncertainty; tag every non-trivial claim [FAKT]/[EMP]/[HYP]/[SPEK] and never invent sources or numbers.

---

### 1. HOW THE COMPETITION WORKS

Teams submit one zip (`submission.zip`) containing circuits for three benchmarks in Google's **kickmix** format: `invsqrt.kmb`, `dqi.kmb`, `dfthcsos/angle_k_{0..14}.kmb` + `dfthcsos/submission.npz`.

**Verifiable structure:** circuits may only use reversible classical logic (Toffoli-type gates), phasing operations (rotations), and measurement-based uncomputation (HMR: measure an ancilla instead of uncomputing, conditionally fixing phase). This makes them exactly classically simulable per input by Google's `kickmix` simulator — the official verifier fuzz-tests every legal input (deterministic seeds/salts).

**Score = geometric mean of three ratios:**
```
Score = ( r_I · r_II · r_III )^(1/3)
r_k   = reference_cost_k / our_cost_k
```
Cost models (authoritative, from official verifier source + competition paper arXiv:2610.23832):
- **Benchmark I (invsqrt) & III (chemistry):** `cost = Q_peak × C` where `C = mean_executed_Toffolis + (t_count + Σ_rotations(0.56·log2(1/ε_j) + 5.3)) / 4` — **the rotation sum is divided by 4** (T-gate accounting converted to Toffoli-equivalents). Verified numerically: 1,289.29 + (20.5 + 41×28.78)/4 = 1,589.26; ×62Q = 98,535 ≈ official 98,533.87.
- **Benchmark II (DQI):** `cost = R(ε₊) × Q² × T` — **Q SQUARED** (confirmed from `data/verifiers/dqi/verify_submission_dqi.py`: "the score is R(eps_plus) * Q^2 * T"). `R(ε₊) = ln2 / −ln(1/2 + 2√ε₊)`; the verifier requires **ε₊ < 1/16 — not zero errors**. **Width floor: 70 syndrome registers × 12 bits = 840 qubits are interface-mandatory** — current circuit is 891Q, so width-only improvement tops out at GM 25.44 (×(891/840)^(2/3)). DQI gains must come from T (Toffolis) and the R/T trade surface. Breakeven table for spending the ε₊ budget (R at ε₊ vs gate reduction needed to break even vs R=1.19126): ε₊=0.001→R=1.207 (need −1.3% gates), 0.002→1.311 (−9.2%), 0.005→1.561 (−23.7%), 0.010→1.943 (−38.7%). Optimize total R·Q²·T, not gate count subject to passing.

Consequences:
- Geometric mean ⇒ a ×factor improvement counts equally in ANY benchmark. Improving the weakest task (chemistry, 10.66×) is as valuable as improving the strongest.
- Error margin is a currency that buys circuit cost: tighter margin forces finer (more expensive) rotations. Only DQI has a usable approximation budget (ε₊ < 1/16); invsqrt and chemistry margins are saturated (§2).
- Max **5 submissions/day**, scoring ~45 min, LB keeps best score. Identical bytes → identical score (deterministic), except DQI where the shot draw can change R slightly (Poisson: p(≥2 failures) ≈ 1.6% on current circuit).

**Prize structure:** $50k 1st, $25k 2nd, $10k 3rd, $5k ×3 (4th–6th); plus $50k additional: **mid-competition milestone $10k — "The team with the highest public leaderboard score at 2026-11-20 wins, provided its notebook is public"** (NOT auto-met by having published a notebook; it is a live target 17 days out: we need top LB score among teams with a public notebook by Nov 20), longest-leader $10k (LB period ends **2027-01-04**, qualifying notebooks must be public by then), single-task performance prizes $30k. Winner license Apache 2.0. Team size ≤ 5.
**Merger rules (authoritative, from competition Overview/Timeline + Rules §5c/§5d/§6a):** **2027-01-13 is the TEAM MERGER DEADLINE (last day to join or merge teams) — mergers are legally possible NOW**, subject to: (i) combined team ≤ 5 members, (ii) combined submission count ≤ permissible for one team at merger date (5/day × days running — we have used only ~6, so we can merge with heavy submitters like #1 with 57 subs), (iii) completed before 2027-01-13. **CRITICAL: "No private sharing outside of Teams" (Rule 5d) and no private code sharing between separate teams during the competition (Rule 6a)** — any pre-merger private component exchange is a rule violation. The only legal path to another team's private work is forming a team / merging. Public forum sharing is allowed ("It's okay to share code if made available to all Participants on the forums").

### 2. THE THREE BENCHMARKS — SPEC AND CURRENT STATE

#### Benchmark I — Invsqrt (our ratio: **21.0768×**)
Phase a qubit by **1/√x** (in turns) for every integer x = 1 … 3,133,452 (= 3·(2¹⁰−2)²), relative tolerance 2⁻²⁴. Reference cost: 2,076,774.23.
Current public record (what we run, sha `e4ed188b`, Kirill Tymchishin "Four Loaders, Eight Toffolis", released 2026-11-03): **62 qubits**, mean executed Toffolis **1,289.29** (max 1,487), t_count 20.5, 41 fine rotations (ε ≈ 2.43·10⁻¹³), cost **98,533.87**, worst error/tolerance **0.99932 at x=161 → error budget saturated, no approximation headroom**. Lineage: mrmeows/team-selenium 63Q → busyaprime → yoyobar 62Q cone rewrites → Özer phase patch → Ehan Mallick two 3-to-2 AND merges → Kirill four-loaders/eight-toffolis. Structure: one-shot Newton–Raphson, compute-once + clear-by-measurement (897 HMR ops).

#### Benchmark II — DQI Reed–Solomon MBUC syndrome decoder (our ratio: **65.1066×**)
m=4095 codeword positions, n=70 syndromes, corrects up to l=35 errors over GF(2^b). Per shot: restore syndrome registers S0..S69, return all other qubits to |0>, multiply global phase by (−1)^Σ popcount(e_j & M_j); Z_POW gates forbidden. Verifier: 102,400 shots, ε₊ < 1/16 required. Reference cost: 24,439,463,583,672.93.
Current public record (what we run, sha `fc3ba816`, Syed Asad Ali "VQCC 24.43 Portfolio", via alexchilton's verified portfolio, released 2026-11-03): **891 qubits**, mean Toffolis **396,921.5** (max 397,194), R = 1.19126 (0 value/phase errors on our draw, ε_eff 0.000866), cost **375,376,238,975**. Gains so far came from: measurement-based uncomputation of flag-clearing blocks, **product caching** (symbolic hash of Boolean function per wire per gate; repeated AND products cached on provably-idle wires, placement via exact LP — removed ~2,800 Toffolis/shot), deliberate approximate rare branches exploiting the ε₊ budget (~1,830 Toffolis/shot saved). **Full decoder builder source is public** (`somejoint/qcc-dqi-892-q26`, mirrored in our repo `work/dqi_sources/`).

#### Benchmark III — DF-THC chemistry, FeMoCo76o113e ground state (our ratio: **10.6621×**)
Givens-rotation state prep + 15 angle-loader circuits (k=0..14, each ≤128 qubits) + learned factorization weights (`submission.npz`). Cost = λ_eff × Toffolis × Qubits, where λ_eff = √(E_gap·(2Λ − E_gap)). Hard limits: error_1 (one-body residual) ≤ 20 mHa, error_2 (two-body residual) ≤ 20 mHa, Λ > 49.0, E_gap > 3.914898 Ha. Reference cost: 3,355,599,588.32.
Current public record (what we run, Heliosli weights `cef141d1` on Lera's (9,143,40) factorization, manwithacat HW angle loaders, released 2026-11-03): **428 qubits**, **15,629 Toffolis**, λ_eff **47.0494042**, error_1 10.216 mHa, **error_2 19.9999998 mHa (margin 0.00000018 mHa — razor-thin but deterministic)**, E_gap 3.9151481 (margin 2.5·10⁻⁴), cost **314,723,439**. The λ_eff floor for the current word/factorization family is ≈ 46.79 (we are 0.5% above it); the E_gap floor is binding. Recent community gains: kernel-relation search (GF(2)) for angle loaders (manwithacat "Hedge Wizardry" HW-12/13/14: 16,071 → 15,629 Toffolis), weight refits (heliosli, somejoint-Claude-refit), matousakura's own loaders k_0..3 (75→77 relations).

### 3. WHERE WE STAND — AND THE FIELD DYNAMICS (critical context)

- Our score path: 23.24970 (10-31) → 23.91003 → 23.94667 (rank 355, 11-02) → 24.15189 (rank 462!) → 24.17538 → **24.45812 (rank 95, 11-03)**. Note: score rose while rank fell once, because **the field accelerates faster than any single team's adoption loop**.
- **The public frontier moved 24.15 → 24.175 → 24.458 within ONE day.** Three new task records were published between 12:32 and 14:53 UTC today alone. We sit in a **20-team cluster at exactly 24.45812** (everyone adopted the same assembler output). Pack tip (rank 40) is already at **24.72** — better components exist than what we run.
- **Leaderboard top (today):** #1 "James & Geremie & Tony" **28.82853** (members jsday96, tonylica, yeoyunsianggeremie; 57 submissions; was "Quantum AI Team" at 27.32 yesterday → **+1.5 GM overnight** = aggressive coordinated private iteration). #2 "Schrödinger's cat lived" (pjmathematician, SOLO) 28.076 (+0.6 overnight). #3 Breaking1800 27.996. #4 Jack (jackvd) 27.792. #5 Thinking... (4-person team) 26.81. The elite (≥26) is almost entirely **coordinated teams or prolific solos with private work**; the public frontier (≈24.5–24.7) is far below.
- **Gap arithmetic to rank 1:** (28.82853/24.45812)³ = **×1.637** on the product of ratios. If only ONE task improved: invsqrt 21.08→34.5×, DQI 65.11→106.6×, chem 10.66→17.46×. Plausible multi-task combos reaching ≥28.8: e.g. invsqrt 29× + DQI 72× + chem 11.5× → (29·72·11.5)^(1/3) = 28.85; invsqrt 30× + DQI 75× + chem 12× → (30·75·12)^(1/3) = 30.0.
- **Community hub (merger-relevant):** manwithacat (James Barlow) operates the shared infrastructure of the public pack: `vqcc-apache-public-circuits` dataset (every public circuit + local scores + credits + factorizations), `vqcc-chemistry-negative-results` dataset, Rust `kickmix-engine` (reproduces official verifier field-for-field), and a SHA-gated portfolio-assembler notebook ("The Real $150K Was the Friends We Made", 79 votes) that picks the cheapest verified public circuit per task and explicitly invites contributions ("please share your own [negative results]: post them in the discussion"). The pack converges through this hub.
- **Adoption race dynamics:** public releases are adopted byte-exactly within hours by many teams (SHA-pinned). Our edge was the fastest adoption loop; that edge is now commoditized (the assembler does it automatically). Pure adoption cannot reach the elite tier — the top teams' work is private until (possibly) the merger window.

### 4. WHAT WE HAVE TRIED AND RULED OUT (do NOT re-suggest)

1. **Product caching / HMR clearing ported to the 62Q invsqrt:** exact GF(2)-ANF symbolic pass found zero genuine repeated products (one-shot Newton arithmetic has none; DQI's gains came from an *iterative* decoder's repeated flags). Closed.
2. **Constant-seed invsqrt family switch (mrmeows' described model):** we independently reconstructed the numerical model with exact integer truncation and validated it over the full domain (128-entry seed table: worst err/tol 0.6434; our piecewise-cubic variant "pwq3": 0.5577 — better than his claimed 0.617). BUT the raw kickmix build comes out **wider and costlier than the reference** (projection ≈12.7×, far below current SOTA 21.08×); competitive compilation would need the incumbent team's 32-round Z3-SAT exact-rewrite pipeline re-derived for a new core. **PARKED** — not the path to rank 1 at current evidence.
3. **Chemistry angle-loader optimization beyond the public line:** loader is HMR-based with cost-free uncomputation; SOTA layout is co-designed with RM(1)-coded words; shape-truncation fails energy checks. We now ride public weight/factorization/loader releases instead.
4. **Approximation budgets elsewhere:** invsqrt margin 0.99932 (saturated), chemistry error_2 margin 0.00000018 mHa + E_gap margin 2.5·10⁻⁴ (saturated). Only DQI's ε₊ < 1/16 is usable, and the community already exploits it.
5. **DQI width renumbering:** 892Q (now 891Q) is a graph-specific bound of the current decoder architecture — renumbering alone won't shrink it. **However, alternative decoder architectures remain a live open direction** (this is NOT closed).
6. **Lera's "DF-THC 10x compact groups" seed construction** (from Hamiltonian alone, no trained weights): reaches 10.413× at (8,143,45)/427Q — **below** our 10.6621×. Not adoptable for score; its finding (compactness, not vector quality, orders tables) is research input.
7. **psalmprax 10-bit angle family** (123-qubit loaders, J=10 words): cheapest family inadmissible (error_1 = 242 mHa ≫ 20); 9-bit delta-compression falsified (Givens sign invariant holds on only 78.59% of words). Negative result, documented.
8. **Naive adoption gaps:** we reproduce every public release byte-exactly locally (SHA-pinned) and submit within hours; our LB score tracks local verification exactly (24.15189, 24.17538, 24.45812 all matched to 5 decimals).

### 5. OUR ASSETS (what makes ideas executable for us specifically)

- **Full local verification loop:** unmodified official verifiers + kickmix in minutes per circuit on our machine (commands in §9). Any idea can be numerically prototyped (exact integer models) and circuit-verified before consuming a submission.
- **Fastest adoption loop in the community** (automated monitoring of datasets/kernels/leaderboard; sub-hour reaction).
- **Full public source access:** SomeJoint's DQI decoder builder, mrmeows' 32-stage optimization pipeline (Python + Z3-SAT scripts), busyaprime's method descriptions, all circuit files, manwithacat's datasets and Rust engine.
- **Original constant-seed numerical model with better margin than the published spec** (pwq3 0.5577 vs 0.617) — option value if compilation becomes tractable.
- **Community visibility:** published research notebook (milestone prize met), active forum/Discord presence, credit chains preserved on every adoption (we are a trusted node in the hub).
- **Submission budget:** 5/day, best-score retention ⇒ exploration is nearly free (a failed submission costs only a slot, never our standing).

### 6. WHAT WE SPECIFICALLY WANT FROM YOU

1. **The elite gap is private work — how do we close it without being a team?** Concrete paths: (a) which single benchmark offers the largest ΔGM per unit of original effort given the cost models in §1 (do the arithmetic for each candidate direction; note the single-task requirements from §3: invsqrt→34.5×, DQI→106.6×, chem→17.46×); (b) decoder architecture alternatives for DQI below 891Q or with lower T (e.g., different BP schedules, different LDPC/RS code representations, quantum signal processing for the syndrome processing, width reduction via Q² leverage); (c) chemistry beyond the λ_eff floor 46.79 — is a different word/factorization family realistic in ~10.5 weeks, and what would it require (Lera's compactness finding as input); (d) invsqrt beyond 21× without constant-seed — domain-specific structure of x=1..3,133,452, alternative iteration structures, phase-factorization tricks.
2. **Optimization algorithm upgrades:** better than Z3-SAT-per-round exact rewrite discovery (which took the incumbent weeks); co-design of arithmetic core and layout so it optimizes well; automated ANF/product-cache discovery that generalizes across benchmarks; LP/pebbling improvements for the 128-qubit angle-loader cap.
3. **Margin engineering:** anywhere a hard limit (error_2 ≤ 20 mHa, E_gap floor, ε₊ < 1/16, 128-qubit cap) is binding, what is the exact trade surface? E.g.: can chemistry buy Toffolis by spending the 9.8 mHa of error_1 headroom (error_1 is at 10.2, error_2 saturated)? Is there a re-factorization that moves weight between error_1/error_2?
4. **Meta-strategy (≥3 ideas):** merger targets and approach — NOTE: mergers are legally possible NOW (deadline 2027-01-13 is the LAST day, not an opening), but **private code/data sharing outside a team is a rule violation** (§1) — so any approach must lead directly to team formation/merger, not "research discussion" with code exchange. Profiles that complement us (strong private DQI/chem, weak invsqrt?); how to approach "James & Geremie & Tony" (57 subs — we can merge with them because we've used only ~6) vs the manwithacat hub vs pjmathematician (solo at 28.08); timing around milestone prize (2026-11-20: highest LB score + public notebook) and longest-leader end (2027-01-04); allocation of 5 submissions/day between safe-best and exploration; whether publishing our own components to the hub raises our adoption-rank ceiling.
5. **Cross-benchmark transfer:** techniques that move between tasks (product caching worked for DQI's iterative structure; what is the iterative structure hiding in chemistry's 15 loaders or invsqrt's normalization?).
6. **Anything we're structurally missing:** an unused rule, a different decomposition of "verifiable structure", a scoring-model exploit that is legal (e.g., DQI's R(ε₊) depends on the verifier's shot draw — is there a legal way to make R robustly minimal rather than lucky?), or a completely different angle.

### 7. CHALLENGE US

After your idea list, name the 3 assumptions in this brief you believe are most likely wrong (candidates: "the elite gap is mostly non-public work"; "adoption race is commoditized"; "constant-seed is parked correctly"; "DQI width is architecture-bound, not just graph-bound"; "chemistry is at its physical floor"), and say what single piece of evidence would flip each.

### 8. HARD CONSTRAINTS

- Circuits must be expressible in kickmix under the verifiable-structure constraint. Verifier parameters are fixed (domains, tolerances, shot counts, seeds/salts, register conventions). Allowed budgets may be exploited (DQI ε₊ < 1/16), rules never changed.
- Adopted third-party circuits require preserved Apache-2.0 credit chains (shapes collaboration strategy).
- Submission format: zip named `submission.zip` with the 18 files listed in §1.
- We are a solo competitor (team slot capacity: up to 5 members at merger).

### 9. FILE MAP — ALL RELEVANT FILES (repo root: `/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum`)

If you have filesystem access, use this map. Binary `.kmb` circuits are kickmix-serialized (not human-readable text); their verified metrics are in §2 and the logs listed here.

```
data/                          → symlink to ~/.cache/kagglehub/competitions/google-verifiable-quantum-circuit-compilation
  verifiable_circuit_compilation.pdf    official competition paper (full spec)
  verifiers/dfthcsos/verify.py          OFFICIAL chemistry verifier (CLI: verify.py <dfthcsos-dir>)
  verifiers/invsqrt/verify_submission_invsqrt.py   OFFICIAL invsqrt verifier (CLI: … <invsqrt.kmb>)
  verifiers/dqi/verify_submission_dqi.py           OFFICIAL DQI verifier (CLI: … <dqi.kmb>; docstring confirms cost = R(eps_plus)*Q^2*T)
  kickmix/                         kickmix simulator library (.so)
  sample_submission/               Google's reference submission
starter_kit/                     competition starter kit
  starter_kit/verifier/            reference verifier implementation (verify.py, costs.py, dfthc_math.py, circuits.py, reference.py, score.py)
  starter_kit/starter/task1_factorization/   chemistry factorization trainer (train_df_thc_qaggle.py, check_factorization.py)
  starter_kit/starter/task2_angles/          angle encoding (encode.py, trees.py)
  starter_kit/starter/task3_circuits/        circuit builders (build_circuits.py, angle_k_kickmix.py)
qualtran/                        Google Qualtran source (reversible-circuit library; kickmix .so built from it lives in .venv)
external/refs/uncompute/         reference implementations incl. tasks/dqi-hermitian, tasks/dqi-reed-solomon, lean proofs (lean/dqi, lean/divsteps), tools/
docs/research/                   scraped competition pages: rules.txt (full legal rules), overview.txt, discussion.txt, leaderboard.txt, data.txt, paper.txt (text of the PDF), fetch_topic.py, nbtext.py
notebooks/                       pulled public notebooks (constseed-invsqrt-reconstruction.ipynb = OUR published research; dqi-kmb-at-59-56854.ipynb; lb-22-86841…; lb-22-99-invsqrt-101-62-qubits.ipynb; 22-57-lb-verified-three-task-portfolio.ipynb; etc.)
sota_mrmeows/                    mrmeows' public package: circuits/, sources/ (32-stage optimization pipeline incl. Z3-SAT scripts), README.md
sota_yoyobar/                    yoyobar's public package: submission/, evidence/, RESEARCH_TIMELINE.md, research-timeline.json, portfolio-manifest.json, SOURCES.md
work/archive/submissions/        OUR submitted zips: qvc-001-yoyobar-portfolio.zip, qvc-002-busyaprime-v14.zip, qvc-003-hybrid-best.zip, submission.zip (latest)
work/frontier_scan/              TODAY'S frontier scan (2026-11-03):
  *.ipynb                          pulled notebooks: best-of-public-portfolio-vqcc-24-0x-class (matousakura), the-real-150k-was-the-friends-we-made (manwithacat assembler), df-thc-10x-compact-groups (Lera), benchmark-iii-a-123-qubit-angle-family (psalmprax)
  mwa_output/                      manwithacat assembler OUTPUT: submission.zip (= our qvc-006, LB 24.45812), check.json (GM 24.458128565853283 + picks), receipt.json (gates G1–G4, headroom analysis, DQI Poisson risk), checks.csv (per-task costs/ratios), frontier_commentary.md (today's record changes), hedge_blend_used.json, leaderboard_summary.csv, credits.csv
  mwa_unpacked/                    unzipped qvc-006 (invsqrt.kmb, dqi.kmb, dfthcsos/)
  mwa_verify_{invsqrt,dqi,chem}.log  OUR local official-verifier PASS logs for qvc-006 (exact metrics)
  syed_output/, chilton_output/    comparison portfolios (GM 24.4321) + SHA diff vs ours
  mato_output/, mato_unpacked/     matousakura portfolio (= our qvc-005, LB 24.17538)
work/somejoint_2415/             somejoint 24.15 portfolio (= our qvc-004, LB 24.15189) + verify_dqi.log
work/dqi_sources/                SomeJoint's PUBLIC DQI decoder builder source (audit.py, conversion.py, direct_forney.py, division.py, lowwidth.py, narrow_gauge.py, …)
work/invsqrt_caching/            our product-caching investigation (zero-gain result, §4.1)
work/constseed_build/            constant-seed raw build (parked, §4.2)
work/lb_scan/monitor.py          automated LB/dataset/kernel monitor (30-min loop)
work/chem_*.py                   chemistry measurement/recompile scripts (chem_measure.py, chem_recompile.py, chem_shape_probe.py, chem_gluzdov_planner.py, chem_emit_borrowed.py)
docs/overview/deep-research-output/2026-11-03-chatgpt-deepresearch.clean.md   full ChatGPT Deep Research report on the competition (3,493 words; note: its "linear width" DQI claim was REFUTED by the official verifier source — see §1)
docs/overview/ai-advisor-prompt.md previous advisor prompt (STALE state: rank 255/23.91 — superseded by this document)
docs/overview/qvc-expertise-prompt.md expertise-extraction prompt (German; runs the same competition through ChatGPT/Claude/DeepSeek/Gemini)
main.py, notebooks/sandbox.ipynb scratch entry points
.venv/                           Python env: numpy 2.5.4, scipy 1.18.1, kickmix (qualtran build), kaggle CLI
```

**Local verification commands (any AI with repo access can run these):**
```
cd /Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum
.venv/bin/python data/verifiers/dfthcsos/verify.py <dfthcsos-dir>                 # chemistry, ~minutes
.venv/bin/python data/verifiers/dqi/verify_submission_dqi.py <dqi.kmb>            # DQI, ~10 min
.venv/bin/python data/verifiers/invsqrt/verify_submission_invsqrt.py <invsqrt.kmb> # invsqrt, full domain 200M shots
.venv/bin/kaggle competitions submissions -c google-verifiable-quantum-circuit-compilation
.venv/bin/kaggle kernels list --competition google-verifiable-quantum-circuit-compilation --page-size 40 -v
```

### 10. APPENDIX — KEY NUMBERS (for your arithmetic)

| quantity | value |
|---|---|
| our score (best, LB) | **24.45812** (rank 95–99 / 2169 teams, 2026-11-03) |
| rank 1 | 28.82853 ("James & Geremie & Tony", 57 subs) |
| rank 2 | 28.07608 (pjmathematician, solo) |
| pack tip (rank 40) | 24.72175 (better components than ours exist) |
| product factor needed for 28.83 | **×1.637** |
| reference costs (I, II, III) | 2,076,774.23 · 24,439,463,583,672.93 · 3,355,599,588.32 |
| our costs (I, II, III) | 98,533.87 · 375,376,238,975 · 314,723,439 |
| our ratios (I, II, III) | 21.0768 · 65.1066 · 10.6621 |
| invsqrt SOTA | 62Q, 1,289.29 mean Toffolis, 41 rotations, err/tol 0.99932 (saturated) |
| DQI SOTA | 891Q, 396,921.5 mean Toffolis, R=1.19126, ε_eff 0.000866 (budget 1/16) |
| chem SOTA | 428Q, 15,629 Toffolis, λ_eff 47.0494 (family floor ≈46.79), error_2 margin 1.8·10⁻⁷ mHa, E_gap margin 2.5·10⁻⁴ |
| timeline | today 2026-11-03 · **milestone prize judged 2026-11-20** (highest LB score + public notebook) · longest-leader ends 2027-01-04 · **team merger deadline 2027-01-13 (mergers possible now)** · deadline 2027-01-20 (buffer: submit by 01-19 12:00 UTC) |
| submission budget | 5/day, best-score retention, ~45 min scoring |

// PROMPT END
