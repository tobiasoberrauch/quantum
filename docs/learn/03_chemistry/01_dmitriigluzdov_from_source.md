# Quantum Circuit Compilation from Source

> **Lernziel:** Das komplette DF-THC-SOS-Kostenmodell und wie die FeMoCo-Hamiltonian block-encodiert wird — Faktorisierung (R,B,C), Wort-Tabelle, Angle-Loader, Pi-Gauge, Weight-Refit und Rounding — von der Quelle erklärt.
> **Dauer:** ~12 Minuten lesen
> **Quelle:** Dmitrii Gluzdov (dmitriigluzdov) · 92 votes
> **Technik:** Factorization / Word Table / Loaders / Pi-Gauge / Weight Refit / Rounding (alles — das Fundament-Dokument)
> **Level:** Mittel

---

This notebook assembles circuits for the three benchmarks of the competition and checks each one with the official verifier at its full number of shots. The benchmarks are an inverse-square-root phase for Coulomb interactions in fusion plasmas, a Reed–Solomon decoder for Decoded Quantum Interferometry (DQI), and the angle lookups of a FeMoCo block encoding. All circuits are kickmix circuits — reversible classical gates, phase gates and measurement-based uncomputation — so a classical simulator can check them input by input.

The score is the geometric mean of $\text{cost}_\text{ref}/\text{cost}$ over the three tasks. The costs are defined by the organizers as follows.

| Task | Cost | Reference circuit | This notebook |
|---|---|---|---|
| Inverse square root | Q × (Toffoli + T / 4) | Q 260, 7,735 Toffolis | Q 62, 1,564 Toffoli-equivalents |
| DQI decoder | R(ε₊) × Q² × T | Q 1,893, 5.73 M Toffolis | Q 892, 0.40 M Toffolis |
| FeMoCo lookups | λ_eff × T_total × Q_total | Q 730, 93,237 Toffolis, λ_eff 49.30 | Q 427, 14,966 Toffolis, λ_eff 46.89 |

Q is the qubit count. In the first row T counts T gates, and synthesized rotations are priced in T gates. In the second row T is the mean Toffoli count per shot, and R(ε₊) grows with the decoder's measured failure rate. T_total and Q_total cover the whole block encoding, including the organizers' state-preparation costs. Because the score is a geometric mean, a 1% saving in any task raises it by about 0.33%; what differs between tasks is how much circuit a percent costs. Near 890 qubits one DQI qubit is worth about 0.22% of its cost, while one inverse-square-root qubit near 62 is worth about 1.6%.

Each section below follows the same order: why the subroutine matters, what the circuit computes, where the savings come from, and which approximation is used and how much of the accuracy budget it spends.

> **Code (DE):** Pinnt jede Circuit-Datei per SHA-256, kopiert sie ins Submit-Verzeichnis und fährt den offiziellen Verifikator über alle drei Tasks. Erst wenn alle PASS sind, wird submission.zip geschrieben.

