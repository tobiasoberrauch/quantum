# VQCC Team — Ausschreibungen & Struktur

Stand: 2026-11-11 · **Sprint-Ziel:** Top-100 (≥25.40) gesichert bis Mitte Dezember → Top-10 (~27.0–27.3) bis Deadline **2027-01-13**.

Alles in einer Datei: Teil A = deutsche Steuerungs-Ebene, Teil B = die vier englischen Ausschreibungen (Best-of-World-Pool ist englischsprachig). Jede Ausschreibung ist selbstständig postbar (Kaggle-Topic, X/LinkedIn, Direkt-Outreach) und funktioniert doppelt als Collab-Offer.

**Inhaltsverzeichnis**
- [Teil A — Team-Struktur & Konditionen (DE)](#teil-a--team-struktur--konditionen-de)
- [Rolle 1 — Lead: Reversible Circuit Synthesis](#rolle-1--lead-reversible-circuit-synthesis--fault-tolerant-cost-optimization)
- [Rolle 2 — Coding Theory & Decoder Expert](#rolle-2--coding-theory--algebraic-decoding-expert-reed–solomon--dqi)
- [Rolle 3 — HPC & Agent Infrastructure Engineer](#rolle-3--hpc--autonomous-optimization-infrastructure-engineer)
- [Rolle 4 — Quantum Chemistry / DFTHC Expert](#rolle-4--quantum-chemistry--block-encoding-expert-femoco--dfthc)

---

# Teil A — Team-Struktur & Konditionen (DE)

## Warum ein Team (Befund aus [CAMPAIGN.md](../strategy/CAMPAIGN.md) + Memory)

Solo-Hebel sind dokumentiert erschöpft:
- **Curation**: alle 3 Tasks am Public-Frontier (Erträge ≈ +0.004…+0.07 pro Fund, abnehmend).
- **invsqrt**: lokal optimal (Beam-Search: 0/6 Toffoli-Hotspots reduzierbar).
- **chem**: Winkel-Compiler exakt an der ANF-Rang-Untergrenze (4.148 CCX Census, 15/15 Public-Circuits unabhängig validiert) — Compiler-Lever tot.
- **dqi**: der große Hebel (~74k mean Toffolis via Uncompute/MBUC, Inverse-Overhead −12.3 %) ist **architektonisch** und braucht Source-Level-Arbeit am Decoder-Builder.

⇒ Das Team muss **novelle Quantenschaltplan-Architektur** liefern (v. a. DQI), nicht mehr Curation. Score-Modell: `Overall = (R_invsqrt · R_dqi · R_chem)^(1/3)` — x % auf EINE Benchmark = x % overall.

## Aktuelle harte Zahlen (2026-11-11)

| Größe | Wert |
|---|---|
| Unser Score (banked, ref 58232773) | **25.2952** (Rang ~493/2830) |
| Ratios | invsqrt 22.1109 (Q=62) · dqi 65.2264 (Q=892, T̄≈395k) · chem 11.2224 |
| Top-100-Cutoff | 25.40112 (steigt täglich) → braucht dqi ≥ 66.05 bei fixem inv+chem |
| Top-10-Cutoff | ~27.3 (SomeJoint Rang 9 @ 27.34, +0.34/Tag) → braucht dqi ≈ 80 |
| dqi-Zielrechnung | ~5.000 mean Toffolis sparen (≈4,5 % der 111.308 MBU-Kandidaten) → Top-100 |
| Deadline | 2027-01-13 (Merger-Deadline laut Report; „20.11"-Variante ungeklärt) |

## Rollen & Priorität

| # | Rolle | Hebel | Priorität |
|---|---|---|---|
| 1 | Lead Reversible Circuit Synthesis | dqi: Toffoli-Architektur am Builder | **P0** |
| 2 | Coding Theory / Decoder Expert | dqi: Algorithmus-Design (RS-Decoding, F₂¹²) | **P0** |
| 3 | HPC & Agent-Infra Engineer | Iterations-Durchsatz (Verifier-Farm, Agent-Loop) | **P1** |
| 4 | Quantum Chemistry / DFTHC Expert | chem: Factorization-Level (T↔λ_eff) | **P2** (optional) |

- Rollen 1+2 arbeiten als Paar auf demselben DQI-Problem (1 = Schaltplan, 2 = Algorithmus). Ein einzelner Weltklasse-Kandidat, der beides kann, ersetzt beide — dann ist das Team 2 Köpfe + Rolle 3.
- Reihenfolge des Engagements: 1 oder 2 zuerst (wer zuerst da ist, zieht den anderen per Pairing), dann 3, dann 4.

## Gemeinsame Konditionen (stehen in jeder Ausschreibung)

- **Sprint:** jetzt → 2027-01-13 (~10 Wochen), remote, Freelance-/Werkvertrag.
- **Arbeitssprache:** Englisch (Codebase, Memory, Kommunikation).
- **Vergütung:** Preispool $150.000 (Kaggle) + Erfolgsbonus an finalen Rang gekoppelt (Betrag im Angebot klären).
- **Governance (verbindlich):**
  - Submissions nur über den Account-Inhaber (Kaggle-Credentials bleiben bei uns; 4 Submits/Tag-Limit; jeder Submit erfordert explizite Freigabe).
  - Kein dqi-Byte-Change ohne vorherige ≥5-Salt-Verifikation (Process-Lesson: Salt-Draws haben schon Scores bewegt).
  - Jede signifikante Entscheidung/Befund/Negativ-Ergebnis in die Evidence-Memory (`~/.agent-memory/kaggle-qvc/`) — Negativresultate sind erste Klasse.
  - Eine Ursache pro Änderung; Messung vor und nach jedem Claim.
- **Onboarding:** voller Repo-Zugriff, laufende Verifier-Umgebung (`.venv-chem`), `qvc_agent`-Loop (63 Tests grün), dokumentierter Lernpfad (`work/frontier_1110/hello_world_circuit.py` → `lernen_stufe0-2.md` → `competition_brief.md`).

## Wo ausschreiben (in dieser Reihenfolge)

1. **Direkt-Outreach an Merger-Kandidaten** — schnellster Pfad, die Ausschreibungen funktionieren doppelt als Collab-Angebot:
   - `crackercoder` (explizit merger-offen, C-Bitparallelen-DQI-Sim + ANF/Toffoli-Uncompute-Tracer + code-only-chem-Generator — infra-komplementär zu Rolle 1/3)
   - `ahoirg` (Ali Haydar Özdağ — tiefstes SomeJoint-Source-Wissen außer Agniv; Brücke zum Builder)
   - `syed3000`, `yoyobar` (Frontier-Rewrites)
   - `SomeJoint` (Agniv Banerjee) — **de-facto-Benchmarkhalter** (Rang 9 @ 27.34, hält DEN 892Q-Builder privat, LB 25.717). Merger mit ihm schlägt jede Einzelanstellung. Topic #755075 ist bereits live und aktualisiert.
2. **Kaggle-Discussion** #755075 („Seeking collaboration / merger") — dort die Rollen als konkrete Offerts posten.
3. **X/LinkedIn** mit den englischen Ausschreibungen (Hashtags: #quantumcomputing #kaggle #VQCC).
4. **Fachkanäle:** Quantum Computing StackExchange; arXiv-Autorenlisten (DFTHC: O'Malley et al.; RS-Decoding: Gao, Viterbi, Feldman; Reversible Synthesis: T-count-Literatur).

## Hinweis „Beste der Welt"

Die besten Köpfe für DQI sitzen teilweise **im Wettbewerb selbst** (SomeJoint, ahoirg, crackercoder, syed3000, yoyobar). Für sie ist „Anstellung" realistisch als **Merger/Collab mit geteiltem Score** zu framen — die Ausschreibungen sind bewusst so geschrieben, dass sie sowohl als Job-Post als auch als Collab-Offer funktionieren (Mission + konkrete Zahlen statt Firmen-Jargon).

---

# Teil B — Stellenausschreibungen (Englisch)

## Rolle 1 — Lead: Reversible Circuit Synthesis & Fault-Tolerant Cost Optimization

**Engagement:** 10-week sprint (November 2026 → January 13, 2027), fully remote, freelance/contract. English working language.
**Context:** Google Quantum AI "Verifiable Quantum Circuit Compilation" (Kaggle, $150,000 prize pool). Our team currently scores **25.30** (rank ~493/2830); the Top-10 cutoff is ~27.3. This role directly determines whether we cross it.

### Mission

Reduce the Toffoli-equivalent cost of our compiled quantum circuits — primarily the **Reed–Solomon syndrome-decoding benchmark ("dqi")** — through novel circuit architecture at the source level of a real decoder builder.

The dqi score model is `S = R(ε⁺) · Q² · T_mean` (lower is better; zero-failure floor `R ≈ 1.19`). Qubits are penalized **quadratically**: a 1% qubit reduction scores like a 2% Toffoli reduction. Both Q and T are levers, and they trade off along a Pareto curve we have partially mapped.

Current best (officially verified): **Q = 892, T_mean ≈ 395,303, ratio 65.23**.
Targets: **ratio ≥ 66.05** (secures Top-100 overall) and stretch **~80** (Top-10 trajectory).

### The problem, concretely

The benchmark implements the sign correction `U_c|s⟩|0⟩_W = (−1)^{c·bin(e(s))}|s⟩|0⟩_W` for correctable errors `wt(e) ≤ 35` of a Reed–Solomon code over `F_{2^12}` with parameters `(m, n, b, r) = (4095, 70, 12, 2016)`: an 840-qubit syndrome input plus a 49,140-bit classical measurement record. The baseline architecture is the Extended Euclidean Algorithm decoder (key equation → Chien search + Forney formula) followed by full uncomputation.

We hold a **bit-exactly reproducible 218-file Python decoder builder** (Apache-licensed lineage, SHA-pinned, builds in ~90 s) whose baseline verifies at ratio 63.14. It is a genuine optimization platform: exposed knobs (qubit ceiling, norm-cache forcing, retained-core keep parameters, forward-cache shift levels) trade Q↔T at the Pareto knee, and its synthesis passes (extract / synthesis / convert / scan / unconvert / unsynthesis / unextract + companion and inverse passes) are modifiable by source edit.

Documented structure in our current best circuit (op census): **CCX 382,190 · CCZ 1,384 · CSWAP 12,012 · HMR 78,990 · R 56,223**, with **301,621 exact triple-repeats (76%)**, of which **111,308 lie within 10k-op windows** — candidates for converting uncompute chains into measurement-based uncomputation (one `HMR` + one classically-controlled `CZ` when `b=1` = **0 counted Toffolis** instead of 1). Saving ~5,000 mean Toffolis (≈4.5% of those candidates) reaches the Top-100 target.

#### Gate set you will optimize against ("kickmix")

Circuits map every computational-basis input to a single basis state up to a scalar phase, so a classical simulator verifies them in time linear in gate count. Four instruction classes:

1. **Reversible classical gates:** `X`, `CX`, `CCX` (Toffoli), `SWAP` — permute basis states.
2. **Diagonal phase gates:** `Z`, `CZ`, `CCZ`, `Z_POW`, `NEG` — leave bits unchanged, add a tracked output phase when all controls are `|1⟩`.
3. **Measurement & reset:** `HMR` (Hadamard, measure in X basis into a classical bit, reset to `|0⟩`; yields phase kickback `(−1)^{b·f(x)}`), `R` (reset a qubit already uncomputed to `|0⟩`).
4. **Classical bit ops:** `BIT_STORE0`, `BIT_STORE1`, `BIT_INVERT`.

Any instruction can be classically controlled per-gate (`if b`) or via a condition stack (`PUSH_CONDITION` / `POP_CONDITION`). Counted cost: `num_toffoli_like` counts only `CCX`/`CCZ`/`CSWAP`; Clifford `Z_POW` angles are free, T-angles cost 1 T, finer rotations are priced analytically. Misusing `HMR`/`R` on still-entangled junk fails the verifier loudly (random sign flip, caught with probability 1/2 per shot).

### What you will do

- Modify the builder's synthesis passes: new pebbling schedules, qubit caching strategies, inverse-overhead elimination, and systematic `del_and` (measurement-based uncomputation) pattern insertion in the hot regions.
- Design Toffoli-minimal reversible circuits for the algorithmic hot spots: field arithmetic in `F_{2^12}` (multiply, invert, trace/norm), key-equation iteration, Chien search, Forney formula.
- Exploit the documented repeat structure (111,308 MBU candidates) with a principled selection rule — naive bulk conversion fails (selection bits are rewritten mid-circuit as scratch; we have measured this: 668/668 apparent "pairs" have distinct monomials). You will find what actually works.
- **Prove operation counts before building** (op census discipline). Every candidate must pass the official verifier: 102,400 shots × ≥5 independent salts, zero failures, strictly lower cost.
- Maintain the evidence memory: negative results, per-region cost tables, the Q↔T Pareto frontier. A future engineer must be able to reproduce every one of your conclusions.
- Pair with Role 2 (coding theory) on algorithm-level changes; you own circuit-level implementation and verification.

### Must have

- **Proven expertise in reversible logic synthesis:** Toffoli/CCZ-minimal designs for arithmetic — adders (Cuccaro/Draper/Maas lineage), multipliers, comparators, division, modular exponentiation. You know the state of the art in T-counts and can cite it.
- **Deep understanding of pebbling** (Barrington's theorem; Håstad–Impagliazzo–Lewin–Nisan–Pudlák), qubit↔gate tradeoffs, and why T-count drives fault-tolerant cost (magic-state distillation overhead makes T the dominant resource).
- **Rigor as identity:** you count operations formally before implementing; "the simulator says it works" is never sufficient without a cost argument. Negative results are written down as first-class outcomes.
- **Fluent C++20 and Python**, with hands-on experience in a real circuit-compilation stack (Qualtran, Cirq, tket, or equivalent).
- **Track record of beating published baselines** — competition, paper, or production system.
- Comfort with a **non-interactive verification contract**: the verifier hashes the raw circuit bytes with SHA-256 combined with a private salt to seed challenge inputs. No hard-coding outputs, no seed fishing. Determinism is the game.

### Nice to have

- Direct experience with kickmix-style gate sets (reversible classical + diagonal phase + `HMR`/`R` + per-gate classical control).
- SAT/SMT-based synthesis (Z3, MiniSat) applied to reversible circuits.
- Quantum error correction background: decoders, measurement-based quantum computation, surface codes.
- Experience modifying a large unfamiliar codebase under **exact type-check constraints** (our builder rejects subclass-based instrumentation — it corrupted the scheduler: Q 893→900, T 482k→2.48M. Source edits only.)
- Kaggle or similar competition experience.

### Toolset you will work with

- **Qualtran** (Google) + **kickmix** package (C++20/Python), binary `.kmb` circuit format.
- **Official verifiers** in a dedicated environment (`.venv-chem`): CPU-bound, single thread per process, 128 GB RAM host; full dqi runs take minutes to ~10 minutes.
- Python 3.11+/3.13, NumPy; C++20, cmake.
- Profiling: flame charts (mark hierarchy: extract/synthesis/convert/scan/unconvert/unsynthesis/unextract + companion/inverse passes), per-region Toffoli counters via source edits.
- Existing agent infrastructure: verifier-gated beam-search circuit optimizer, LLM hypothesis loop (`qvc_agent`, 63 tests green), FastAPI debug UI — extend, don't rebuild.
- Git with SHA-256-pinned artifacts, build manifests, bit-exact rebuilds.

### Success metrics

- **Week 4:** dqi ratio **≥ 66.05** officially verified (≥5 salts, zero failures) → Top-100 secured.
- **Week 10:** best achievable ratio on the stretch path toward ~80.
- Every number above backed by official-verifier PASS.
- Evidence memory current: per-region cost attribution, all negative results, reproducible build commands.

### Terms

Freelance sprint contract, remote. Base fee (hourly or fixed) + success bonus tied to final leaderboard rank (amount in offer). Prize pool: $150,000. We ask for full documentation of methods — the documented technique is the durable asset, and we are happy to credit authors publicly.

**This posting doubles as a collaboration offer.** If you are one of the top teams in this competition holding a stronger DQI base or builder source, a merger with shared score may fit better than a contract — say so in your reply.

---

## Rolle 2 — Coding Theory & Algebraic Decoding Expert (Reed–Solomon / DQI)

**Engagement:** 10-week sprint (November 2026 → January 13, 2027), fully remote, freelance/contract. English working language.
**Context:** Google Quantum AI "Verifiable Quantum Circuit Compilation" (Kaggle, $150,000 prize pool). Our team scores **25.30** (rank ~493/2830); Top-10 cutoff ~27.3. This role attacks the single biggest remaining lever: the algorithm underneath our worst-performing benchmark.

### Mission

Redesign the **classical decoding algorithm** at the root of the dqi benchmark so that its reversible implementation is fundamentally cheaper — then hand proven, counted specifications to Role 1 (circuit synthesis) and verify their implementations against your counts.

The benchmark implements the sign correction `U_c|s⟩|0⟩_W = (−1)^{c·bin(e(s))}|s⟩|0⟩_W` for correctable errors `wt(e) ≤ 35` of a Reed–Solomon code over `F_{2^12}`, parameters `(m, n, b, r) = (4095, 70, 12, 2016)`: 840-qubit syndrome input, 49,140-bit classical measurement record. Baseline architecture: **Extended Euclidean Algorithm** (key equation → Chien search + Forney formula) with full uncomputation.

Score model: `S = R(ε⁺) · Q² · T_mean` (zero-failure floor `R ≈ 1.19`). A 1% qubit reduction scores like a 2% Toffoli reduction. Current best ratio **65.23**; targets **≥ 66.05** (Top-100) and **~80** (Top-10).

Why the algorithm layer is the lever: our circuit-level compiler work is exhausted (measured, documented negative results). The remaining headroom — on the order of tens of thousands of mean Toffolis — lives in *which computations the decoder performs*, not in how cheaply each one is compiled.

### What you will do

- **Validate and refine the operation census** of the current decoder (CCX 382,190 · CCZ 1,384 · CSWAP 12,012 · HMR 78,990 · R 56,223; 301,621 exact triple-repeats, 76%) and attribute cost to algorithmic stages: which stage owns how many Toffolis.
- **Explore cheaper decoding architectures:** Gao's algorithm, Viterbi-style fast Euclidean decoding, Berlekamp–Massey variants, modified key-equation formulations, table-driven vs. computed field operations, and alternative basis representations (polynomial vs. normal basis) for `F_{2^12}`.
- **Minimize finite-field arithmetic exactly:** multiplication (schoolbook vs. Karatsuba vs. Kronecker/Toom), inversion (Fermat vs. extended Euclidean), trace/norm maps — with exact gate-operation counts, no hidden constants.
- **Define the reversible translation** of whichever algorithm wins: which intermediates are kept (qubit cost), which are uncomputed (Toffoli cost), where measurement-based uncomputation applies (`HMR` + classically-controlled `CZ` = 0 counted Toffolis for an AND-wire uncompute), where pebbling schedules (Barrington trees) buy qubits at acceptable T-cost.
- **Run algebraic experiments** in SageMath/Magma/PARI-GP; use SMT solvers (Z3) for structural search — e.g., Chien-search parallelization patterns, table sizes vs. comparison costs.
- **Verify claims two ways:** algebraically (counts derived from the algorithm) and empirically (Role 1's circuits pass the official verifier: 102,400 shots × ≥5 independent salts, zero failures).

### Must have

- **PhD-level (or equivalently demonstrated) depth in coding theory or algebraic complexity:** Reed–Solomon decoding, extended Euclidean algorithm, key equation, Chien search, Forney formula — you can derive operation counts from first principles and defend them.
- **Finite-field arithmetic expertise:** representations of `F_{2^m}`, multiplication and inversion algorithms with their exact costs, basis conversions, trace/norm structure. You have thought about what a field multiplication *costs* at the gate level, not just the flop level.
- **Experience turning algorithms into fixed-cost datapaths.** FPGA/ASIC pipeline design is an excellent proxy: latency-bounded stages, exact resource counts, no amortization tricks that hide constants.
- **Rigor as identity:** you prove counts before anyone builds. You are comfortable being wrong in writing — our evidence memory records negative results as first-class outcomes, and several of our most valuable entries are measured dead ends (e.g., "all 668 apparent same-control CCX pairs have distinct monomials because selection bits are rewritten as scratch mid-circuit").
- **Strong Python and C++;** comfort reading a 218-file codebase whose builder performs exact type-checks.

### Nice to have

- Quantum computing background: uncomputation, phase kickback (`(−1)^{b·f(x)}`), measurement-based computation, T-count reasoning. If absent: we provide structured onboarding — a self-verifying 2-bit adder (16/16 test vectors, 2 Toffolis), kickmix gate-set templates with worked examples, and the full competition brief. The gate set is deliberately classical-simulatable; the barrier is the optimization discipline, not the physics.
- Quantum error correction decoder experience (classical decoders for QEC codes; MBUC semantics).
- SAT/SMT (Z3) for combinatorial structure search.
- Familiarity with the decoded quantum interferometry (OPI/DQI) literature.
- Having competed in or contributed to this exact competition (your strongest signal — tell us what you know that is not public).

### The gate set (primer)

Circuits map every computational-basis input to a single basis state up to a scalar phase; a classical simulator verifies them linearly in gate count. Instruction classes:

1. Reversible classical: `X`, `CX`, `CCX` (Toffoli), `SWAP`.
2. Diagonal phase: `Z`, `CZ`, `CCZ`, `Z_POW`, `NEG` (phase added when all controls are `|1⟩`).
3. Measurement & reset: `HMR` (Hadamard → X-basis measure → classical bit → reset; yields kickback `(−1)^{b·f(x)}`), `R` (reset an already-uncomputed qubit).
4. Classical bit ops: `BIT_STORE0`, `BIT_STORE1`, `BIT_INVERT`.

Per-gate classical control (`if b`) and a condition stack (`PUSH_CONDITION`/`POP_CONDITION`) are available. Counted cost: only `CCX`/`CCZ`/`CSWAP` count as Toffolis; `HMR`+controlled-`CZ` uncomputes an AND wire for **0 counted Toffolis**. Clifford `Z_POW` angles are free; T-angles cost 1 T.

### Toolset

- SageMath, Magma, or PARI/GP for field experiments; NumPy for numerics.
- Z3 / SMT for constraint and structure search.
- Official verifier contract (102,400 shots × ≥5 salts) via the Role 1/3 pipeline.
- Evidence memory + git, SHA-256-pinned artifacts, bit-exact rebuilds.

### Success metrics

- **Week 2:** validated per-stage operation census of the current decoder (which stage owns how many Toffolis; where the 76% triple-repeat structure comes from algorithmically).
- **Week 4:** at least one alternative algorithm variant with a **proven** lower reversible cost, specified to Role 1, implemented, and officially verified.
- **End of sprint:** a decoder architecture that materially moves the ratio toward ≥ 66.05, documented end-to-end (algorithm → counts → circuit → verifier output).

### Terms

Freelance sprint contract, remote. Base fee + success bonus tied to final rank (amount in offer). Prize pool: $150,000. Full method documentation expected; public author credit offered.

**This posting doubles as a collaboration offer.** If you hold a stronger DQI base, decoder source, or unpublished result from this competition, a merger with shared score may fit better than a contract — say so in your reply.

---

## Rolle 3 — HPC & Autonomous Optimization Infrastructure Engineer

**Engagement:** 10-week sprint (November 2026 → January 13, 2027), fully remote, freelance/contract. English working language.
**Context:** Google Quantum AI "Verifiable Quantum Circuit Compilation" (Kaggle, $150,000 prize pool). Our team scores **25.30** (rank ~493/2830); Top-10 cutoff ~27.3.

### Mission

Maximize the number of **verified** circuit candidates per day. Our bottleneck is not ideas — it is the verification loop. Official verifier runs are CPU-bound, single-threaded per process, and take minutes to ~10 minutes (dqi: 102,400 shots per salt, ≥5 salts required per candidate). We operate a 128 GB RAM workstation and an existing autonomous agent (`qvc_agent`: LLM hypothesis → candidate build → verifier-gated keep/discard, 63 tests green, scheduled every 6 hours).

You make this loop **5–10× faster and safer**, and add the compute headroom for aggressive knob sweeps and parallel candidate races. Roles 1 and 2 produce the wins; you determine how many of them we can *test* before the deadline.

### What you will do

- **Parallel verifier farm:** orchestrate verifier processes across cores/machines — process pools, job queue, priority preemption for human-approved candidates. Target: ≥4 concurrent full dqi verifications on available hardware, no cross-talk, crash-safe.
- **Fast pre-checks:** build and maintain stratified-subset adapters (<1 s) that filter candidates before expensive full runs; tune shot budgets statistically — characterize when a pre-check failure is predictive of full-run failure (our dqi score literally uses an upper confidence bound ε⁺ at confidence 1−2^{−128}; you will reason in the same currency).
- **C++20 performance work** on hot paths: builder import (~90 s today), verifier inner loops, `.kmb` serialization. Profile-first (flame charts, perf/Instruments); every change ships with before/after measurements.
- **Scale the agent loop safely:** bounded autonomous runs with explicit stop conditions, watchdogs, cost floors, and human-in-the-loop approval gates. The existing KEEP policy (official PASS + strictly lower cost + explicit approval) stays — you make it faster, not looser.
- **Reproducibility infrastructure:** SHA-256-pinned artifacts, build manifests, bit-exact rebuilds, dependency locks, content-hash caches with correct invalidation semantics (stale caches have burned us; the cache key must cover the command, not just the input).
- **Candidate ledger:** append-only SQLite/Postgres store of every candidate — hash, task, cost, salts, verdict, provenance, timestamp — queryable, and the single source of truth for "what have we already tried."
- **Optional:** cloud burst capacity (spot instances) for sweep weekends, with hard cost caps and automatic teardown.

### Must have

- **Senior systems engineering:** C++20 performance (profiling-driven; memory layout; SIMD where it genuinely helps) and modern Python (async, multiprocessing, subprocess management).
- **Experience operating long-running batch/autonomous workloads safely:** job queues, timeouts, idempotency, crash recovery, bounded loops, clean shutdown. You have run something unattended for days and trusted it.
- **Measurement culture:** you reproduce before you fix; you ship numbers with every claim; "faster" without a benchmark is not a deliverable.
- **Git discipline; Linux/macOS fluency; container tooling** (Docker/OrbStack).

### Nice to have

- **ML/LLM ops:** OpenAI-compatible API integration, structured JSON outputs with schema validation, model fallback chains, cost-aware routing. We have a working stack (multi-model registry, defensive env handling, graceful degradation when an agent dies) — extend it, don't rebuild it.
- **FastAPI service development** (existing: `qvc_agent` API, `qvc_ui` debug console with async jobs + model-call traces, `qvc_web` Next.js 15 dashboard).
- **Statistical reasoning about sampling:** shot counts, confidence bounds, sequential testing.
- **SLURM/Kubernetes** or equivalent cluster experience.
- **Competitive programming** background (fast I/O, tight loops, deterministic behavior under time pressure).

### Known constraints (so you can scope honestly)

- Verifier processes are single-threaded by contract (one CPU thread per verifier process) — parallelism is at the process level.
- The builder performs exact type-checks: instrumentation via subclassing corrupts its scheduler (measured: Q 893→900, T 482k→2.48M). Performance work happens in source, with care.
- macOS host today (M-series, 128 GB RAM); cloud burst is your proposal to make.
- Kaggle credentials stay with the account owner: your surface is downloads and local verification, never submission.

### Toolset

- C++20, cmake, perf/Instruments/VTune, flame charts.
- Python 3.11+/3.13, FastAPI, uvicorn, SQLite/Postgres.
- launchd/cron scheduling (existing 6-hour agent cycle), Docker/OrbStack.
- Next.js 15 (existing dashboard), ego-browser for web workflows.
- Kaggle CLI (dataset downloads only).

### Success metrics

- **Week 2:** parallel verifier farm operational (≥4 concurrent full dqi verifications) + candidate ledger live and queryable.
- **Week 4:** end-to-end loop (hypothesis → pre-check → full verify → ledger) **≥5× faster** than baseline; zero lost results across a deliberate crash/restart test.
- **Ongoing:** daily sweep-throughput report; infrastructure never blocks a verified win; every performance claim benchmarked.

### Terms

Freelance sprint contract, remote. Base fee + success bonus tied to final rank (amount in offer). Prize pool: $150,000.

---

## Rolle 4 — Quantum Chemistry & Block-Encoding Expert (FeMoCo / DFTHC)

**Engagement:** 10-week sprint (November 2026 → January 13, 2027), fully remote, freelance/contract. English working language. **Priority: P2 — engage after Roles 1–2 are confirmed** (current ROI is lower than DQI, but the lever is real and unexplored at the factorization level).
**Context:** Google Quantum AI "Verifiable Quantum Circuit Compilation" (Kaggle, $150,000 prize pool). Our team scores **25.30** (rank ~493/2830); Top-10 cutoff ~27.3.

### Mission

Improve our chemistry benchmark — the **DFTHC block encoding of the FeMoCo Hamiltonian** (N = 76 orbitals, η = 113) — at the **factorization level**, where the remaining headroom lives.

Score model: `S = λ_eff · T_tot · Q_tot` with `λ_eff = √(E_gap · (2Λ − E_gap))` (lower is better), under hard verifier-enforced floors `Λ > 49.0 Ha` and `E_gap > 3.914898 Ha`, and a Frobenius error budget `≤ 20 mHa` on the DFTHC factorization.

**Why factorization level:** the compiler side is provably exhausted — our angle-family compiler sits at the ANF-rank lower bound (measured op census: 4,148 CCX = 1,142 cache-init ANDs + 3,006 word-bit product CCX; all 15 public reference circuits independently validated against it; every local alternative compiler measured worse: +12% to +30%). What remains is choosing a *different factorization* — trading Toffolis against `λ_eff` — and reducing qubits in the angle oracles.

### What you will do

- **Own the DFTHC factorization:** explore alternative tensor decompositions (rank structure, sparsity patterns, gauge freedom in the double factorization) and quantify the T↔λ_eff tradeoff exactly, including where the Pareto knee sits relative to our current point.
- **Optimize the boolean angle-oracle circuits** (`Angles_k`, each ≤128 qubits, no `Z_POW` — phases are multiples of π): QROM and multiplexer structure, address-decomposition choices, Toffoli counts per oracle.
- **Improve the Givens-rotation tree** structure where the heuristic cost model allows real gains (the Outer/Inner state-prep unitaries and the Givens rotation itself are black boxes with heuristic Toffoli costs — you reason about their inputs, not their internals).
- **Validate every candidate** against the official verifier: all valid vector addresses simulated with 64 samples, angle words checked, clean workspace, corrected phases forward+reverse, floors enforced.
- **Maintain the chem op census and negative-results memory.** Our standard is high: e.g., "no local alternative compiler beats the 3,006 word-bit-product CCX kernel" is a recorded, measured conclusion with per-circuit validation — your entries must meet the same bar.

### Must have

- **Deep expertise in quantum algorithms for electronic structure:** second quantization, block encodings, QROM design, Givens rotations. You have read and worked from the DFTHC literature (O'Malley et al. lineage: scalable quantum simulation of molecular spectra) and know its cost assumptions cold.
- **Constrained tensor decomposition:** managing a Frobenius error budget (≤20 mHa) against circuit cost; low-rank methods (hierarchical SVD, APT/CP where applicable); gauge freedom in factorizations and how to exploit it.
- **Numerical linear algebra at scale:** NumPy/SciPy/JAX, eigenvalue problems, working directly with fcidump-format two-electron integrals (we hold `FeMoCo76o113e.fcidump` and precomputed shift data).
- **Exact cost accounting:** you count Toffolis and qubits the way an accountant counts money. Heuristic cost models are inputs to your analysis, never the answer.

### Nice to have

- Reversible-circuit implementation experience (you will pair with Role 1 for anything that touches the emitted circuit).
- kickmix/Qualtran familiarity (gate set: reversible classical `X/CX/CCX/SWAP`, diagonal phase `Z/CZ/CCZ/Z_POW/NEG`, measurement-reset `HMR/R`, classical bit ops; per-gate classical control; only `CCX/CCZ/CSWAP` counted as Toffolis).
- FeMoCo or other transition-metal-complex experience.
- C++ for hot numerical loops.
- Having competed in or contributed to this exact competition (strongest signal — tell us what you know that is not public).

### Toolset

- Python 3.11+, NumPy/SciPy/JAX, fcidump data, Qualtran/kickmix, official verifier contract (dedicated environment `.venv-chem`).
- Existing code-only chem generation pipeline and Apache-licensed pool circuits for reference/validation.
- Evidence memory + git, SHA-256-pinned artifacts, bit-exact rebuilds.

### Success metrics

- **Week 3:** validated T↔λ_eff tradeoff map for the current factorization family — where the Pareto knee is, and whether our current point is on it.
- **End of sprint:** best officially verified chem ratio (current: 11.22, at the public frontier — any gain is novel work, not curation).

### Terms

Freelance sprint contract, remote. Base fee + success bonus tied to final rank (amount in offer). Prize pool: $150,000. Full method documentation expected; public author credit offered.

**This posting doubles as a collaboration offer.** If you hold a stronger chem circuit, factorization, or unpublished result from this competition, a merger with shared score may fit better than a contract — say so in your reply.
