# VQCC Hedge Wizardry

> **Lernziel:** Wie man DQI-Decoder schrittweise mit *kleinen, verifizierten* Tweaks verbessert — measurement-based Uncomputation (MBU), release-and-recompute, Site-Census-Ports und das Verbinden zweier byte-identischer Circuit-Abschnitte — und wie man DQI-Gewinne über **48 fixe Draws** statt über einen glücklichen Draw bewertet.
> **Dauer:** ~25 Minuten lesen
> **Quelle:** manwithacat (James Barlow) | 52 votes (V23; diese Datei ist V26/HW-24)
> **Technik:** Readout (MBU) + Qubit Floor + Product Caching
> **Level:** Fortgeschritten

---

**What this is.** An ongoing public collection of *small* verified tweaks to circuits for the [verifiable quantum circuit compilation competition](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation). A tweak lands here when it passes the local unmodified verifier and its expected gain is below +0.5% of the overall score. These gains are released straight away: the circuit in the [VQCC Hedge Wizardry dataset](https://www.kaggle.com/datasets/manwithacat/vqcc-hedge-wizardry), the explanation here. The notebook then runs the verifier on Kaggle.

**How releases work.** Each new version of this notebook opens with what is new in it: the entry, the gain, and the technique it demonstrates, explained in full. Earlier entries are then summarised in a few lines each, with a link to the notebook version where they were the headline, for the full detail. A techniques index lists every technique shown so far. The [version history](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/versions) of this notebook and the dataset is the dated record.

Each entry is:

- **explained**: what changed and why it pays, written for someone new to the task;
- **verified**: the unchanged official verifier passes the circuit, on Kaggle, in the cells at the end. For DQI the gain is also judged on its expected cost over 48 fixed random draws, never on one lucky draw;
- **credited**: most tweaks are made on someone else's public circuit, and that author is named first, with the licence kept.

**It is also a working submission notebook.** The hidden cells at the end take the cheapest public circuit for each task from our [VQCC public circuits dataset](https://www.kaggle.com/datasets/manwithacat/vqcc-apache-public-circuits). Where an entry is cheaper for its task, they swap it in, check every file's SHA-256, run the unchanged official verifiers and write `submission.zip` with a receipt.

**How to read it.** The code is hidden; click a cell to see it. Numbers carry the evidence tier they were measured at, and a number is never shown at a higher tier than that:

- *static model*: arithmetic on the official cost formula;
- *local prescreen*: our re-implementation of the official evaluator's functions, used inside a search;
- *local engine*: our fast re-implementation of the simulator, cross-checked against the official verifier;
- *local official verifier*: the unmodified competition verifier on a local build of kickmix (*re-verified by us* when the circuit is someone else's published one);
- *official verifier (Kaggle)*: the same verifier run by this notebook on Kaggle.

Bigger changes, and the release-and-recompute method, are explained in [Quantum Voodoo](https://www.kaggle.com/code/manwithacat/vqcc-quantum-voodoo).

```python
# Code-Zelle: DQI-Ranking-Logik. Ein DQI-Cost bei einem Salt ist EIN Draw der gesampelten Fehlschläge
# (1-2 Phase-Errors bewegen R von 1.19126 auf 1.19673 / 1.20139). Deshalb rankt DQI nach
# dqi_expected_cost (Mittel über einen 48-Draw-Sweep), sonst dqi_zero_failure_cost (R-Floor x Q^2 x mean Toffolis).
# Tie-Regel: eine byte-verschiedene Kopie ändert den Verifier-Draw und kann per Rauschen hauchbilliger
# aussehen — sie darf den Original-Designer nicht verdrängen (REL_TIE = 1e-5).
def rank_cost(r):
    keys = ("dqi_expected_cost", "dqi_zero_failure_cost", "local_task_score") if r.get("task") == "dqi" \
        else ("local_task_score",)
    for k in keys:
        try:
            v = float(r.get(k) or "nan")
        except ValueError:
            continue
        if v == v:
            return v
    return None

def rank_basis(r):
    if r.get("task") != "dqi":
        return "default salt"
    return ("expected (48 draws)" if r.get("dqi_expected_cost") else
            "zero-failure" if r.get("dqi_zero_failure_cost") else "default salt")

import datetime as _dt
REL_TIE = 1e-5

def public_when(r):
    for k in ("public_since", "first_known", "release_date"):
        s = (r.get(k) or "").strip()
        if not s:
            continue
        try:
            d = _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            continue
        return d.replace(tzinfo=_dt.timezone.utc) if d.tzinfo is None else d.astimezone(_dt.timezone.utc)
    return None

def rank_order(rows):
    scored = [(rank_cost(r), r) for r in rows]
    scored = [(c, r) for c, r in scored if c is not None]
    if not scored:
        return []
    limit = min(c for c, _ in scored) * (1 + REL_TIE)
    far = _dt.datetime.max.replace(tzinfo=_dt.timezone.utc)
    def tie_key(cr):
        w = public_when(cr[1])
        return (w is None, w or far, cr[0], cr[1].get("sha256") or cr[1].get("sha12") or "")
    by_time = sorted(scored, key=tie_key)
    pick = by_time[0]
    for cr in by_time[1:]:
        if pick[0] > cr[0] * (1 + REL_TIE):
            pick = cr
    tied = [pick] + [cr for cr in by_time if cr is not pick and cr[0] <= limit]
    rest = sorted((cr for cr in scored if cr[0] > limit),
                  key=lambda cr: (cr[0], cr[1].get("sha256") or cr[1].get("sha12") or ""))
    return [r for _, r in tied + rest]

def pick_best(rows_for_task):
    order = rank_order(rows_for_task)
    return order[0] if order else None
```

---

# DQI-Einträge (alle HWs, die DQI betreffen)

## HW-22 (2026-11-05, dqi): two public 891-qubit DQI decoders joined where they are byte-identical

The unsynthesis section of busyaprime's public DQI decoder `fd0ef09efd45` joined to the rest of the current public pick `1c43b7ff2fcf` (Alex Chilton's version, released by Leo Tang), at a stretch where the two are byte-identical: 14 fewer static Toffolis, same 891 qubits, all 48 draws PASS; 48-draw expected cost -0.0035% (about +0.0012% overall by static arithmetic). Local unmodified verifier PASS at the default salt.

- **Technique:** Joining two public circuits where they are byte-identical.
- **Credit:** Unsynthesis section from `fd0ef09efd45` by **Akmal Xodarev (busyaprime)** ([33 QCC V8 members](https://www.kaggle.com/datasets/busyaprime/33-qcc-v8-members) v10, Apache-2.0), their exact rewrite of **Syed Asad Ali**'s 891-qubit decoder `fc3ba81614e1`. Everything else, including the unextract section, from `1c43b7ff2fcf`: **Alex Chilton**'s decoder version, released by **Leo Tang** in [VQCC T7421 Submission](https://www.kaggle.com/code/leotang09/vqcc-t7421-submission) v17 (Apache-2.0), on the public 891-qubit decoder line (Syed Asad Ali, Agniv Banerjee and others, as credited there). The join of the two public circuits and its verification are by manwithacat (James Barlow), assisted by Claude (Anthropic).
- **Status (2026-11-05):** Released 2026-11-05 in dataset v23 / notebook v24; hosted entry gate PASS in notebook v24.
- **Full detail:** [Version 24](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/version/24) of this notebook.

## HW-09 (2026-11-02, dqi): conditionally clean S12/S6 flag computations on busyaprime's public DQI

Twelve 12-input AND computations and twelve 6-input AND computations in busyaprime's public decoder are replaced with our exhaustively checked conditionally clean templates. All 24 sites have proved clean-wire obligations. Same 892 qubits; -293.998 mean Toffolis per shot; -0.07351% DQI expected cost on 48 shared draws, cheaper on every draw with identical errors. Expected portfolio GM 23.90474283 to 23.91060278 (+0.02451%, arithmetic). Unmodified local official verifier PASS; hosted official verifier PASS in notebook v10, exact cost match.

- **Technique:** Conditionally clean flag computation with measurement-based cleanup.
- **Credit:** Base by **Akmal Xodarev (Busya PRIME)**: [33 QCC V8 members](https://www.kaggle.com/datasets/busyaprime/33-qcc-v8-members) v9, from [Exact DQI Rewrites](https://www.kaggle.com/code/busyaprime/23-910-local-gm-exact-dqi-rewrites-892-qubits) v15, Apache-2.0. The core decoder is **SomeJoint (Agniv Banerjee)**'s q26 892-qubit design; busyaprime adds exact product caching, credits **Ahmed Berat Özer** for that idea, and incorporates our HW-07 ladder. Our S12/S6 templates were developed in the earlier local relay, following **Khattar and Gidney**'s conditionally clean ancilla method; this port and verification are by **manwithacat (James Barlow), assisted by Codex (OpenAI)**.
- **Status (2026-11-05):** Published in Hedge dataset v9 and notebook v10; hosted official verifier PASS, exact cost match. Version 9 artifacts omitted HW-09 through a stale dataset attachment; v10 explicitly pinned dataset v9 and required the headline SHA before verification. Hosted ZIP SHA-256 cff190d21377b7ec425a1baac2ac68f971e180eb66f735dd95fb5e672d041ad7. No competition submission.
- **Full detail:** [Version 10](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/version/10) of this notebook.

## HW-08 (2026-11-01, dqi): measurement-based uncomputation for the 12 three-input flag ANDs and the 12 six-input normalize flags, ported to SomeJoint's 892-qubit DQI

SomeJoint's (Agniv Banerjee) newer public 892-qubit DQI decoder `b7ca9bce749d` overtook HW-07 on the public frontier. It still clears its 12 three-input flag ANDs and 12 six-input normalize flags by re-running borrowed-wire Toffoli chains, so we carried both HW-06's and HW-07's measurement-based uncomputation onto it. Our census tool found all 24 sites in about a minute. Result `5e86f69a9611`: same 892 qubits, −207.01 mean Toffolis per shot, −0.0514% DQI cost over 48 fixed draws, cheaper on every draw, with the same 7 failing shots (local engine); about +0.017% expected overall score. Local official verifier PASS at the default salt. **Published as a reference record:** before release, busyaprime's public exact product caching on the same SomeJoint base (`3779a3431e9c`) overtook it by 0.60% on the same 48 draws; that circuit already clears the HW-06-class sites by measurement-based uncomputation, and our census no longer finds the HW-07-class sites there. The value of this entry is the worked port: what the circuit does, which sites changed, and the steps taken.

- **Technique:** Porting a tweak to a new base by site census.
- **Credit:** base circuit `b7ca9bce749d` by **SomeJoint (Agniv Banerjee)** ([notebook](https://www.kaggle.com/code/somejoint/quantum-circuits-23-85-local-gm-892-qubit-dqi) v26, Apache-2.0): GPT-6 Astra Pro's q26 decoder round, with Claude putting SomeJoint's flag carry, which follows **Ali Haydar Özdağ**'s, on it; the flag carry is as in `bdee18489fac` (**yoyobar**'s one-carry history). Change: HW-06's and HW-07's measurement-based uncomputation at 24 sites, found by our census tool, by manwithacat.
- **Status (2026-11-05):** Headline of Version 8, published as a reference record. Overtaken before release by busyaprime's public exact product caching on the same SomeJoint base, `3779a3431e9c` (48-draw mean 379,530,489,015; -0.60% against HW-08 on the same draws), which also clears the HW-06-class sites (12 self-uncompute Toffolis) by measurement-based uncomputation; our census finds the HW-07-class sites no longer present there. Local official verifier PASS at the default salt; the entry gate in this version is its first hosted run.
- **Full detail:** [Version 8](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/version/8) of this notebook.

## HW-07 (2026-11-01, dqi): measurement-based uncomputation with a two-wire ladder for the 12 six-input normalize flags in yoyobar's 892-qubit DQI

On our HW-06 circuit (yoyobar's public 892-qubit DQI `6d58bd6d0232` with 12 flag ANDs made measurement-based), we clear the six-input pivot flag of each epoch's normalize step by measurement-based uncomputation instead of a 16-Toffoli chain on borrowed wires. When the measurement gives 1, the phase fix rebuilds the six-input AND on a ladder of two clean wires, about 2.25 Toffolis expected per site. Result `1779b4e5967f`: same 892 qubits, −164.95 mean Toffolis per shot, −0.0409% DQI cost over 48 fixed draws against HW-06 and −0.0513% against `6d58bd6d0232`, with the same 7 failing shots (local engine); about +0.014% expected overall score against HW-06 (+0.017% against `6d58bd6d0232`). Local official verifier PASS at the default salt.

- **Technique:** Measurement-based uncomputation of a multi-input AND with a clean-wire ladder.
- **Credit:** base circuit `c253111974fc`, our HW-06, on **yoyobar**'s `6d58bd6d0232` (with GPT-6 Astra; [notebook](https://www.kaggle.com/code/yoyobar/lb-22-99-invsqrt-101-62-qubits) v11, Apache-2.0), the infinity-lead product reuse on **SomeJoint (Agniv Banerjee)**'s 892-qubit flag-carry circuit `bdee18489fac` ([notebook](https://www.kaggle.com/code/somejoint/quantum-circuits-23-77-local-gm-892-qubit-dqi) v25, Apache-2.0), whose flag carry follows **Ali Haydar Özdağ**'s flag carry. Reading Ali Haydar Özdağ's (ahoirg) public reproducible rebuild of SomeJoint's decoder sources ([notebook](https://www.kaggle.com/code/ahoirg/score-23-64254-reproducible-circuit-portfolio) v1) explained the normalize step's wires. Change: the two-wire measurement-based uncomputation of the 12 six-input flags, by manwithacat.
- **Status (2026-11-05):** Published on 2026-11-01: the notebook was pushed twice with identical content, as Versions 6 and 7 (a duplicate push), so Version 7 is its headline. Hosted official verifier PASS at the default salt in Version 6 (384,137,374,413.52, equal to `entries.csv`). Overtaken on the public frontier the same day by SomeJoint's (Agniv Banerjee) `b7ca9bce749d`: 48-draw mean cost 382,020,234,789.40 against HW-07's 382,637,339,169.98 (local engine, same draws). HW-08 carries HW-06's and HW-07's techniques onto `b7ca9bce749d`.
- **Full detail:** [Version 7](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/version/7) of this notebook.

## HW-06 (2026-11-01, dqi): measurement-based uncomputation for the 12 borrowed-wire flag ANDs in yoyobar's 892-qubit DQI

On yoyobar's public 892-qubit DQI circuit `6d58bd6d0232` (on SomeJoint's flag carry), our measurement-based uncomputation replaces 12 four-Toffoli uncomputes that borrowed an in-use wire. Result `c253111974fc`: same 892 qubits, −42.0 mean Toffolis per shot, −0.0104% DQI cost over 48 fixed draws with the same 7 failing shots (local engine), about +0.0035% expected overall score. Local official verifier PASS at the default salt.

- **Technique:** Measurement-based uncomputation of a borrowed-wire AND; Sound value tracking for provably-zero targets.
- **Credit:** base circuit `6d58bd6d0232` by **yoyobar** (with GPT-6 Astra; [notebook](https://www.kaggle.com/code/yoyobar/lb-22-99-invsqrt-101-62-qubits) v11, Apache-2.0), the infinity-lead product reuse on **SomeJoint (Agniv Banerjee)**'s 892-qubit flag-carry circuit `bdee18489fac` ([notebook](https://www.kaggle.com/code/somejoint/quantum-circuits-23-77-local-gm-892-qubit-dqi) v25, Apache-2.0), whose flag carry follows **Ali Haydar Özdağ**'s flag carry. Change: measurement-based uncomputation at the 12 borrowed-wire flag ANDs, and the value tracker that found them, by manwithacat.
- **Status (2026-11-05):** Published on 2026-11-01 as the headline of Version 5; its hosted run of the unchanged official verifier on Kaggle passed (cost 382,537,501,561.76, 0 errors, equal to `entries.csv`), and it was that version's DQI pick. Superseded for DQI by HW-07 (`1779b4e5967f`), which builds on it: −0.0409% DQI cost over the same 48 draws (local engine).
- **Full detail:** [Version 5](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/versions) (open the version list and choose Version 5) of this notebook.

## HW-01 (2026-10-30, dqi): 889 -> 888 qubits on yoyobar's DQI by release-and-recompute

On yoyobar's public 889-qubit DQI decoder `73e1b187b288`, our release-and-recompute freed one qubit for +460.4 mean Toffolis per shot (a qubit is worth about 960 here). Result `5faba4591853`: 888 qubits, −0.117% DQI cost at the default salt and −0.108% over 48 fixed draws (local official verifier; local engine), about +0.036% expected overall score. One preregistered threshold was missed (8 failing draws of 48 against the base's 7) and the release said so.

- **Technique:** Release-and-recompute (spooky pebbling); Liveness ledger to find the idle hold.
- **Credit:** base circuit `73e1b187b288` by **yoyobar** ([notebook](https://www.kaggle.com/code/yoyobar/lb-22-99-invsqrt-101-62-qubits) v8, Apache-2.0), on the decoder line of **SomeJoint (Agniv Banerjee)**; releasing a pole flag and recomputing it was first used publicly by **heliosli** on SomeJoint's decoder. Change: release-and-recompute (Quantum Voodoo line), the q852 release, the q878 reset and the handover erase, by manwithacat.
- **Status (2026-11-05):** Overtaken: newer public 888-qubit DQI circuits are cheaper, for example yoyobar's `25db915d86ab` and `e20e6abea7e2` and Ahmed Berat Özer's `fe98677c61ef` (398,268,953,061 at the default salt, −0.93% against HW-01; re-verified by us with the local official verifier, 2026-10-31).
- **Full detail:** [Version 1](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook?scriptVersionId=364036151) of this notebook.

---

## 3. Techniques index

Every technique demonstrated so far, where it first appeared, and which later entries reuse it. **(Fett = DQI-Techniken.)**

| Technique | First shown | Reused in | What it does |
| --- | --- | --- | --- |
| **Release-and-recompute (spooky pebbling)** | HW-01, [Version 1](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook?scriptVersionId=364036151) | — | Measurement-based uncomputation (HMR) releases a value that sits idle across every peak run; it is recomputed (rematerialised) where it is next needed and the phase correction applied, so the peak qubit count falls for a few hundred extra Toffolis. Credit: ours (Quantum Voodoo line); releasing a pole flag was first used publicly by heliosli. |
| **Liveness ledger to find the idle hold** | HW-01, [Version 1](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook?scriptVersionId=364036151) | — | A liveness analysis (render.py ledger) lists each value's idle time at peak width, priced at the qubit's shadow price; it named the target (q852) before anything was built. Credit: ours (kickmix-macos fork). |
| Constrained λ_eff refit at fixed words | HW-03, [Version 2](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/versions) | HW-04, HW-05, HW-10, HW-11, HW-15 | Projected L-BFGS on log λ_eff over the continuous weights and offsets, with e1, e2 and E_gap held as equality constraints just inside their limits and a Gauss–Newton step back onto them after every move; the angle words and angle loaders, so qubits and Toffolis, never change. Credit: ours (constraint-manifold retraction idea from anazemcev's projected L-BFGS). |
| Refit alternated with a per-rank orthogonal column gauge | HW-03, [Version 2](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/versions) | HW-04, HW-15, HW-21 | Rotating one rank's columns by an orthogonal matrix leaves e1, e2 and E_gap unchanged but changes the column L1 norms in Λ; exact Jacobi sweeps plus a smoothed-L1 L-BFGS find a sparser frame between refits. Credit: gauge idea by Isabe11aM00re; the alternation and gauge search ours. |
| Slack-spending constrained refit (stepped e1 continuation) | HW-04, [Version 3](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/versions) | — | From a point that leaves error margin unused, the refit spends the e2 and E_gap margin and raises the e1 target in steps (16.5 → 18 → 19 → 19.9999 mHa), each from the previous point, with column gauges between; the extra e1 room lets the offsets lower the one-body norm Σ\|eig h1′\|. Credit: ours. |
| KKT shadow prices of the error margins | HW-04, [Version 3](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/versions) | — | The Lagrange multipliers of the equality-held constraints price each margin in % of λ_eff per mHa, showing which margin pays (here e2, about 200 times e1 at the final point) before compute is spent. Credit: ours (standard sensitivity analysis). |
| Fixed-e1 constrained refit on an open-pattern C40 table | HW-05, [Version 4](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook?scriptVersionId=364542669) | — | Move continuous W and H2_I on the e1/e2/E_gap constraint surface while freezing Lera's integer words and all compiled loaders; a nonzero projected KKT residual predicts local room to improve λ_eff. Credit: our application of the HW-03 constrained refit to Lera's C40 table. |
| **Measurement-based uncomputation of a borrowed-wire AND** | HW-06, [Version 5](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/versions) | HW-07, HW-08, HW-09 | A three-input AND computed with the help of a borrowed (dirty) wire costs 4 Toffolis to uncompute the same way. Measuring the result in the X basis instead clears it for free; the phase it leaves, (−1)^(m·abc), is removed by one CCZ on the three inputs, run only when the measured bit m is 1 (about half the shots). Credit: the construction is Gidney's (2018) measurement-based uncomputation of a temporary logical-AND; its application to these 12 sites is ours. |
| **Sound value tracking for provably-zero targets** | HW-06, [Version 5](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/versions) | — | A conservative tracker follows which wires are certainly 0 after each operation. A Toffoli whose target is provably 0 just afterwards is an uncompute, and so a candidate for measurement-based uncomputation. In this circuit it found exactly 12 such Toffoli groups; every other clean uncompute was already measurement-based. Credit: ours (harness probe, 2026-11-01). |
| **Measurement-based uncomputation of a multi-input AND with a clean-wire ladder** | HW-07, [Version 7](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/version/7) | HW-08 | A flag holding the AND of six bits, cleared by re-running a 16-Toffoli borrowed-wire chain, is instead measured in the X basis. Only when the outcome is 1 is a phase fix needed, (−1)^(y1⋯y6): it is applied by rebuilding the AND on two clean wires (3 CCX and one CCZ), each partial product then itself cleared by measurement-based uncomputation with a CZ or CCZ fix-up conditioned on its outcome. About 2.25 Toffolis expected per site instead of 16. Credit: measurement-based uncomputation of a temporary logical-AND is Gidney's (2018); the ladder and its application to these 12 sites are ours. |
| **Porting a tweak to a new base by site census** | HW-08, [Version 8](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/version/8) | — | A tweak found on one circuit often applies to a newer circuit from the same line. A census of the circuit file lists every site with the tweak's pattern (here, the three-input flag ANDs and six-input flags cleared by re-running a borrowed-wire chain) in about a minute, and the edits are generated from that list, so the port is mechanical and every site is accounted for. Re-running the original build code on the ported file and getting the same bytes checks the port. Credit: ours. |
| **Conditionally clean flag computation with measurement-based cleanup** | HW-09, [Version 10](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/version/10) | — | A clean target and one or two clean scratch wires replace a 6- or 12-input dirty-borrow compute chain; input wires become scratch only in the branch where their values are known, are restored, and temporary products are measured with phase corrections. Credit: Khattar and Gidney for conditionally clean ancillae; our local relay for these exhaustively checked S12/S6 templates; manwithacat with Codex for this frontier port. |
| Constrained λ_eff refit at fixed words, e1 released | HW-10, [Version 11](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/version/11) | — | Move W and H2_I on the e2/E_gap constraint surface with the integer words and compiled loaders frozen, letting e1 use its remaining headroom. Credit: our HW-03..HW-05 refit, applied to the newest public weights. |
| Weights and loaders combined across entries | HW-11, [Version 12](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/version/12) | HW-23 | Weights fit at fixed words are valid with any loaders for the same words, so the best weights and the cheapest loaders combine. Credit: parts assembly, with our HW-10 weights. |
| Systematic GF(2) kernel-relation search for QROM loaders | HW-12, [Version 13](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/version/13) | HW-13 | Add GF(2) relations that annihilate every high-monomial slice of a loader's mixed ANF tensor, keeping a perfectly paired rank-one basis; each admissible relation saves half a Toffoli per pass. Balanced round-robin choice over in-phase slot triples is what keeps pairing feasible. Credit: ours, on lightningv08's, Ahmed Berat Özer's, mrmeows' and matousakura's ideas, built with Lera's emitter. |
| Block-design relation plans with exchange repair | HW-13, [Version 14](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/version/14) | HW-14 | Partition the loader's slots into disjoint within-phase triples and draw a fixed number of relations from each triple's kernel; a basis-exchange repair then removes unpaired templates. Concentrating relations keeps each slot's constraint space small enough to pair perfectly (15 per triple: 35 − 2n partner directions). Credit: ours, extending HW-12. |
| Dead-word flips for QROM loaders | HW-14, [Version 15](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/version/15) | — | Angle words whose rotation acts on a zero-amplitude branch are exact don't-cares: changing them leaves every accuracy metric unchanged. Choosing their values to enlarge a loader's within-phase relation supply lets the planner find one more paired relation, saving a Toffoli per pass with no refit. Credit: ours, with the Rust qrom-plan search. |
| A reusable constrained refit tool (dfthc_refit) | HW-15, [Version 17](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/version/17) | HW-21 | The fixed-word constrained refit and column gauge of HW-03 to HW-10, packaged as one deterministic public tool: projected L-BFGS on log(λ_eff) with error_2 and E_gap held, error_1 as an inequality and near-zero h1′ eigenvalues held, alternated with the exact Jacobi column gauge, stopped when the KKT first-order gain and the realised gain both fall below 1e-5. Anyone can apply it to a new public family. Credit: ours (dfthc_refit 1.1.0); projected L-BFGS idea after anazemcev. |
| Re-planning a public loader's GF(2) relations from its own words | HW-16, [Version 19](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/version/19) | HW-17, HW-18 | A loader's Toffoli count is set by how many paired kernel relations its plan uses (HW-12 to HW-14). Starting from the published angle words, our relation planner finds a plan with four more products shared on each of the four plain loaders (0–3) of Ayodeji's new layout; Lera's unmodified emitter turns the plan into the circuit. Words, weights and accuracy do not move. Credit: ours (qrom-plan); emitter and table by Lera, layout by Ayodeji. |
| Loader re-planning as a repeatable step (dfthc_refit replan) | HW-17, [Version 20](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/version/20) | HW-23, HW-24 | The HW-16 re-planning packaged as a tool step: for each slot it recovers the loaded words, re-plans the loader with the relation planner, emits it with Lera's emitter and keeps it only if it has strictly fewer Toffolis and passes the native, width, layout and family checks; otherwise the shipped file is kept. Applied to a newer public family, it carries the HW-16 saving forward without redoing the work. Credit: ours (dfthc_refit 1.2.0-dev, local). |
| Padding rows as don't-cares in the loader search | HW-18, [Version 22](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/version/22) | HW-19, HW-23, HW-24 | Lera's loaders address 1,232 rows but the table has 1,220; the 12 padded rows are never read, so their values are free. Letting the relation search choose them lowers the rank of each loader's first output group by enough to save one product, with every loaded word unchanged. Credit: ours, on qwertykeypadapple's search. |
| Refit with the error margins held at the input's values | HW-21, [Version 24](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/version/24) | — | When a public table already sits at (or a hair past) the refit tool's default error caps, the refit is asked to hold error_1 and error_2 at the input's own values instead of tightening them first; the weights then move along the constraint surface and lower lambda_eff. Credit: manwithacat (James Barlow) with Claude (Anthropic), using our dfthc_refit tool. |
| **Joining two public circuits where they are byte-identical** | HW-22, [Version 24](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/version/24) | — | Two public circuits for the same task that agree byte for byte over a stretch can be cut there and joined: each side keeps the section where it is cheaper. The result uses no new gate, only the two authors' own operations. Credit: the two source circuits' authors (Akmal Xodarev; Alex Chilton and Leo Tang); the join by manwithacat with Claude (Anthropic). |
| Gauge-aware loader emission for a pi-gauge table | HW-23, [Version 25](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook/version/25) | HW-24 | Lera's emitter borrows each output word's top bit as scratch and restores it from bit 6, which is right only when the table is stored with bit 7 = bit 6. The table of Heliosli's aba448aeadb5 (Syed Asad Ali's words in Atakan Aldemir's pi-gauge tree) flips the top bit on about 21% of entries by a pattern fixed per column and set by the low address bits (an exact symmetry: the rotations do not change), and its loaders are exact XOR oracles given the previous slot's flip pattern. Building the low-address cache first lets the emitter clear the borrowed bit of the incoming pattern and restore it with the outgoing one, so loaders planned one Toffoli cheaper can be emitted on this table; a word whose pattern changes between slots keeps its top bit (+1 qubit). Credit: manwithacat (James Barlow) with Claude (Anthropic), extending Lera's (marculera) tensorqrom emitter, in dfthc_refit 1.5.0-dev (local). |
| Chained loader re-planning on a newly published family | HW-24, Version 26 (this release) | — | A new public table is taken through the loader tools the day it appears: read its storage convention (here a pi gauge with 10 flip patterns, and brot = 8 read from the circuits because the weights file has no brot field), compare each loader with the planner's floor, re-plan only the loaders above it, and chain the runs, each starting from the previous run's output, with fresh seeds for the slots still above the floor. A loader changes only if it is strictly cheaper and passes a native check on its real inputs. Credit: manwithacat (James Barlow) with Claude (Anthropic), dfthc_refit 1.6.0-dev (local). |

## 5. What did not work

Ideas that failed are kept with the same care as those that worked, in the [VQCC Negative Results](https://www.kaggle.com/datasets/manwithacat/vqcc-chemistry-negative-results) dataset: one row per idea, with its evidence tier, why it failed and what would reopen it. Before trying something, check there. **(Fett = DQI-Bezug.)**

- **Porting our failure fix to yoyobar's circuit gains nothing (HW-01).** Our Quantum Voodoo failure fix rebuilt decoder groups 4–7 as homogeneous chains with their poles dropped. yoyobar's circuit already has groups 3–7 built that way, so there is no Toffoli saving left and no chance-zero failure to remove (measured per group, local engine).
- **Releasing more idle wires cannot reach 887 (HW-01).** Releasing q866 or the 7-wire block cannot lower the peak, because 34 stretches at 888 use every live wire (24-bit multiplications; census, structural).
- A column gauge alone does not beat Isabe11aM00re's (HW-03). From Özer's weights, exact Jacobi sweeps and a smoothed-L1 L-BFGS from the identity, from Isabe11aM00re's frame and from 128 random kicks found nothing below Isabe11aM00re's frame (local prescreen). On Özer's C43 polish a gauge alone gained only 0.00073 in λ_eff (HW-04 run).
- Our earlier claim that the fixed-word refit sits at a constrained optimum (NR-0080) was start-specific. From Heliosli's weights it stalled; from Özer's, Isabe11aM00re's and Lera's it keeps improving (HW-03, HW-04).
- Jumping error_1 straight to its limit fails (HW-04). The refit's Gauss–Newton correction could not move the error_1 target from 13.3 to 18 or 20 mHa in one go; raising it in steps works.
- **yoyobar's 892-qubit DQI circuit does not reach 891 by cheap means (HW-06).** CNOT-only freeing covers 60 of 216 full-width stretches; releasing and recomputing the held epoch flags would cost about 1,900 Toffolis; clearing allocator artefacts leaves 132 stretches at 892. The normalize step needs a redesign (static model; see the HW-06 section).
- **Nor by releasing the carried pole flag (HW-07).** It is the one wire idle across every 892-qubit stretch, but it holds [N_k = 0] ∧ P with P the parity of the error weight, a global bit that no wire carries where it would be recomputed; rebuilding it costs about 1,872 Toffolis per shot against about 905 that a qubit is worth (bit-parallel classical simulation on 4,096 valid syndromes). 891 needs a new inversion kernel.

## 6. Credits (DQI)

- **HW-01** (dqi): base circuit `73e1b187b288` by **yoyobar** ([notebook](https://www.kaggle.com/code/yoyobar/lb-22-99-invsqrt-101-62-qubits) v8, Apache-2.0), on the decoder line of **SomeJoint (Agniv Banerjee)**; releasing a pole flag and recomputing it was first used publicly by **heliosli** on SomeJoint's decoder. Change: release-and-recompute (Quantum Voodoo line), the q852 release, the q878 reset and the handover erase, by manwithacat.
- **HW-06** (dqi): base circuit `6d58bd6d0232` by **yoyobar** (with GPT-6 Astra; [notebook](https://www.kaggle.com/code/yoyobar/lb-22-99-invsqrt-101-62-qubits) v11, Apache-2.0), the infinity-lead product reuse on **SomeJoint (Agniv Banerjee)**'s 892-qubit flag-carry circuit `bdee18489fac` ([notebook](https://www.kaggle.com/code/somejoint/quantum-circuits-23-77-local-gm-892-qubit-dqi) v25, Apache-2.0), whose flag carry follows **Ali Haydar Özdağ**'s flag carry. Change: measurement-based uncomputation at the 12 borrowed-wire flag ANDs, and the value tracker that found them, by manwithacat.
- **HW-07** (dqi): base circuit `c253111974fc`, our HW-06, on **yoyobar**'s `6d58bd6d0232` (with GPT-6 Astra; [notebook](https://www.kaggle.com/code/yoyobar/lb-22-99-invsqrt-101-62-qubits) v11, Apache-2.0), the infinity-lead product reuse on **SomeJoint (Agniv Banerjee)**'s 892-qubit flag-carry circuit `bdee18489fac` ([notebook](https://www.kaggle.com/code/somejoint/quantum-circuits-23-77-local-gm-892-qubit-dqi) v25, Apache-2.0), whose flag carry follows **Ali Haydar Özdağ**'s flag carry. Reading Ali Haydar Özdağ's (ahoirg) public reproducible rebuild of SomeJoint's decoder sources ([notebook](https://www.kaggle.com/code/ahoirg/score-23-64254-reproducible-circuit-portfolio) v1) explained the normalize step's wires. Change: the two-wire measurement-based uncomputation of the 12 six-input flags, by manwithacat.
- **HW-08** (dqi): base circuit `b7ca9bce749d` by **SomeJoint (Agniv Banerjee)** ([notebook](https://www.kaggle.com/code/somejoint/quantum-circuits-23-85-local-gm-892-qubit-dqi) v26, Apache-2.0): GPT-6 Astra Pro's q26 decoder round, with Claude putting SomeJoint's flag carry, which follows **Ali Haydar Özdağ**'s, on it; the flag carry is as in `bdee18489fac` (**yoyobar**'s one-carry history). Change: HW-06's and HW-07's measurement-based uncomputation at 24 sites, found by our census tool, by manwithacat.
- **HW-09** (dqi): Base by **Akmal Xodarev (Busya PRIME)**: [33 QCC V8 members](https://www.kaggle.com/datasets/busyaprime/33-qcc-v8-members) v9, from [Exact DQI Rewrites](https://www.kaggle.com/code/busyaprime/23-910-local-gm-exact-dqi-rewrites-892-qubits) v15, Apache-2.0. The core decoder is **SomeJoint (Agniv Banerjee)**'s q26 892-qubit design; busyaprime adds exact product caching, credits **Ahmed Berat Özer** for that idea, and incorporates our HW-07 ladder. Our S12/S6 templates were developed in the earlier local relay, following **Khattar and Gidney**'s conditionally clean ancilla method; this port and verification are by **manwithacat (James Barlow), assisted by Codex (OpenAI)**.
- **HW-22** (dqi): Unsynthesis section from `fd0ef09efd45` by **Akmal Xodarev (busyaprime)** ([33 QCC V8 members](https://www.kaggle.com/datasets/busyaprime/33-qcc-v8-members) v10, Apache-2.0), their exact rewrite of **Syed Asad Ali**'s 891-qubit decoder `fc3ba81614e1`. Everything else, including the unextract section, from `1c43b7ff2fcf`: **Alex Chilton**'s decoder version, released by **Leo Tang** in [VQCC T7421 Submission](https://www.kaggle.com/code/leotang09/vqcc-t7421-submission) v17 (Apache-2.0), on the public 891-qubit decoder line (Syed Asad Ali, Agniv Banerjee and others, as credited there). The join of the two public circuits and its verification are by manwithacat (James Barlow), assisted by Claude (Anthropic).

## 7. How to reproduce (DQI-Relevanz)

1. **Get the circuits.** Attach the [VQCC Hedge Wizardry dataset](https://www.kaggle.com/datasets/manwithacat/vqcc-hedge-wizardry). `entries.csv` gives each circuit's SHA-256 (`SHA256SUMS` lists every file; a chemistry entry's hash is its family hash). The base circuits are in the [VQCC public circuits dataset](https://www.kaggle.com/datasets/manwithacat/vqcc-apache-public-circuits) under `circuits/<task>/<sha12>`.
2. **Verify on Kaggle.** Copy this notebook and run it (CPU, internet off). It installs our [kickmix fork](https://github.com/manwithacat/kickmix-macos) offline from the attached wheel and runs the unchanged official verifiers on the portfolio. The entry gate below checks every entry's cost against `entries.csv`. The verifier seeds every shot from the file's SHA-256, so the same bytes give the same cost at the default salt.
3. **Verify locally** — DQI-Einträge:
   - **HW-01**: run the official `dqi` verifier on `circuits/dqi/5faba4591853.kmb` with an empty salt: PASS, 888 qubits, cost 401,986,129,571.42.
   - **HW-06**: run the official `dqi` verifier on `circuits/dqi/c253111974fc.kmb` with an empty salt: PASS, 892 qubits, cost 382,537,501,561.76.
   - **HW-07**: run the official `dqi` verifier on `circuits/dqi/1779b4e5967f.kmb` with an empty salt: PASS, 892 qubits, cost 384,137,374,413.52.
   - **HW-08**: run the official `dqi` verifier on `circuits/dqi/5e86f69a9611.kmb` with an empty salt: PASS, 892 qubits, cost 383,320,859,120.03.
   - **HW-09**: run the official `dqi` verifier on `circuits/dqi/1698e864a3a6.kmb` with an empty salt: PASS, 892 qubits, cost 378,829,899,786.41.
   - **HW-22**: run the official `dqi` verifier on `circuits/dqi/b99bf23306f6.kmb` with an empty salt: PASS, 891 qubits, cost 375,320,367,805.64.
4. **DQI draws.** The 48 draws come from our local engine with fixed seeds shared by base and candidate. That engine is not published, so these numbers cannot be re-run from public files. The per-draw costs and errors are in `evidence/<entry>/draws_48.csv`.
5. **Read the change.** A `.kmb` circuit is a list of operations. The fork's circuit viewer (`tools/circuit-viewer/render.py`, including `ledger --compare`) shows where base and candidate differ.

```python
# Code-Zelle (Submission-Builder): Das DQI-Risikomodell. Da nur der DQI-Cost vom Draw abhängt
# (cost = R(k) x Q^2 x Toffolis), wird aus dem 48-Draw-Mittel gegen den Zero-Failure-Cost ein
# Poisson-lambda gefittet (Bisektion auf E[R(k)]/R(0)). R_K ist die R-Tabelle des Verifiers.
# Daraus ergeben sich die fairen Fehlergrenzen (lucky / 1 Fehlschlag / 2 Fehlschläge) für den GM.
R_K = [1.19126, 1.19673, 1.20139, 1.20558, 1.20946, 1.21311, 1.21657]  # R(k), 102,400 shots (verifier)
def _pois(lam):
    from math import exp, factorial
    p = [exp(-lam) * lam ** k / factorial(k) for k in range(len(R_K))]
    p[-1] += 1 - sum(p)
    return p
DQI_RISK = None
ec = picks['dqi'].get('dqi_expected_cost')
if zf and ec and float(ec) >= float(zf):
    target = float(ec) / float(zf)
    lo, hi = 0.0, 10.0
    for _ in range(80):  # E[R(k)]/R(0) rises with lam: bisect
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if sum(q * r / R_K[0] for q, r in zip(_pois(mid), R_K)) < target else (lo, mid)
    lam = (lo + hi) / 2
    pk = _pois(lam)
    gm_k = lambda k: prod(dict(ratios, dqi=REFERENCE['dqi'] / (float(zf) * R_K[k] / R_K[0])).values()) ** (1 / 3)
    DQI_RISK = {"failures_per_draw": lam, "p_none": pk[0], "p_one_or_more": 1 - pk[0],
                "p_two_or_more": 1 - pk[0] - pk[1], "gm_lucky": gm_k(0), "gm_one": gm_k(1), "gm_two": gm_k(2),
                "basis": "Poisson fit to the 48-draw expected cost / zero-failure cost (manifest)"}
```

### Entry gate & Verification receipt (DQI-Teile)

Der Entry gate verifiziert jeden Eintrag auf Kaggle (kickmix-engine + kickmix-fork, beide laufen den unveränderten offiziellen Verifier-Code). Ein bereits im Portfolio enthaltener Eintrag reutilisiert den Lauf oben; neue Releases werden separat geprüft. Die Kosten eines verifizierten Eintrags müssen mit dem lokalen `entries.csv`-Record auf 1e-9 übereinstimmen — das gilt, weil der Verifier jeden Shot vom SHA-256 der Datei seedet.

Im Headroom-Report wird für DQI ausgegeben: `failed shots on this file's draw (value / phase)` und `repetition factor R = …; each extra failure costs about 0.46% of DQI cost`. Die Gates sind: G1 (jede Datei matcht ihren SHA-256), G2 (alle drei PASS), G3 (jede Kosten-Verifikation dieses Laufs innerhalb 1e-9 ihres Source-Records), G4 (Notebook-Wall-Time < 2 h).

---

## Anhang: Chemistry-Einträge (nicht DQI, kompakt)

Die restlichen HWs betreffen die Chemistry (dfthcsos)-Task — hier als Verweis, damit nichts verloren geht. Details stehen in den jeweiligen Notebook-Versionen.

| HW | Datum | Technik (Chemistry) | Gain |
|---|---|---|---|
| HW-03 | 2026-10-31 | Constrained λ_eff refit at fixed words; Refit alternated with a per-rank orthogonal column gauge | λ_eff 48.293182 → 48.274616, −0.0384 % |
| HW-04 | 2026-10-31 | Slack-spending constrained refit (stepped e1 continuation); KKT shadow prices | λ_eff 47.080918 → 46.976679, −0.2214 % |
| HW-05 | 2026-11-01 | Fixed-e1 constrained refit on an open-pattern C40 table | λ_eff 47.105858 → 47.048390, −0.1220 % |
| HW-10 | 2026-11-02 | Constrained λ_eff refit at fixed words, e1 released | λ_eff 47.035278 → 47.031870, −0.0072 % |
| HW-11 | 2026-11-02 | Weights and loaders combined across entries | −0.0072 % |
| HW-12 | 2026-11-02 | Systematic GF(2) kernel-relation search for QROM loaders | 16,071 → 15,861 Toffolis, −1.31 % |
| HW-13 | 2026-11-02 | Block-design relation plans with exchange repair | 15,861 → 15,787, −0.47 % |
| HW-14 | 2026-11-02 | Dead-word flips for QROM loaders | 297 → 296/loader, −0.063 % |
| HW-15 | 2026-11-03 | A reusable constrained refit tool (dfthc_refit) | λ_eff 47.025650 → 47.023457, −0.0047 % |
| HW-16 | 2026-11-04 | Re-planning a public loader's GF(2) relations from its own words | 307 → 303/loader, −0.207 % |
| HW-17 | 2026-11-04 | Loader re-planning as a repeatable step (dfthc_refit replan) | −0.207 % / −0.013 % |
| HW-18 | 2026-11-04 | Padding rows as don't-cares in the loader search | 4,303 → 4,288/pass, −0.195 % |
| HW-19 | 2026-11-04 | HW-18 padded-row step on Syed Asad Ali's new word table | 282 → 280/pass, −0.287 % |
| HW-21 | 2026-11-05 | Refit with the error margins held at the input's values | λ_eff 46.876470 → 46.874651, −0.0039 % |
| HW-23 | 2026-11-05 | Gauge-aware loader emission for a pi-gauge table | 15,181 → 15,173, −0.0527 % |
| HW-24 | 2026-11-05 | Chained loader re-planning on a newly published family | 4,229 → 4,207/pass, −0.2910 % |

---

## 🔑 Kern-Technik in 3 Sätzen

1. **Measurement-based Uncomputation (MBU):** Statt ein multi-Input-AND (z. B. 6- oder 12-Input) mit einer 16-Toffoli-Borrowed-Wire-Kette rückwärts zu rechnen, misst man das Ergebnis in der X-Basis — das räumt den Wire gratis; nur wenn die Messung 1 liefert, muss man die Phase (−1)^(y1⋯y6) per CCZ bzw. einer Zwei-Wire-Ladder (~2.25 Toffolis erwartet statt 16) korrigieren.
2. **Release-and-recompute (Qubit Floor):** Ein Wert, der über alle Peak-Läufe idle liegt, wird per HMR freigegeben und an der nächsten Stelle neu materialisiert — das senkt die Peak-Qubit-Zahl um 1 (889→888) für nur +460 Toffolis/Shot, weil ein Qubit hier ~960 Toffolis wert ist (Q²-Faktor!).
3. **48-Draw-Bewertung statt Lucky Draw:** Weil der DQI-Cost R(k)×Q²×T vom Salt-Draw abhängt, wird jeder Gewinn als Mittel über 48 fixe, zwischen Base und Candidate geteilte Draws gemessen und nie an einem einzelnen glücklichen Draw — erst dann ist ein Tweak wirklich billiger.

## ⚠️ Häufigste Fehlerfalle

Einen DQI-Gewinn **an einem einzelnen Salt-Draw zu messen** und zu glauben, er sei echt. Ein byte-verschiedener Circuit würfelt den Verifier-Draw neu und kann per Rauschen hauchbilliger aussehen (daher die Tie-Regel REL_TIE=1e-5 und das „original first“-Prinzip). Zweitgefährlich: **zu früh auf 891 Qubits zu hoffen** — HW-06/HW-07 zeigen, dass der 892er nicht billig auf 891 kommt (CNOT-only-Freigabe deckt nur 60 von 216 Full-Width-Stretches; das Pole-Flag neu zu bauen kostet ~1,872 Toffolis/Shot, mehr als ein Qubit wert ist). 891 braucht einen neuen Inversion-Kernel.

## 📝 Lern-Notizen (füll das selbst aus)

- [ ] Decoding-Prinzip verstanden: DQI = Reed-Solomon-Decoder RS(4095,4025)/GF(2¹²); die Tweaks ändern die Dekodierung nicht, nur die Gate-Zahl/Qubit-Breite.
- [ ] Cost-Formel R(k)×Q²×T internalisiert: MBU spart T (linear), release-and-recompute spart Q (quadratisch!) — deshalb ist ein Qubit-Gewinn (~960 Toffolis äquiv.) oft mehr wert als viele Toffolis.
- [ ] Product Caching nachvollziehbar: busyaprimes exact product caching (R41) übertrifft HW-08 um 0.60 % auf denselben 48 Draws — Caching räumt die HW-06/07-Klasse-Stellen bereits per MBU auf.
- [ ] Verbindung zu invsqrt/Chem: invsqrt hat kein Q² (nur Q×Toffoli-äquiv.), Chemistry ist linear in Q (λ_eff×T×Q) — nur DQI belohnt Qubit-Sparen quadratisch, daher konzentriert sich die Frontier dort auf 891 vs 892.
- [ ] Frage die ich noch habe: Wie genau funktioniert der „Site Census“, der alle 24 MBU-Stellen in ~1 Minute findet — welche Pattern-Matching-Regel auf der .kmb-Operationliste?