```python

import hashlib, lzma
OWN = next(p.parent for p in INPUT.rglob('femoco_thc_r5.npz'))
OPEN = OWN
FILES = {
    'dfthcsos/angle_k_0.kmb': ('open_circuits_v61/dfthcsos__angle_k_0.kmb', 'd3aab7479fe3b8510e3af3797a14ec8d9bfa226d7aa7717ae4e93f496d2d9538'),
    'dfthcsos/angle_k_1.kmb': ('open_circuits_v61/dfthcsos__angle_k_1.kmb', '4595e5dcc982295db2520c8497219e1768757edf3aa9e706fa44b1716f996ed2'),
    'dfthcsos/angle_k_10.kmb': ('open_circuits_v61/dfthcsos__angle_k_10.kmb', 'f28f2ead2b7eb3d45aadf4e0bb9f9399c7d8f016247d7020ae39dbd9c062cace'),
    'dfthcsos/angle_k_11.kmb': ('open_circuits_v61/dfthcsos__angle_k_11.kmb', '7b9094ddc215c6c7db223fe319e6d2a6f67c1669f412e4d3281c280723df5b81'),
    'dfthcsos/angle_k_12.kmb': ('open_circuits_v61/dfthcsos__angle_k_12.kmb', 'd49dfbfdb8cff3c3d680e4ef65a3d1a01db7a2fc666f49a522d7f58f50305e78'),
    'dfthcsos/angle_k_13.kmb': ('open_circuits_v61/dfthcsos__angle_k_13.kmb', 'cb7e48a7029323a6ec11c0f6dede5f5e0443f67da92e0e6554ff9120b8279efd'),
    'dfthcsos/angle_k_14.kmb': ('open_circuits_v61/dfthcsos__angle_k_14.kmb', '07fcdcb75d3a9e7f2573e057376ec20b7a56bf9a53fe7d7f00fb351614c2003f'),
    'dfthcsos/angle_k_2.kmb': ('open_circuits_v61/dfthcsos__angle_k_2.kmb', '77dec28c5ebffe723fb58717a31c017d66c44cbec220bc3cc5a15a2fff051aa3'),
    'dfthcsos/angle_k_3.kmb': ('open_circuits_v61/dfthcsos__angle_k_3.kmb', '8e137a014a1325450eaf9ec15bc824475b757b3a05bbc542eed9cccfd6b5ec53'),
    'dfthcsos/angle_k_4.kmb': ('open_circuits_v61/dfthcsos__angle_k_4.kmb', 'd9f2a0d739142a1d20789352c617cccc702a8f0b4b17f91971e4e4ef3e6f6c3f'),
    'dfthcsos/angle_k_5.kmb': ('open_circuits_v61/dfthcsos__angle_k_5.kmb', 'bd0886bb6c3d5c04f5e1fd29dbd2562d1c7e5b1a7406bc1abde6819093a0880e'),
    'dfthcsos/angle_k_6.kmb': ('open_circuits_v61/dfthcsos__angle_k_6.kmb', '12c0c6f92d708ff7d852f2c6f36a40ecf4369249fa1f0ab4527b08e0152e7558'),
    'dfthcsos/angle_k_7.kmb': ('open_circuits_v61/dfthcsos__angle_k_7.kmb', '93dc9742392a0dd6e754aebbbea1519014292a56b6908dfce5ae417f2cde73d6'),
    'dfthcsos/angle_k_8.kmb': ('open_circuits_v61/dfthcsos__angle_k_8.kmb', 'd43bd96b88e6ef38c7ea9e697856646af4259889b75d1bc67a94a1768670b5a6'),
    'dfthcsos/angle_k_9.kmb': ('open_circuits_v61/dfthcsos__angle_k_9.kmb', 'a5960a572c39a3996b3919eb8bc18066b8aa78d3fc83bc7435d7e5550de3a2a6'),
    'dfthcsos/submission.npz': ('open_circuits_v61/dfthcsos__submission.npz', 'c421b3231ca3bf953be4990f5dddc9165ef1a47410991f8cb9b2e20e073193de'),
    'dqi.kmb': ('open_circuits_v61/dqi.kmb.xz', '1ab3ac53d442d74410cc753d140fb3008057672d2fcde67b563bfef3808339e5'),
    'invsqrt.kmb': ('open_circuits_v61/invsqrt.kmb', 'af846e54422c303c1c2269d8bd14214868e130269c21303218390de81116e440'),
}
for name, (stored, pin) in FILES.items():
    data = (OPEN / stored).read_bytes()
    if stored.endswith('.xz'):
        data = lzma.decompress(data)
    assert hashlib.sha256(data).hexdigest() == pin, name
    (SUB / name).parent.mkdir(parents=True, exist_ok=True)
    (SUB / name).write_bytes(data)
sys.path.insert(0, str(WORK / 'src'))
import shutil
shutil.copytree(next(OWN.rglob('qcc_pipeline.py')).parent, WORK / 'src', dirs_exist_ok=True)
import qcc_pipeline as P
P.setup(COMP)
RESULTS = P.verify_all(SUB, 'notebook-verification', workers=WORKERS)
assert all(r['status'] == 'PASS' for r in RESULTS.values())
(WORK / 'verification.json').write_text(json.dumps(RESULTS, indent=1, default=str))
P.write_zip(SUB, WORK / 'submission.zip')

```

## 1. Inverse square root

**Role.** Stopping-power simulations of warm dense plasmas evaluate a pairwise Coulomb potential. The quantum subroutine applies the phase $e^{2\pi i/\sqrt{x}}$ to a 22-bit input $x$, and every gate in it is repeated for every particle pair and time step.

**Computation.** Binary shift stages normalize $x$ to a mantissa $M \in [1, 2)$. Their flags give the shift, with $e$ its parity and $s$ half of it:

$$\frac{1}{\sqrt{x}} = 2^{\,s-10}\, y, \qquad y = \frac{2^{(e-1)/2}}{\sqrt{M}} \in (0.5, 1].$$

A lookup addressed by $e$ and the high mantissa bits loads the coefficients of a centered quadratic, and the low bits form an offset whose digits are all $\pm 1$:

$$\delta = \sum_i (2d_i - 1)\, 2^{\,i-22}, \qquad R = K_1 - C_2\,\delta, \qquad y = K_0 - R\,\delta .$$

**Savings.** The circuit used here is Syed Asad Ali's public Apache-2.0 62-qubit circuit ([syed3000](https://www.kaggle.com/code/syed3000/vqcc-own-circuit-portfolio-notebook)), used unchanged. It continues the public line of mrmeows / team selenium, Akmal Xodarev (busyaprime) and yoyobar (an 8-bit semi-log table, degree-2 Horner evaluation and a two-pass phase with 41 rotations). Its savings, as described by its author, are the following.
- Because every digit is $\pm 1$, each Horner row is a plain addition or subtraction rather than a controlled multiplication.
- **Deferred fan-in lookup.** The coefficients are decoded with algebraic three-product decodes, 169 AND gates in all.
- **Measurement-based uncomputation of carries.** The carries of the pre- and post-low addition and subtraction, of the Q rows and of the high R un-ripple are erased by X-basis measurement and a conditional CZ instead of reverse ripples, as in Gidney's temporary logical-AND.
- **Carry-save merges** in the reverse decoders and R rows, ancilla-free top-of-ripple steps (T gates count a quarter of a Toffoli), and pruning of helper wires.
- **Exact window resynthesis.** Every small window of the compiled circuit, up to 12 wires, is re-synthesized from its exact truth table including phases with the fewest products; seven windows go from three Toffolis to two.
- **Measurement clean-up.** Two X-basis measurements act on a qubit that is provably $|0\rangle$, so their outcomes carry no phase and every fix-up they condition is removed; the mean T count falls from 20.5 to 14.5.
- **Proven rewrites.** A phase gadget that fires on half of the shots is quadratic and is applied with two-qubit gates; a fix-up chain that acts on 3 of the 3,133,452 legal inputs is replaced by a smaller equivalent block; four products feeding one target form a rank-2 quadratic and take two Toffolis; products computed shortly after are reused; the clean-up of the shift register becomes a thermometer code erased top-down by measurement; the conditioned T blocks are rebuilt in their measured branch; and a product held on a measured wire forms the control of a controlled swap with two CNOTs.
- **Shorter clean-up and shift networks.** Holding the class bits in idle qubits removes two clean-up cascades and the flush of the low pass; the normalizing and unnormalizing shift networks shrink from 52 to 47 and from 52 to 48 controlled swaps; and one cascade after the high pass is removed by reusing a controlled swap that runs anyway. The mean Toffoli count falls from 1,281.5 to 1,268.8.
- Every rewrite is proven exact on all 3,133,452 legal inputs and all measurement outcomes. A shot costs 1,563.8 Toffoli-equivalents on 62 qubits (cost 96,958).

**Approximation.** The quadratic coefficients use short precisions fitted on the reachable inputs, and the rotation angles are calibrated over the whole domain so that the phase error stays within the verifier's tolerance. The verifier tests every legal input 64 times.

## 2. DQI decoder

**Role.** Decoded Quantum Interferometry turns an optimization problem over a finite field into the decoding of a Reed–Solomon code. Its dominant cost is a reversible decoder that runs in superposition.

**Computation.** Seventy 12-bit registers hold the syndromes $S_i = \sum_j e_j \alpha^{(i+1)j}$ of an unknown error vector $e$ over GF($2^{12}$) with at most 35 nonzero entries among 4,095 positions. Beside them sit 4,095 classical words $M_j$. The circuit multiplies the phase by $(-1)^{\sum_j |e_j \wedge M_j|}$, returns the syndromes and leaves every other qubit clean: it decodes $e$ in superposition, applies the phase and undoes the decoding. The locator $\sigma$ and evaluator $\Omega$ solve

$$S(z)\,\sigma(z) \equiv \Omega(z) \pmod{z^{70}}.$$

The circuit used here is Syed Asad Ali's public Apache-2.0 892-qubit decoder of the C1 line ([syed3000](https://www.kaggle.com/code/syed3000/vqcc-own-circuit-portfolio-notebook)), built with GPT-6 Astra on the SomeJoint team's kit, used unchanged. Its main ideas, as described by its author, are the following.

**Savings.**
- The syndrome words are transformed in place, so the decoder needs only 52 qubits beyond its 840 input qubits.
- **Retained-head chain.** The continued-fraction extraction keeps each head on its wires instead of recomputing it, and a block-Wronskian identity telescopes the prefix of the chain so that several steps are taken at once.
- **Narrow return.** The undoing of the extraction runs as a single reverse pass per node (the SomeJoint team's design).
- **Flag carry.** Pole flags, needed wherever a denominator can vanish, are measured in the X basis on the way forward, rebuilt on the way back as the AND of the flag condition and a zero test, and their phase is repaid with a controlled-Z (idea of Ali Haydar Özdağ, from the SomeJoint team's 892-qubit line). This takes the width from 902 to 891 qubits.
- **Measurement-based erasure.** Recompute steps and flag uncomputes are erased by measurement instead of reverse circuits, and AND ladders are made conditionally clean (Khattar and Gidney, 2024).
- **Exact product caching.** Repeated products are kept on wires proven idle and reused with CNOTs.
- **One-qubit trade.** An 892nd qubit lets the conversion and the reverse stages use wider exact variants, which saves about 1,070 Toffolis for a qubit worth about 890 at this size. The last node's pole flag is measured on the way forward and recomputed at the start of the reverse, each scan position's test runs only when its classical mask is nonzero, and one extraction node runs as a retained chain without a pole flag.
- The locator and evaluator then give the error values, a scan applies each position's phase where the locator vanishes, and the whole computation is undone. A shot uses 395,394 Toffolis on average (at most 395,679), about 7% of the reference decoder.

**Approximation.** Rare degenerate pivot patterns, rare chance events such as an accidental zero in a 24-bit test, and the pole of one extraction node, which fires only on error weights of 5 or less, are not handled exactly. In six independent draws of 102,400 shots from the competition distribution they caused no value or phase failures. The verifier prices failures through $R(\varepsilon_+)$, a Clopper–Pearson bound at confidence $1 - 2^{-128}$; with no failures $R = 1.191$.

## 3. FeMoCo angle lookups

**Role.** FeMoCo is the active site of nitrogenase. Its block encoding is the core of a quantum chemistry algorithm for nitrogen fixation. The lookup circuits stream the 75 Givens-rotation angles of every factor vector into word registers.

**Factorization.** The two-body tensor is written with eight groups of 143 unit vectors and rank 44, $(R, B, C) = (8, 143, 44)$, which gives 76 + 8 × 143 = 1,220 lookup addresses, and every angle is stored with **8 bits**. The short words are the main lever: the organizers' state-preparation cost model sizes its temporary workspace by the word width, so for $B \ge 129$ the whole block encoding needs 427 qubits instead of about 740, and with $143 = 9 \cdot 16 - 1$ vectors a group fills exactly nine 16-way blocks of the inner state preparation; one column fewer saves about 78 Toffolis per step, because the column count enters only the weights. The table used here is Syed Asad Ali's ([syed3000](https://www.kaggle.com/code/syed3000/vqcc-own-circuit-portfolio-notebook)), used unchanged with its words, weights and circuits. It was obtained by his own continuous fit, a float64 L-BFGS with a sign-mixing penalty started from an 8 × 48 basin with columns merged down, on marculera's DF-THC compact-group pipeline ([DF-THC 10x](https://www.kaggle.com/code/marculera/df-thc-10x-compact-groups-from-the-hamiltonian)) and Ahmed Berat Özer's progressive rounding ([Özer](https://www.kaggle.com/code/ahmedberatozer/quantum-ai-df-thc-group-compression)). The angles are rounded to 8 bits by lattice-aware, Babai-style nearest-plane rounding with lazy code commitment and a sign-mixing penalty, frozen in an order set by conditional curvature, with refits between the stages.

**Refit.** With every angle word fixed, the weights are refit, in a long run with tight gate margins, so that both error measures sit at the 20 mHa limit, with exact zero weights and column-gauge rotations, which spends the whole error budget on the normalization: $\lambda_\text{eff} = 46.893$ (refitting the weights up to the error gate was first shown publicly by heliosli ([notebook](https://www.kaggle.com/code/heliosli/the-dataset-is-public-now-enjoy))).

**Circuits.** Circuit $k$ loads into five 8-bit word registers the words of batch $k$ as a function of the 11-bit address. Address monomials are cached, and mixed terms are covered two per Toffoli by a GF(2) decomposition: one Toffoli computes the AND of two XOR combinations, $(h_1+l_2)(h_2+l_1) = h_1l_1 + h_2l_2 + h_1h_2 + l_1l_2$, and the extra terms are corrected from the caches; the work registers are erased by measurement (marculera's tensor compiler, after the emitter design of mrmeows). Syed Asad Ali's loader compiler, used here, adds the following.
- **Product selection.** Overlapping products are chosen by an exact linear-matroid-parity pairing, with at most four cached products alive at a time and no recomputation, and the lowest bit of the coded words is carried by the code.
- **Carried helpers.** Adding π to an angle of the Givens tree negates its sine and cosine; when every root-to-leaf path collects the same parity, each molecular vector changes only by a global sign, so the two-body tensor is unchanged (physical π gauge, after Atakan Aldemir ([QCC notebook](https://www.kaggle.com/code/atakanaldemir/qcc-gap-3-residue-repair-and-c43-native-compiler))). A commuting reorder of the Givens tree together with the exact π gauge of each address in bit 7 carries five low-address helper products from one batch to the next.
- **Five-block coded plans.** The coded loaders are planned with five blocks of three low address coordinates. Because the carried helpers keep every low monomial live in one window, every pair of blocks is a valid product pair, so the pairing is perfect; each coded loader drops from 202 to 195 products.
- **Don't-care absorption.** Only 1,220 of the 2,048 addresses are used, and table rows are completed on unused addresses where that frees a relation, while every used entry stays exactly as it was. The planner variants were found by an evolutionary search scored by the exact verifier.
- The coded batches cost 270 to 274 Toffolis and the uncoded 291 to 297, so a pass costs 4,152 Toffolis, and one step of the block encoding costs 14,966 Toffolis, 8,304 of them for the two lookup passes. The qubit count is set by the inner state preparation; the lookups fit inside its workspace. The verifier checks every circuit on all 1,220 addresses, 64 times each.

**Approximation.** The factorization spends the two-body budget fully: error_1 is 19.99999 mHa and error_2 is 19.99999 mHa against their 20 mHa limit, and $E_\text{gap} = 3.9149$ Ha lies inside its admissible domain.

## 4. Results

All values come from the official verifiers at full shot counts in this run. The decoder's failure count and the mean Toffoli counts depend slightly on the verification seed.

```python

r = RESULTS
rows = [
    ('Inverse square root', r['invsqrt']['num_qubits'], f"{r['invsqrt']['toffoli_count']:,.0f}",
     f"C = {r['invsqrt']['toffoli_equivalent']:,.0f} ({r['invsqrt']['rotation_count']:.0f} rotations)", 'invsqrt'),
    ('DQI decoder', r['dqi']['num_qubits'], f"{r['dqi']['toffoli_count']:,.0f}",
     f"R = {r['dqi']['repetition_factor']:.3f} ({r['dqi']['value_errors'] + r['dqi']['phase_errors']} failed of {r['dqi']['verified_shots']:,})", 'dqi'),
    ('FeMoCo lookups', r['dfthcsos']['num_qubits'], f"{r['dfthcsos']['toffoli_count']:,.0f}",
     f"λ_eff = {r['dfthcsos']['lambda_eff']:.2f}", 'dfthcsos'),
]
table = pd.DataFrame([{'Task': name, 'Qubits': q, 'Toffoli': t, 'Other': other,
                       'Cost': f"{r[k]['score']:.4g}", 'Reference cost': f'{REFERENCE[k]:.4g}',
                       'Reference / cost': f"{REFERENCE[k] / r[k]['score']:.2f}"} for name, q, t, other, k in rows])
score = math.prod(REFERENCE[k] / r[k]['score'] for k in REFERENCE) ** (1 / 3)
display(table.style.hide(axis='index'))
print(f'Score (geometric mean of reference / cost): {score:.3f}')

```

## Sources and reproducibility

The notebook runs on a CPU with the competition data and the attached dataset. All circuits, the chemistry table and its weights are Syed Asad Ali's public Apache-2.0 files ([dataset](https://www.kaggle.com/datasets/syed3000/vqcc-own-circuit-portfolio)), used unchanged. All are stored in the dataset folder `open_circuits_v61/` with their licence and credits and checked against SHA-256 values written in the code cell; the decoder file is stored xz-compressed. The code cell writes `submission.zip` only after all three official verifiers pass.

- Organizers: task definitions, verifiers, kickmix and the log-depth Givens tree ([competition](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation), [arXiv:2610.23832](https://arxiv.org/abs/2610.23832)).
- Inverse square root: **Syed Asad Ali (syed3000)**'s 62-qubit circuit ([VQCC Own-Circuit Portfolio](https://www.kaggle.com/code/syed3000/vqcc-own-circuit-portfolio-notebook)): deferred fan-in lookup, measured carry uncomputation, carry-save merges, exact window resynthesis, measurement clean-up and proven rewrites, verified with manwithacat's kickmix engine; on the public line of mrmeows / team selenium, Akmal Xodarev (busyaprime) and yoyobar ([62-qubit circuit](https://www.kaggle.com/code/yoyobar/lb-22-99-invsqrt-101-62-qubits)). Earlier links: **Ehan Mallick**'s 62-qubit circuit with two 3-to-2 AND merges, on [yoyobar](https://www.kaggle.com/code/yoyobar/lb-22-99-invsqrt-101-62-qubits)'s 62-qubit circuit with four nonlinear-cone rewrites (with GPT-6 Astra), which includes the cached swap condition of [Ahmed Berat Özer](https://www.kaggle.com/code/ahmedberatozer/quantum-ai-df-thc-group-compression) distributed through [James Barlow (manwithacat)](https://www.kaggle.com/code/manwithacat/vqcc-quantum-voodoo); the 63-qubit starting point with the re-synthesized main lookup and product window by [Akmal Xodarev (busyaprime)](https://www.kaggle.com/datasets/busyaprime/33-qcc-v8-members), based on [mrmeows / team selenium](https://www.kaggle.com/datasets/mrmeows/qcc-1375-open-circuits); on the earlier public line of busyaprime (78 qubits), Phuc Thai (EXP-222/226a), this notebook's earlier 84-qubit construction and marsyas (fused phase stage), which in turn builds on Sumit Chongder, Rudra Bhaskar, Artem1410, kozykappa, Zongao Bian, lightningv08 and Mizero Lucky Gall.
- DQI: **Syed Asad Ali (syed3000)**'s 892-qubit C1 decoder, built with GPT-6 Astra on the SomeJoint team's kit, with the SomeJoint team's narrow return, the flag carry of **Ali Haydar Özdağ**, measurement-based erasure, conditionally clean AND ladders after Khattar and Gidney (2024), exact product caching and a one-qubit trade. Earlier links of the line: the **SomeJoint team's (Agniv Banerjee)** 892-qubit decoder ([Quantum Circuits 23.85, 892-qubit DQI](https://www.kaggle.com/code/somejoint/quantum-circuits-23-85-local-gm-892-qubit-dqi), [dataset](https://www.kaggle.com/datasets/somejoint/qcc-dqi-892-q26)) with the carried pole flags of **Ali Haydar Özdağ** ([reproducible circuit portfolio](https://www.kaggle.com/code/ahoirg/score-23-64254-reproducible-circuit-portfolio)) and contributions of yoyobar, GPT-6 Astra Pro, Alex Chilton, jday96314, mrmeows and manwithacat; on the SomeJoint line of the [889-qubit two-halves decoder](https://www.kaggle.com/code/somejoint/quantum-circuits-23-17-local-gm-889-qubit-dqi) (front half and conversion pair by GPT-6 Astra Pro) and the [897-qubit decoder](https://www.kaggle.com/code/somejoint/quantum-circuits-22-75-local-gm-897-qubit-dqi) with GPT-6 Astra Pro's homogeneous chains and 658-Toffoli jet; the narrowing of [Ahmed Berat Özer](https://www.kaggle.com/code/ahmedberatozer/quantum-ai-df-thc-group-compression)'s version 9; Alex Chilton's 883-qubit Schur decoder, based on jday96314's decoder; the mask projection of mrmeows and Ahmed Berat Özer after manwithacat's classical-mask projection; and earlier links: this notebook's round-12 decoder, Agniv Banerjee's Bézout–Hankel phase solve, ViberTeam and Phuc Thai (DePie), going back to the reversible decoder of A. Gu et al., [arXiv:2610.22367](https://arxiv.org/abs/2610.22367).
- FeMoCo: **Syed Asad Ali (syed3000)**'s $(8, 143, 44)$ table, lattice-aware rounding, weight refit and loader compiler (matroid-parity pairing, carried helpers, five-block coded plans), with the π gauge after Atakan Aldemir; refitting the weights up to the gate first shown by heliosli. It builds on the $(8, 143, 45)$ compact-group factorization, its seed construction, rounding and coded bits, and the tensor lookup compiler by **marculera (Lera)** ([DF-THC 10x: Compact Groups From the Hamiltonian](https://www.kaggle.com/code/marculera/df-thc-10x-compact-groups-from-the-hamiltonian), [dataset](https://www.kaggle.com/datasets/marculera/dfthc-compact-pipeline)), whose pipeline credits Ahmed Berat Özer (D(w) penalty, staged group dropping, quantization order), kozykappa with Kozykorpesh and Sumit Chongder (banked lookup, signed gauge), kozykappa and Artem1410 (anazemcev) (copy-column gauge, effective-norm refinement), Phuc Thai (paired combine, refit after rounding, word-level coordinate descent, per-group copy gauge after haideptry), the SomeJoint team (640-vector dictionary, coded low bit), mrmeows (lookup emitter design), lightningv08 (five words per circuit), Michael Rustad (the $B \ge 129$ cliff at 8 bits, L-BFGS refits of merged groups), and k256net and Dmitrii Gluzdov (the public 10-bit factorization); the kernel-relation search after matousakura and James Barlow (manwithacat), Dmitrii Gluzdov and qwertykeypadapple; after the exact coefficient gauge of [kirilltym](https://www.kaggle.com/code/kirilltym/quantum-circuits-exact-gauge-5-word-qrom) and earlier gauge studies by kozykappa, Phuc Thai, anazemcev, Alex Chilton and avazaku.
- C. Gidney, [Halving the cost of quantum addition](https://quantum-journal.org/papers/q-2018-06-18-74/) (2018); G. H. Low et al., [PRX 15, 041016](https://journals.aps.org/prx/abstract/10.1103/pb2g-j9cw) (2025).

All reused circuits and code are Apache 2.0; this notebook and its dataset are released under Apache 2.0.

> **Code (DE):** Schreibt das finale submission.zip (nachdem der Verifikator oben alle drei Tasks bestätigt hat).

```python

P.write_zip(SUB, WORK / 'submission.zip')

```

---

## 🔑 Kern-Konzept in 3 Sätzen

Die FeMoCo-Hamiltonian wird über DF-THC in eine Summe aus R Gruppen × B Vektoren × Rang C zerlegt; jede Gruppe liefert einen Block der Block-Encoding, und die Gesamtkosten sind λ_eff × T × Q. Die eigentliche Arbeit steckt im Laden der 75 Givens-Winkel pro Faktorvektor: eine kompakte Wort-Tabelle (aktuell 8×143×44 mit 8-Bit-Wörtern) plus 15 Lookup-Circuits (Loader), deren Toffoli-Anzahl T dominiert. λ_eff ist die effektive Spektralnorm der Encoding-Matrix — man minimiert sie durch Weight-Refit und Pi-Gauge, während beide Fehlermaße exakt an der 20-mHa-Schwelle gehalten werden.

## 📐 Die Zahlen die zählen

| Parameter | Wert | Bedeutung |
|-----------|------|-----------|
| (R,B,C) | 8 × 143 × 44 | Gruppen × Vektoren/Gruppe × Rang → 76 + 8·143 = 1,220 Lookup-Adressen |
| Wort-Breite (brot) | 8 Bit | Bits pro Winkel-Wort; bei B ≥ 129 → nur 427 Qubits (statt ~740) |
| Q (FeMoCo) | 427 | Qubit-Zahl der ganzen Block-Encoding |
| T_total | 14,966 | Toffolis pro Step (8,304 davon für zwei Lookup-Pässe) |
| λ_eff | 46.893 | effektive Spektralnorm (Reference 49.30) |
| error₁ / error₂ | 19.99999 / 19.99999 mHa | beide exakt an der 20-mHa-Grenze |
| E_gap | 3.9149 Ha | Sum-of-Squares-Gap, muss ≥ 3.914898 Ha |
| Loader-Cost | 270–274 (coded) / 291–297 (uncoded) | Toffolis pro Batch; ein Pass = 4,152 |
| Reference | Q 730, 93,237 Toffolis, λ_eff 49.30 | Organisatoren-Baseline |
| Score | geometrisches Mittel von ref/cost über 3 Tasks | 1% Ersparnis ≈ +0.33% Score |

## 📝 Lern-Notizen (füll das selbst aus)

- [ ] DF-THC Factorization verstanden: ...
- [ ] (R,B,C) Tabelle nachvollziehbar: ...
- [ ] Loader-Kosten verstanden: ...
- [ ] λ_eff und was es physikalisch bedeutet: ...
- [ ] Verbindung zu invsqrt/DQI: ...
- [ ] Frage die ich noch habe: ...
