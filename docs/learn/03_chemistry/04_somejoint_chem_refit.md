# Quantum Circuits | 24.65 Local GM: Chem Refit

> **Lernziel:** Wie man eine bestehende Compact-Group-Tabelle (Lera, 8×143×45) mit qwertykeypadapples Kernel-Search-Loadern nimmt und λ_eff durch iterativen Weight-Refit (W, H2_I) mit guarded Tangent Steps + exakten Gauge-Sweeps weiter drückt — fünf Pässe.
> **Dauer:** ~18 Minuten lesen
> **Quelle:** Agniv Banerjee (somejoint) · 117 votes
> **Technik:** Weight Refit (guarded tangent steps + exact gauge sweeps)
> **Level:** Fortgeschritten

---

**Geometric mean 24.65394** from the official verifiers at their default seeds. That is a local measurement; the leaderboard measures again with its own samples.

For each task this notebook takes the best public circuit we have verified. The DQI circuit is other people's public work, used unchanged: we link it and credit its authors in full. In inverse square root, our circuit of version 33 takes Kirill Tymchishin's two forced phase bits, explained below. In chemistry, qwertykeypadapple's kernel-search circuits for Lera's compact-group table are used byte for byte, and the table weights on them are our own refit, explained below. The notebook checks that every member is byte for byte the circuit the official verifiers passed, and writes `/kaggle/working/submission.zip`.

| Task | Circuit by | Q | Mean Toffolis | Cost | Ratio |
|---|---|---:|---:|---:|---:|
| invsqrt | Kirill Tymchishin's two forced phase bits, on our circuit of version 33: Alex Chilton's rewrite of our ladder on Syed Asad Ali's circuit, with one accumulator's four Toffolis as two, a saving qiuqiuh made first | 62 | 1,281.7 | 97,921.6 | **21.2085** |
| DQI | yoyobar, one more CCZ saved on its second rewrite of Syed Asad Ali (syed3000)'s 891-qubit decoder, on our 892-qubit line with its narrow return and flag carry, an idea of Ali Haydar Özdağ | 891 | 396,918.5 | 3.75373e+11 | **65.1071** |
| Chemistry | qwertykeypadapple's kernel-relation search on Lera's compiler for the fifteen circuits, Lera's compact-group table, with the weights refit by Claude | 427 | 15,347.0 | 3.09208e+08 | **10.8523** |

## How the score works

Each task has an official verifier. It runs the circuit on many sampled inputs, checks every answer exactly, and bills a cost:

| Task | Cost | The letters |
|---|---|---|
| invsqrt | $Q \cdot C$ | $Q$ qubits; $C = N_{\mathrm{Tof}} + N_T / 4$, the mean Toffolis and T gates of one shot |
| DQI | $R \cdot Q^2 \cdot T$ | $T$ the mean Toffolis of one shot; $R \ge 1$ grows with the failed shots |
| Chemistry | $\lambda_{\mathrm{eff}} \cdot T \cdot Q$ | $\lambda_{\mathrm{eff}}$ the Hamiltonian's effective normalization; $T$ the Toffolis of one step |

A task's **ratio** is the organizers' reference cost divided by this cost. The references are 2,076,774, $2.4439 \times 10^{13}$ and 3,355,599,588. The score is the **geometric mean of the three ratios**:

$$\text{score} = \left( \frac{C^{\mathrm{ref}}_{\mathrm{invsqrt}}}{C_{\mathrm{invsqrt}}} \cdot \frac{C^{\mathrm{ref}}_{\mathrm{DQI}}}{C_{\mathrm{DQI}}} \cdot \frac{C^{\mathrm{ref}}_{\mathrm{chem}}}{C_{\mathrm{chem}}} \right)^{1/3}$$

So making any one task 1% cheaper lifts the score by about 0.33%.

The three bills reward different things. In DQI, $Q$ is squared: near 880 qubits one qubit is worth 0.23% of the cost. In invsqrt one qubit near 63 is worth 1.6%. In chemistry each of the three factors counts the same.

## invsqrt · Our version 33 circuit, with Kirill Tymchishin's two idle phase bits forced to zero

**This circuit.**
- $Q = 62$. A shot runs 1,281.6647 Toffolis on average, 41 rotations and 11.5 T gates.
- The cost is $S = 97{,}921.58$, 21.2085× below the reference. That is 77.54 below our version 33 circuit, at 97,999.12, and 201.55 below Alex Chilton's, at 98,123.13.
- It is our version 33 circuit with two lines added. Nothing else changes.

**Kirill Tymchishin's forced bits.**
- The circuit undoes its work wires by measurement. Each such measurement gives a random bit, and the bit switches on the phase corrections that follow it.
- Two of these measurements read a wire that is already zero on every branch. Such a bit is a fair coin and leaves no phase behind, so every correction it switches on is unnecessary.
- Kirill Tymchishin's public circuit of 4 November sets these two bits to zero right after their measurements, so their branches never run. On average a shot saves half a Toffoli and 3 T gates.
- We put the same two lines into our version 33 circuit with a small script. On Alex Chilton's circuit the script gives back Kirill Tymchishin's file byte for byte.
- Our census of all 899 measurements finds no third such site that saves anything.

**The accumulator cut of version 33, and qiuqiuh.** In version 33 we cut the four Toffolis of one accumulator site to two, by the rank of their quadratic form. qiuqiuh's public notebook makes the same saving at that site, in another placement, in a version that ran at 09:09 UTC on 4 November, before ours. We found ours independently and first saw theirs at 11:50 UTC. The credit for that saving is qiuqiuh's.

**How it was checked.**
- The official verifier passes at its defaults and at three fresh salts, 97,921.60 to 97,921.64, worst shot 0.99932 of the tolerance.
- Our replay of every outcome passes on all 3,133,452 inputs for every assignment of the 899 measurements. The exact mean Toffoli count is $167990399/131072$, exactly half a Toffoli below version 33.
- Another of our agents checked it with its own engine: the same exact mean and $23/2$ T gates on eight input screens, with every outcome.

**Genealogy.** mrmeows and team selenium → Akmal Xodarev (busyaprime), 63 qubits → yoyobar with GPT-6 Astra, 62 qubits → Ahmed Berat Özer's phase patch and Ehan Mallick's two AND merges → Syed Asad Ali's lookup, edit rounds and window resynthesis → Claude's ladder and window splice → Alex Chilton's rewrite: five Toffolis into one accumulator as four → qiuqiuh's, and independently Claude's, cut of that accumulator's four Toffolis to two → Kirill Tymchishin's two forced phase bits. Source: our own: our circuit of version 33 (block qform-80ac3d48), with the two lines that Kirill Tymchishin's circuit c2735d8e adds to Alex Chilton's, from [Quantum Circuits | Four Loaders, Eight Toffolis](https://www.kaggle.com/code/kirilltym/quantum-circuits-four-loaders-eight-toffolis), its run of 10:56 UTC on 4 November 2026, which we took in at 11:55 UTC, under Apache 2.0; inserted by our script.

## DQI · yoyobar's third rewrite of Syed Asad Ali's 891-qubit decoder

Used unchanged. Source: the output of yoyobar's public portfolio notebook [lb-22-99-invsqrt-101-62-qubits](https://www.kaggle.com/code/yoyobar/lb-22-99-invsqrt-101-62-qubits), its run of about 15:23 UTC on 4 November 2026, which we took in at 15:34 UTC, as dqi.kmb inside its submission.zip; held in our dataset so that a later version of that notebook changes nothing here.

**Genealogy.** jday96314 and Alex Chilton, by design → our decoder line and its narrow return → Ali Haydar Özdağ's flag carry, in our 892-qubit line → Syed Asad Ali's C1 decoder at 891 qubits → yoyobar's one-CCZ rewrite → yoyobar's further Toffoli-equivalent saving → yoyobar's one more CCZ.

## Chemistry · qwertykeypadapple's kernel-search circuits, with our refit of the table weights

**The task.** Block-encode the FeMoCo active-space Hamiltonian, 76 orbitals and 113 electrons, for qubitized phase estimation. The submission supplies a factorization of the Hamiltonian and the circuits that load its rotation angles. Two error measures of the factorization must stay below 20 mHa, and the sum-of-squares gap $E_{\mathrm{gap}}$ must stay above 3.914898 Ha. The bill is **$\lambda_{\mathrm{eff}} \times T \times Q$**.

**This submission.**
- $\lambda_{\mathrm{eff}}$ **47.184436**, $T$ **15,347**, $Q$ **427**.
- Errors 11.195 and 19.999999 mHa, against the 20 mHa limit. Gap 3.9148990 Ha.
- Cost **309,207,580**, 10.8523× below the reference. That is 1,716 below 309,209,296, qwertykeypadapple's at its version 1 on 4 November 2026, the best public chemistry we know of, with the weights of our version 34 on the same circuits, and 1,220 below 309,208,800, Isabe11aM00re's run of 20:09 UTC, the same circuits with its own weights.

**What changed.** The circuits are now qwertykeypadapple's, and the table weights $W$ and $H_2^I$ on them are our own refit, one pass further than version 35.

- **The circuits** are the fifteen of qwertykeypadapple's notebook, byte for byte: its kernel-relation search on Lera's tensor lookup compiler, for Lera's (8, 143, 45) table, 303 Toffolis on each of circuits 0–3 and 281 on each of circuits 4–14, against 307 and 282–285 in Lera's own. So $T$ 15,347 and $Q$ 427. The weights fit the angle words, not the circuits, so any weights fitted to those words serve them.
- **The weights** start from the part's own. Its gap stood 3.19 mHa above its limit; our chain of guarded tangent steps, with exact gauge sweeps between them, spends that margin and lets the second error come within a few $10^{-9}$ Ha of its limit. $\lambda_{\mathrm{eff}}$ falls from 47.266713 to 47.184436: version 34 stopped after the third pass, at 47.184697, version 35 after the fourth, at 47.184606, and this is the fifth.

The angle words and the factors are those of Lera's public table, and the circuits, $T$ and $Q$ those of qwertykeypadapple's.

**Genealogy.** Lera's DF-THC pipeline and Ahmed Berat Özer's progressive rounding → Lera's compact groups pipeline: the (8, 143, 45) table and its words → Lera's tensor lookup compiler → qwertykeypadapple's kernel-relation search: fifteen circuits → Claude's refit of the weights. Source: our own: `submission.npz` has our `W` and `H2_I`, the fifth pass of our refit, with every other array equal to the file of ayodejiibrahimlateef's [Quantum Portfolio | 24.56308 Local](https://www.kaggle.com/code/ayodejiibrahimlateef/quantum-portfolio-24-56308-local), its run of 12:02 UTC on 4 November 2026, under Apache 2.0. The 15 angle circuits are those of qwertykeypadapple's [QCC Kernel Search 24.65](https://www.kaggle.com/code/qwertykeypadapple/qcc-kernel-search-24-65), version 1 on 4 November 2026 as our intake took it at 20:34 UTC, byte for byte, under Apache 2.0. Held in our dataset so that a later version of either notebook changes nothing here.

## Run: take the bytes, check, pack

Attach the competition data and the dataset [somejoint/qcc-ladder-parts](https://www.kaggle.com/datasets/somejoint/qcc-ladder-parts), and choose the Python 3.13 CPU image. No internet, installs or training are needed.

Every member is found by its SHA-256, among the inputs, so a changed input fails loudly instead of slipping through. The official verifiers ran on these exact bytes before assembly, at their defaults; the tables above quote those runs. Set `VERIFY = True` below to rerun all three here, about ten minutes. The last cell checks the format rules, packs the ZIP and reads it back.

> **Code (DE):** Kern der Assemblierung: COMPETITION_FILES/MEMBERS/SOURCES pinnen jede Datei per SHA-256; EXPECTED hält die exakten Verifikator-Werte (λ_eff, Toffolis, Qubits, Cost) der letzten offiziellen Läufe; die Funktionen run()/build()/verify() finden die Bytes unter den Inputs, prüfen sie und fahren den unveränderten offiziellen Verifikator.

```python

COMPETITION_FILES = {'kickmix/LICENSE.txt': 'cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30', 'kickmix/kickmix.so': 'c66b3216c4029e0cdfd09054306aa0feadf53ab2f50c1164e37f752874e5005e', 'verifiers/LICENSE.txt': 'cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30', 'verifiers/dfthcsos/FeMoCo76o113e.fcidump': 'e5a48af746fd075026dec9e8f5df2d363802a121e8c53af9a0b984bde695e1bd', 'verifiers/dfthcsos/FeMoCo76o113e.fixed_shifts.npz': '7b7facf63fe35a9d9d3d00787ffdb700c863fa845fe4724d7f7c54778151cd87', 'verifiers/dfthcsos/SCORING_README.md': 'c2228569f96e58e118419bc32be2be9e33d6abffb8117cb0b91e1fc25b2a0230', 'verifiers/dfthcsos/__init__.py': '81915e324cc0cade67f52a54b7a51991fd96abaea94d1f8a4d423dae20e57348', 'verifiers/dfthcsos/scoreinfra/__init__.py': 'be90e0d503d5c20dcac0102af638b9a4ccad0341daa5baa5d49216a259e4516f', 'verifiers/dfthcsos/scoreinfra/circuits.py': 'fc027b52fdcebe14404f403a089122485d097ed65d03e6d989623d620b1ab68c', 'verifiers/dfthcsos/scoreinfra/costs_prepare.py': '7f1e190c42fc5325f3e6689fbbef51f95b0cb12f1c828cda92b6c088e72206da', 'verifiers/dfthcsos/scoreinfra/dfthc_math.py': 'ae82898d47a7a86b96378fb906e0f8a9f46003065cf19c7c09952a123b5b5af8', 'verifiers/dfthcsos/scoreinfra/reference.py': 'a2d5a63191d655729e29f0fde1e85fe4630bf896a91a63bb894d8d7daf71ed39', 'verifiers/dfthcsos/verify.py': '0775be7a528922367caebe9e4d051d6199811f1aefeaa4b793eaaa4621b8ec9d', 'verifiers/dqi/__init__.py': '01c870aa9763f4e4357fc6654bff1d3296cec995bd0943f87b4a48946ada5b40', 'verifiers/dqi/dqi_reference_circuit.py': '2b8e1b80a806157c333a7e308eaf2499ee09de499efbc05875202c327959959e', 'verifiers/dqi/verify_submission_dqi.py': 'f14274bc0943fb9769ddb01131be6063191a15009fe1caf1d4bdd9fd25194e65', 'verifiers/invsqrt/__init__.py': 'e9a6ecf253c343528578be5fa92eb820ccade63333aebb784552fb4ae75dbc0b', 'verifiers/invsqrt/nr_reference_circuit.py': 'bb90330dcf774f7b502de471293facba67f27952cc8808fe4a9970a9b1322e23', 'verifiers/invsqrt/verify_submission_invsqrt.py': 'ddef520dec6b68d1cf0a6f328ddd36d79eb84570b9192cf3f7acaf073f06733a'}
SOURCES = {'notebooks/launch.py': '"""Isolated launcher for the pinned official verifiers and reviewed local code.\n\nSPDX-License-Identifier: Apache-2.0\nOnly authenticated competition directories are added; never input ZIP code.\n"""\nfrom pathlib import Path\nimport runpy\nimport sys\n\nroot = Path(__file__).resolve().parent.parent\nsys.dont_write_bytecode = True\nsys.path[:0] = [str(root / \'data/comp/kickmix\'), str(root / \'data/comp/verifiers\')]\ntarget = Path(sys.argv[1]).resolve()\nsys.argv = [str(target), *sys.argv[2:]]\nrunpy.run_path(str(target), run_name=\'__main__\')\n', 'notebooks/take.py': '"""Copy pinned submission members out of the notebook\'s inputs.\n\nSPDX-License-Identifier: Apache-2.0\nRun with Python -I: take.py INPUT_ROOT OUTPUT_DIR MEMBERS_JSON [MORE_ROOTS...]\nMEMBERS_JSON maps each member name to its sha256 and size. A member is taken from a\nplain file whose path ends with the member\'s name, or else from a ZIP member whose\nname ends the same way; only a copy with the pinned size and SHA-256 is kept. Nothing\nfrom an input is executed, and no archive is extracted whole. MORE_ROOTS, such as the folder of\nmembers built in the notebook, are searched the same way.\n"""\nimport hashlib\nimport json\nfrom pathlib import Path, PurePosixPath\nimport shutil\nimport sys\nimport zipfile\n\n\ndef digest(stream):\n    h = hashlib.sha256()\n    while chunk := stream.read(1 << 22):\n        h.update(chunk)\n    return h.hexdigest()\n\n\ndef ends_with(path_parts, name_parts):\n    return tuple(path_parts[-len(name_parts):]) == name_parts\n\n\ndef main():\n    root, out, manifest = Path(sys.argv[1]), Path(sys.argv[2]), json.loads(Path(sys.argv[3]).read_text())\n    roots = [root, *map(Path, sys.argv[4:])]\n    files = sorted(p for r in roots if r.is_dir() for p in r.rglob(\'*\') if p.is_file())\n    zips = [p for p in files if p.suffix == \'.zip\']\n    taken = {}\n    for name, pin in manifest.items():\n        parts = PurePosixPath(name).parts\n        assert not PurePosixPath(name).is_absolute() and \'..\' not in parts, name\n        target = out / name\n        target.parent.mkdir(parents=True, exist_ok=True)\n        for path in files:\n            if ends_with(path.parts, parts) and path.stat().st_size == pin[\'size\']:\n                with path.open(\'rb\') as stream:\n                    if digest(stream) == pin[\'sha256\']:\n                        shutil.copyfile(path, target)\n                        taken[name] = str(path)\n                        break\n        for path in zips if name not in taken else []:\n            with zipfile.ZipFile(path) as archive:\n                for info in archive.infolist():\n                    if not ends_with(PurePosixPath(info.filename).parts, parts) or info.file_size != pin[\'size\']:\n                        continue\n                    # Reading to EOF also checks the member\'s ZIP CRC.\n                    with archive.open(info) as source, target.open(\'wb\') as copy:\n                        shutil.copyfileobj(source, copy, length=1 << 20)\n                    with target.open(\'rb\') as stream:\n                        if digest(stream) == pin[\'sha256\']:\n                            taken[name] = f\'{path}:{info.filename}\'\n                            break\n                    target.unlink()\n            if name in taken:\n                break\n        if name not in taken:\n            raise SystemExit(f\'{name}: no input holds SHA-256 {pin["sha256"]}; attach the source its block names\')\n    print(json.dumps({\'status\': \'PASS\', \'taken\': taken}, indent=1))\n\n\nif __name__ == \'__main__\':\n    main()\n', 'notebooks/check-submission': '#!/usr/bin/env python3\n"""Checks a submission folder against the metric\'s extra rules, the ones the local verifiers skip.\n\n    .venv/bin/python -I tools/check-submission SUBMISSION_DIR\n\nThe rules come from the metric notebook, as reported in Kaggle discussion 751951; a submission that breaks one\nis rejected as a whole, even when every verifier passes:\n- every circuit\'s largest qubit or bit id, max(num_qubits, num_bits) - 1, is below 2**30 // 1536 = 699,050;\n- every register has a name;\n- the folder holds exactly invsqrt.kmb, dqi.kmb and dfthcsos/ with angle_k_0 .. angle_k_<n-1> (no gaps) and\n  submission.npz, and nothing else anywhere;\n- submission.npz arrays are little-endian floats, except the index arrays tree_edges and angle_words, which are\n  integer types. The sample submission, which the metric accepted in submission 1, stores angle_words as int64.\n  The 8-bit factorizations of 2026-10-26 also store brot and kept_indices as int64 and one_body_requires_refresh\n  as a bool; the metric scored exactly such a file, version 14 of kirilltym\'s QROM + Tower42 (public 19.57899).\n  Lera\'s compact-group factorization stores coded (60,), coded2 (0,) and codes (75, 8) as int64, which the verifier\n  never reads; the metric scored exactly such a file, version 3 of ayodejiibrahimlateef\'s\n  quantum-portfolio-24-56308-local, run of 12:02 UTC on 2026-11-04 (public 24.56307, its local GM 24.56308).\n"""\nimport os\nimport pathlib\nimport re\nimport sys\n\nimport numpy as np\n\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / \'data\' / \'comp\' / \'kickmix\'))\nimport kickmix as km  # noqa: E402\n\nMAX_ID = 2**30 // 1536\nINTEGER_ARRAYS = (\'tree_edges\', \'angle_words\', \'brot\', \'kept_indices\', \'coded\', \'coded2\', \'codes\')\nBOOL_ARRAYS = (\'one_body_requires_refresh\',)\n\nroot = sys.argv[1]\nproblems = []\nfiles = sorted(os.path.relpath(os.path.join(d, f), root) for d, _, fs in os.walk(root) for f in fs)\nangles = [f for f in files if re.fullmatch(r\'dfthcsos/angle_k_\\d+\\.kmb\', f)]\nexpected = {\'invsqrt.kmb\', \'dqi.kmb\', \'dfthcsos/submission.npz\'} | {f\'dfthcsos/angle_k_{i}.kmb\' for i in range(len(angles))}\nif set(files) != expected:\n    problems.append(f\'file set differs: extra {sorted(set(files) - expected)}, missing {sorted(expected - set(files))}\')\nfor f in [f for f in files if f.endswith(\'.kmb\')]:\n    c = km.Circuit.from_file(os.path.join(root, f))\n    top = max(c.num_qubits, c.num_bits) - 1\n    unnamed = [k for k in c.register_data if not isinstance(k, str)]\n    print(f\'{f}: qubits {c.num_qubits}, bits {c.num_bits}, largest id {top}, {len(c.register_data)} registers\')\n    if top >= MAX_ID:\n        problems.append(f\'{f}: largest id {top} >= {MAX_ID}\')\n    if unnamed:\n        problems.append(f\'{f}: unnamed registers {unnamed}\')\nnpz = np.load(os.path.join(root, \'dfthcsos\', \'submission.npz\'), allow_pickle=False)\nfor name in npz.files:\n    a = npz[name]\n    kind = np.integer if name in INTEGER_ARRAYS else np.bool_ if name in BOOL_ARRAYS else np.floating\n    kind_ok = np.issubdtype(a.dtype, kind)\n    little = a.dtype.byteorder in (\'<\', \'|\') or (a.dtype.byteorder == \'=\' and sys.byteorder == \'little\')\n    print(f\'npz {name}: dtype {a.dtype.str}, shape {a.shape}\')\n    if not kind_ok or not little:\n        problems.append(f\'npz {name}: dtype {a.dtype.str}\')\nprint(\'PROBLEMS:\' if problems else \'ALL CHECKS PASS\', *problems, sep=\'\\n  \')\nsys.exit(1 if problems else 0)\n', 'notebooks/extra-format.py': '#!/usr/bin/env python3\n"""Supplement check-submission with NPZ header bounds and ANGLE T counts.\n\nFrom runs/submission-8/extra-format.py; booleans are allowed since 2026-10-27, as in check-submission.\n"""\nimport json\nimport math\nfrom pathlib import Path\nimport sys\nimport zipfile\n\nimport kickmix as km\nimport numpy as np\n\nroot = Path(sys.argv[1]) / "dfthcsos"\naudit = {"npz_headers": {}, "angle_circuits": {}}\nwith zipfile.ZipFile(root / "submission.npz") as z:\n    for member in z.infolist():\n        with z.open(member) as f:\n            version = np.lib.format.read_magic(f)\n            assert version == (1, 0), (member.filename, version)\n            shape, _, dtype = np.lib.format.read_array_header_1_0(f)\n        assert dtype.kind in ("f", "i", "u", "b") and dtype.byteorder != ">"\n        assert dtype.names is None and dtype.subdtype is None\n        audit["npz_headers"][member.filename] = {\n            "shape": list(shape), "dtype": dtype.str,\n            "array_bytes": math.prod(shape) * dtype.itemsize,\n            "npy_version": list(version),\n        }\naudit["total_npz_array_bytes"] = sum(x["array_bytes"] for x in audit["npz_headers"].values())\nassert audit["total_npz_array_bytes"] <= 2**26\nfor p in sorted(root.glob("angle_k_*.kmb")):\n    circuit = km.Circuit.from_file(str(p))\n    stats = circuit.operation_statistics()\n    audit["angle_circuits"][p.name] = {\n        "num_qubits": circuit.num_qubits, "num_bits": circuit.num_bits,\n        "registers": list(circuit.register_data), "t_gates": int(stats.num_t_like),\n        "static_toffolis": int(stats.num_toffoli_like),\n    }\n    assert stats.num_t_like == 0 and circuit.num_qubits <= 128\nprint(json.dumps(audit, indent=2))\n', 'LICENSE': '\n                                 Apache License\n                           Version 2.0, January 2004\n                        http://www.apache.org/licenses/\n\n   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION\n\n   1. Definitions.\n\n      "License" shall mean the terms and conditions for use, reproduction,\n      and distribution as defined by Sections 1 through 9 of this document.\n\n      "Licensor" shall mean the copyright owner or entity authorized by\n      the copyright owner that is granting the License.\n\n      "Legal Entity" shall mean the union of the acting entity and all\n      other entities that control, are controlled by, or are under common\n      control with that entity. For the purposes of this definition,\n      "control" means (i) the power, direct or indirect, to cause the\n      direction or management of such entity, whether by contract or\n      otherwise, or (ii) ownership of fifty percent (50%) or more of the\n      outstanding shares, or (iii) beneficial ownership of such entity.\n\n      "You" (or "Your") shall mean an individual or Legal Entity\n      exercising permissions granted by this License.\n\n      "Source" form shall mean the preferred form for making modifications,\n      including but not limited to software source code, documentation\n      source, and configuration files.\n\n      "Object" form shall mean any form resulting from mechanical\n      transformation or translation of a Source form, including but\n      not limited to compiled object code, generated documentation,\n      and conversions to other media types.\n\n      "Work" shall mean the work of authorship, whether in Source or\n      Object form, made available under the License, as indicated by a\n      copyright notice that is included in or attached to the work\n      (an example is provided in the Appendix below).\n\n      "Derivative Works" shall mean any work, whether in Source or Object\n      form, that is based on (or derived from) the Work and for which the\n      editorial revisions, annotations, elaborations, or other modifications\n      represent, as a whole, an original work of authorship. For the purposes\n      of this License, Derivative Works shall not include works that remain\n      separable from, or merely link (or bind by name) to the interfaces of,\n      the Work and Derivative Works thereof.\n\n      "Contribution" shall mean any work of authorship, including\n      the original version of the Work and any modifications or additions\n      to that Work or Derivative Works thereof, that is intentionally\n      submitted to Licensor for inclusion in the Work by the copyright owner\n      or by an individual or Legal Entity authorized to submit on behalf of\n      the copyright owner. For the purposes of this definition, "submitted"\n      means any form of electronic, verbal, or written communication sent\n      to the Licensor or its representatives, including but not limited to\n      communication on electronic mailing lists, source code control systems,\n      and issue tracking systems that are managed by, or on behalf of, the\n      Licensor for the purpose of discussing and improving the Work, but\n      excluding communication that is conspicuously marked or otherwise\n      designated in writing by the copyright owner as "Not a Contribution."\n\n      "Contributor" shall mean Licensor and any individual or Legal Entity\n      on behalf of whom a Contribution has been received by Licensor and\n      subsequently incorporated within the Work.\n\n   2. Grant of Copyright License. Subject to the terms and conditions of\n      this License, each Contributor hereby grants to You a perpetual,\n      worldwide, non-exclusive, no-charge, royalty-free, irrevocable\n      copyright license to reproduce, prepare Derivative Works of,\n      publicly display, publicly perform, sublicense, and distribute the\n      Work and such Derivative Works in Source or Object form.\n\n   3. Grant of Patent License. Subject to the terms and conditions of\n      this License, each Contributor hereby grants to You a perpetual,\n      worldwide, non-exclusive, no-charge, royalty-free, irrevocable\n      (except as stated in this section) patent license to make, have made,\n      use, offer to sell, sell, import, and otherwise transfer the Work,\n      where such license applies only to those patent claims licensable\n      by such Contributor that are necessarily infringed by their\n      Contribution(s) alone or by combination of their Contribution(s)\n      with the Work to which such Contribution(s) was submitted. If You\n      institute patent litigation against any entity (including a\n      cross-claim or counterclaim in a lawsuit) alleging that the Work\n      or a Contribution incorporated within the Work constitutes direct\n      or contributory patent infringement, then any patent licenses\n      granted to You under this License for that Work shall terminate\n      as of the date such litigation is filed.\n\n   4. Redistribution. You may reproduce and distribute copies of the\n      Work or Derivative Works thereof in any medium, with or without\n      modifications, and in Source or Object form, provided that You\n      meet the following conditions:\n\n      (a) You must give any other recipients of the Work or\n          Derivative Works a copy of this License; and\n\n      (b) You must cause any modified files to carry prominent notices\n          stating that You changed the files; and\n\n      (c) You must retain, in the Source form of any Derivative Works\n          that You distribute, all copyright, patent, trademark, and\n          attribution notices from the Source form of the Work,\n          excluding those notices that do not pertain to any part of\n          the Derivative Works; and\n\n      (d) If the Work includes a "NOTICE" text file as part of its\n          distribution, then any Derivative Works that You distribute must\n          include a readable copy of the attribution notices contained\n          within such NOTICE file, excluding those notices that do not\n          pertain to any part of the Derivative Works, in at least one\n          of the following places: within a NOTICE text file distributed\n          as part of the Derivative Works; within the Source form or\n          documentation, if provided along with the Derivative Works; or,\n          within a display generated by the Derivative Works, if and\n          wherever such third-party notices normally appear. The contents\n          of the NOTICE file are for informational purposes only and\n          do not modify the License. You may add Your own attribution\n          notices within Derivative Works that You distribute, alongside\n          or as an addendum to the NOTICE text from the Work, provided\n          that such additional attribution notices cannot be construed\n          as modifying the License.\n\n      You may add Your own copyright statement to Your modifications and\n      may provide additional or different license terms and conditions\n      for use, reproduction, or distribution of Your modifications, or\n      for any such Derivative Works as a whole, provided Your use,\n      reproduction, and distribution of the Work otherwise complies with\n      the conditions stated in this License.\n\n   5. Submission of Contributions. Unless You explicitly state otherwise,\n      any Contribution intentionally submitted for inclusion in the Work\n      by You to the Licensor shall be under the terms and conditions of\n      this License, without any additional terms or conditions.\n      Notwithstanding the above, nothing herein shall supersede or modify\n      the terms of any separate license agreement you may have executed\n      with Licensor regarding such Contributions.\n\n   6. Trademarks. This License does not grant permission to use the trade\n      names, trademarks, service marks, or product names of the Licensor,\n      except as required for reasonable and customary use in describing the\n      origin of the Work and reproducing the content of the NOTICE file.\n\n   7. Disclaimer of Warranty. Unless required by applicable law or\n      agreed to in writing, Licensor provides the Work (and each\n      Contributor provides its Contributions) on an "AS IS" BASIS,\n      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or\n      implied, including, without limitation, any warranties or conditions\n      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A\n      PARTICULAR PURPOSE. You are solely responsible for determining the\n      appropriateness of using or redistributing the Work and assume any\n      risks associated with Your exercise of permissions under this License.\n\n   8. Limitation of Liability. In no event and under no legal theory,\n      whether in tort (including negligence), contract, or otherwise,\n      unless required by applicable law (such as deliberate and grossly\n      negligent acts) or agreed to in writing, shall any Contributor be\n      liable to You for damages, including any direct, indirect, special,\n      incidental, or consequential damages of any character arising as a\n      result of this License or out of the use or inability to use the\n      Work (including but not limited to damages for loss of goodwill,\n      work stoppage, computer failure or malfunction, or any and all\n      other commercial damages or losses), even if such Contributor\n      has been advised of the possibility of such damages.\n\n   9. Accepting Warranty or Additional Liability. While redistributing\n      the Work or Derivative Works thereof, You may choose to offer,\n      and charge a fee for, acceptance of support, warranty, indemnity,\n      or other liability obligations and/or rights consistent with this\n      License. However, in accepting such obligations, You may act only\n      on Your own behalf and on Your sole responsibility, not on behalf\n      of any other Contributor, and only if You agree to indemnify,\n      defend, and hold each Contributor harmless for any liability\n      incurred by, or claims asserted against, such Contributor by reason\n      of your accepting any such warranty or additional liability.\n\n   END OF TERMS AND CONDITIONS\n\n   APPENDIX: How to apply the Apache License to your work.\n\n      To apply the Apache License to your work, attach the following\n      boilerplate notice, with the fields enclosed by brackets "[]"\n      replaced with your own identifying information. (Don\'t include\n      the brackets!)  The text should be enclosed in the appropriate\n      comment syntax for the file format. We also recommend that a\n      file or class name and description of purpose be included on the\n      same "printed page" as the copyright notice for easier\n      identification within third-party archives.\n\n   Copyright [yyyy] [name of copyright owner]\n\n   Licensed under the Apache License, Version 2.0 (the "License");\n   you may not use this file except in compliance with the License.\n   You may obtain a copy of the License at\n\n       http://www.apache.org/licenses/LICENSE-2.0\n\n   Unless required by applicable law or agreed to in writing, software\n   distributed under the License is distributed on an "AS IS" BASIS,\n   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.\n   See the License for the specific language governing permissions and\n   limitations under the License.\n'}
SOURCE_HASHES = {'notebooks/launch.py': '72179eb4e59baa4adbcab0fa3f8b56cccde7d6ca359a7f06e17d45efaeb14d7b', 'notebooks/take.py': '64b527642010d9b07d9ad3e9b1aeec112feecac14a1053b208cfb46033652e8a', 'notebooks/check-submission': '85cebc93df89a24942c08f7b45ac41bfdce926c9cf8c8c9ee3f2b730b39f0ac9', 'notebooks/extra-format.py': '6593250be3d89ee0942e01daf7251d0e5b351148786aa851d7f07dfe5dcac588', 'LICENSE': 'cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30'}
INPUT_SOURCES = {}
MEMBERS = {'invsqrt.kmb': {'sha256': 'af4698478fbad775a5a271690cf4c2d8783caf0b8d12048106d1973c4ac6862e', 'size': 479055}, 'dqi.kmb': {'sha256': '993c70386a3dde6664ecea36315db3aa60fb18a96dc714a18160cae3472378db', 'size': 529710680}, 'dfthcsos/angle_k_0.kmb': {'sha256': '2665ce00a1704f63e9d7d3532877568a86bd4d95a90d21e62fd1a9f81ff68298', 'size': 413385}, 'dfthcsos/angle_k_1.kmb': {'sha256': '4a551d80b9845030ff32fed85066de9d1d2aaf1629d4f560abf4a533f8848034', 'size': 410647}, 'dfthcsos/angle_k_2.kmb': {'sha256': '67fd7e8f917da9b52ff017787973e447bc3935c8fd768a1c8198d39aa1c6193f', 'size': 411019}, 'dfthcsos/angle_k_3.kmb': {'sha256': '0d96dcfd083d448eda6ae1156f9037a8f5c044e4db13b8fa4d0b4faf98a6269b', 'size': 408565}, 'dfthcsos/angle_k_4.kmb': {'sha256': 'a2b1bddb016684e770d237d4937abc3773015017a12177cc769217f02d928bb4', 'size': 362425}, 'dfthcsos/angle_k_5.kmb': {'sha256': 'e5a93b28520c35ce8244e2b79fe59ca9f06575ba1890d39788d8d4c5446e049b', 'size': 362028}, 'dfthcsos/angle_k_6.kmb': {'sha256': 'ccdcb391f67e720e53434a1c2deaa6d3499ef86cf8663db42523cca11775638e', 'size': 364878}, 'dfthcsos/angle_k_7.kmb': {'sha256': '7a4e30f7112cd70d5c1adb1a1b6861eb9ed548c3277ee2e80efb20e49382d5f7', 'size': 363581}, 'dfthcsos/angle_k_8.kmb': {'sha256': 'a04028ecf1002a9f7b43f2b6d4621d76d858264fca008661e22a18900b7268ff', 'size': 364774}, 'dfthcsos/angle_k_9.kmb': {'sha256': '60c4c540710a1ad71c4e67b48c84383902cd2c11bacf2c9408b44c57a52f0b5e', 'size': 363298}, 'dfthcsos/angle_k_10.kmb': {'sha256': 'e832d29420b4beffc017cc688b0d552354681162faf3cef0ac3b4732d33a4f28', 'size': 365906}, 'dfthcsos/angle_k_11.kmb': {'sha256': '91d72f75bc5d33feadc33635de06052314ee75c708abcf867e3a3374e8f6029d', 'size': 368374}, 'dfthcsos/angle_k_12.kmb': {'sha256': '1cc58e1bf53f1020cc46a1720f4dca9db8d82b56024a2ea0119486af6b9add41', 'size': 362461}, 'dfthcsos/angle_k_13.kmb': {'sha256': '167b7d5a45dcf09139dd31cd8283b8493cde0dbceeba72eea64970398e0d2b78', 'size': 363208}, 'dfthcsos/angle_k_14.kmb': {'sha256': '929035ff8206ad7879d6255cddf25cd3e46f54a67984aa765a50d84d78550caa', 'size': 365401}, 'dfthcsos/submission.npz': {'sha256': 'de4ea64e9612ab2f2fd1c6bcad289f37cf67a48734fd6e56b7228c7545439afa', 'size': 1863164}}
EXPECTED = {'invsqrt': {'status': 'PASS', 'score': 97921.57954257724, 'toffoli_equivalent': 1579.3803152028586, 'toffoli_count': 1281.664677182505, 'max_toffoli_count': 1537, 't_count': 11.49925652582998, 'rotation_count': 41.0, 'rotation_eps': 2.434041480874084e-13, 'num_qubits': 62, 'reaction_depth': 851, 'num_ops': 48262, 'verified_shots': 200540928, 'worst_error_over_tolerance': 0.9993237694056958, 'worst_x': 161, 'circuit_sha256': 'af4698478fbad775a5a271690cf4c2d8783caf0b8d12048106d1973c4ac6862e'}, 'dqi': {'status': 'PASS', 'score': 375373377713.4055, 'm': 4095, 'n': 70, 'degree': 12, 'r': 2016, 'verified_shots': 102400, 'value_errors': 0, 'phase_errors': 0, 'empirical_error_rate': 0.0, 'effective_error_rate': 0.0008660587301657926, 'log2_delta': -128.0, 'repetition_factor': 1.1912604648115832, 'mean_error_weight': 31.046737331746634, 'toffoli_count': 396918.49083984375, 'max_toffoli_count': 397191, 'reaction_depth': 5866, 'num_ops': 58336065, 'num_qubits': 891, 'num_bits': 101624, 'circuit_sha256': '993c70386a3dde6664ecea36315db3aa60fb18a96dc714a18160cae3472378db'}, 'dfthcsos': {'status': 'PASS', 'score': 309207580.1417442, 'lambda_eff': 47.184435521462085, 'toffoli_count': 15347.0, 'num_qubits': 427, 'brot': 8, 'batch_size': 5, 'num_circuits': 15, 'reaction_depth': 165, 'num_ops': 624857, 'verified_shots': 78080, 'submission_sha256': '35a5c8fbb7289ec02edc4db939450304b2cea127e33da1af31f86f4d66ac7203'}}
PARTS = {'invsqrt': 'af4698478fbad775a5a271690cf4c2d8783caf0b8d12048106d1973c4ac6862e', 'dqi': '993c70386a3dde6664ecea36315db3aa60fb18a96dc714a18160cae3472378db', 'dfthcsos': '35a5c8fbb7289ec02edc4db939450304b2cea127e33da1af31f86f4d66ac7203'}
REFERENCE = {'invsqrt': 2076774.233715, 'dqi': 24439463583672.93, 'dfthcsos': 3355599588.3155375}
BLOCKS = {'invsqrt': {'id': 'forcebits-af469847', 'title': "Our version 33 circuit, with Kirill Tymchishin's two idle phase bits forced to zero", 'part': 'af4698478fbad775a5a271690cf4c2d8783caf0b8d12048106d1973c4ac6862e'}, 'dqi': {'id': 'yoyobar-993c7038', 'title': "yoyobar's third rewrite of Syed Asad Ali's 891-qubit decoder", 'part': '993c70386a3dde6664ecea36315db3aa60fb18a96dc714a18160cae3472378db'}, 'dfthcsos': {'id': 'refit-35a5c8fb', 'title': "Our refit of the weights, one pass further than version 35, on qwertykeypadapple's kernel-search circuits for Lera's compact-group table", 'part': '35a5c8fbb7289ec02edc4db939450304b2cea127e33da1af31f86f4d66ac7203'}}
BUILDS = {}
NOTEBOOK = {'assembled_from_commit': 'bb09edf63a4ef0acd26cd67c1db785de3f3889ae', 'blocks_changed_since_commit': True}

import hashlib, importlib.metadata, json, math, os, pathlib, platform, shutil, subprocess, sys, tempfile, time, zipfile
sys.dont_write_bytecode = True
START_TIME = time.monotonic()
INPUT = pathlib.Path(os.environ.get('QCOMP_INPUT', '/kaggle/input'))
WORKING = pathlib.Path(os.environ.get('QCOMP_WORKING', '/kaggle/working'))
WORKING.mkdir(parents=True, exist_ok=True)
SESSION = pathlib.Path(tempfile.mkdtemp(prefix='qcomp-'))
ROOT, OUT = SESSION / 'source', SESSION / 'build'
SUB = OUT / 'submission'
(ROOT / 'data').mkdir(parents=True)
SUB.mkdir(parents=True)
# Use at most the Kaggle CPU budget, one numerical-library thread per process.
if hasattr(os, 'sched_getaffinity'):
    affinity = sorted(os.sched_getaffinity(0))[:4]
    os.sched_setaffinity(0, affinity)
else:
    affinity = list(range(min(4, os.cpu_count() or 1)))
WORKERS = len(affinity)
for key in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
    os.environ[key] = '1'
TIMINGS = []


def sha256(path):
    with open(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


folders = [p.parents[1] for p in sorted(INPUT.rglob('kickmix.so')) if p.parent.name == 'kickmix']
# A dataset may carry its own copies of Kickmix: the official inputs are the first folder whose files all match
# their pinned SHA-256.
COMP = next((folder for folder in folders if all(
    (folder / name).is_file() and sha256(folder / name) == digest for name, digest in COMPETITION_FILES.items())), None)
assert COMP, f'No folder holds the official inputs with their pinned SHA-256; Kickmix found in {folders}'
assert sys.version_info[:2] == (3, 13), 'Select the pinned Python 3.13 CPU image for kickmix.so'
(ROOT / 'data/comp').symlink_to(COMP)
for name, body in SOURCES.items():
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding='utf-8')
    assert sha256(path) == SOURCE_HASHES[name], name
# Block files too large to embed come from an attached dataset or notebook output, public or private: each is found
# among the inputs by name, size and SHA-256.
for name, want in INPUT_SOURCES.items():
    path = ROOT / name
    found = next((p for p in sorted(INPUT.rglob(path.name)) if p.is_file() and p.stat().st_size == want['size']
                  and sha256(p) == want['sha256']), None)
    assert found, f'{name}: no input file has SHA-256 {want["sha256"]}; attach the inputs the Run section names'
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(found, path)
    print(f'{path.name} taken from {found}')
(ROOT / 'members.json').write_text(json.dumps(MEMBERS))


def run(*args, record):
    """Run one embedded script or official verifier in its own Python, keeping stdout as a record."""
    started = time.monotonic()
    result = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'notebooks/launch.py'), *map(str, args)],
                            cwd=ROOT, capture_output=True, text=True)
    TIMINGS.append({'command': list(map(str, args)), 'seconds': time.monotonic() - started,
                    'returncode': result.returncode})
    (OUT / record).write_text(result.stdout)
    (OUT / (record + '.stderr')).write_text(result.stderr)
    print(f'{pathlib.Path(str(args[0])).name}: {TIMINGS[-1]["seconds"]:.1f} s', flush=True)
    if result.returncode:
        print(result.stdout[-5000:], result.stderr[-5000:])
        raise RuntimeError(f'{args[0]} exited {result.returncode}')
    return result.stdout


BUILT = OUT / 'built'


def build(task):
    """Build a block's member, one file or a folder of them, from its embedded source, the way its authors run it,
    and check the SHA-256 of every file."""
    spec = BUILDS[task]
    target = BUILT / spec['member']
    target.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    # Our own code, run as a script: its folder leads sys.path, and Kickmix comes from the authenticated files.
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'data/comp/kickmix'), 'PYTHONNOUSERSITE': '1'}
    result = subprocess.run([sys.executable, '-B', str(ROOT / spec['script']), str(target)], cwd=SESSION, env=env,
                            capture_output=True, text=True)
    TIMINGS.append({'command': ['build', spec['script']], 'seconds': time.monotonic() - started,
                    'returncode': result.returncode})
    (OUT / f'{task}.build.txt').write_text(result.stdout)
    (OUT / f'{task}.build.stderr').write_text(result.stderr)
    if result.returncode:
        print(result.stdout[-5000:], result.stderr[-5000:])
        raise RuntimeError(f'{spec["script"]} exited {result.returncode}')
    names = [name for name in MEMBERS if name == spec['member'] or name.startswith(spec['member'] + '/')]
    assert names, spec['member']
    for name in names:
        digest = sha256(BUILT / name)
        assert digest == MEMBERS[name]['sha256'], f'{name}: built {digest}, not the verified file'
    record = json.loads(target.with_suffix('.build.json').read_text())
    if 'summary' in record:
        print(f'{spec["member"]} built in {TIMINGS[-1]["seconds"]:.0f} s: {record["summary"]}')
    else:
        print(f'{spec["member"]} built in {TIMINGS[-1]["seconds"]:.0f} s: Q {record["Q"]}, static Toffolis '
              f'{record["T_static"]:,}, SHA-256 {digest[:12]}..., the circuit the verifier passed')
    return record


VERIFIERS = {'invsqrt': ['data/comp/verifiers/invsqrt/verify_submission_invsqrt.py', 'invsqrt.kmb', '--max-workers'],
             'dqi': ['data/comp/verifiers/dqi/verify_submission_dqi.py', 'dqi.kmb', '--max-workers'],
             'dfthcsos': ['data/comp/verifiers/dfthcsos/verify.py', 'dfthcsos']}
CHECKED = ['status', 'score', 'num_qubits', 'toffoli_count', 'verified_shots', 'toffoli_equivalent', 't_count',
           'rotation_count', 'repetition_factor', 'value_errors', 'phase_errors', 'lambda_eff']


def verify(task):
    """Run the unmodified official verifier at its defaults and compare with the recorded run."""
    script, target, *workers = VERIFIERS[task]
    report = json.loads(run(script, SUB / target, *([*workers, WORKERS] if workers else []),
                            record=f'{task}.official.json'))
    expected = EXPECTED[task]
    assert report['status'] == 'PASS', report
    for key in CHECKED:
        if key in expected:
            assert math.isclose(report[key], expected[key], rel_tol=1e-9, abs_tol=1e-12) if isinstance(
                expected[key], float) else report[key] == expected[key], (task, key, report[key], expected[key])
    part = report.get('circuit_sha256', report.get('submission_sha256'))
    assert part == PARTS[task], (task, part)
    print(f'{task}: PASS | Q {report["num_qubits"]} | cost {report["score"]:,.6g} | '
          f'{REFERENCE[task] / report["score"]:.4f}x below the reference | same as the recorded run')
    return report


ENVIRONMENT = {'python': platform.python_version(), 'platform': platform.platform(),
               'packages': {name: importlib.metadata.version(name) for name in ['numpy', 'scipy']},
               'workers': WORKERS, 'affinity': affinity, 'numeric_threads': 1,
               'kickmix_sha256': sha256(COMP / 'kickmix/kickmix.so'),
               'seed': 'official default: derived from each circuit SHA-256, empty salt', **NOTEBOOK}
print(f'{len(COMPETITION_FILES)} official input files authenticated; {len(SOURCES)} embedded files written; '
      f'workers {WORKERS}; no network, installs or training')

```

> **Code (DE):** take.py: kopiert die gepinnten Submit-Mitglieder (invsqrt.kmb, dqi.kmb, dfthcsos/*) aus den Inputs in das Submit-Verzeichnis und meldet, woher jedes Byte kam.

```python

taken = json.loads(run('notebooks/take.py', INPUT, SUB, ROOT / 'members.json', BUILT, record='take.json'))
for name, where in taken['taken'].items():
    print(f'{name:26} {MEMBERS[name]["sha256"][:12]}  from {where}')

```

> **Code (DE):** Fährt je Task den offiziellen Verifikator (oder liest den protokollierten Lauf, wenn VERIFY=False) und vergleicht jeden Wert mit EXPECTED.

```python

VERIFY = False  # False: report the recorded official runs instead of rerunning them
REPORTS = {}
for task in REFERENCE:
    REPORTS[task] = verify(task) if VERIFY else EXPECTED[task]

```

> **Code (DE):** Prüft Formatregeln, packt submission.zip mit fixierten Container-Metadaten, liest es zurück, rehasht alle 28 Mitglieder und berechnet den geometrischen Mittelwert der drei Ratios.

```python

print(run('notebooks/check-submission', SUB, record='check-submission.txt').splitlines()[-1])
extra = json.loads(run('notebooks/extra-format.py', SUB, record='extra-format.json'))
names = sorted(str(p.relative_to(SUB)) for p in SUB.rglob('*') if p.is_file())
assert names == sorted(MEMBERS), names
actual = {name: sha256(SUB / name) for name in names}
assert all(actual[n] == MEMBERS[n]['sha256'] for n in names), 'Output member hash mismatch'
with zipfile.ZipFile(WORKING / 'submission.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    # Fixed container metadata, so the same members always give the same archive.
    for name in names:
        info = zipfile.ZipInfo(name, date_time=(2026, 10, 27, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.create_system = 3
        info.external_attr = 0o100644 << 16
        info._compresslevel = 6
        with (SUB / name).open('rb') as source, archive.open(info, 'w', force_zip64=True) as target:
            shutil.copyfileobj(source, target, length=1 << 20)
with zipfile.ZipFile(WORKING / 'submission.zip') as archive:
    assert sorted(archive.namelist()) == names
    for name in names:
        with archive.open(name) as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == actual[name], name
for name, digest in COMPETITION_FILES.items():
    assert sha256(COMP / name) == digest, f'Official input changed during the run: {name}'
gm = math.prod(REFERENCE[t] / REPORTS[t]['score'] for t in REFERENCE) ** (1 / 3)
summary = {'status': 'PASS', 'blocks': BLOCKS, 'verifiers': REPORTS, 'member_sha256': actual,
           'geometric_mean': gm, 'archive_sha256': sha256(WORKING / 'submission.zip'),
           'archive_bytes': (WORKING / 'submission.zip').stat().st_size, 'environment': ENVIRONMENT,
           'timings': TIMINGS, 'elapsed_seconds': time.monotonic() - START_TIME}
(WORKING / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
(WORKING / 'submission-members.sha256').write_text(''.join(f'{actual[n]}  {n}\n' for n in names))
for task, r in REPORTS.items():
    print(f'{task:9} {BLOCKS[task]["title"]}: cost {r["score"]:,.6g}, ratio {REFERENCE[task] / r["score"]:.4f}')
print(f'{len(names)} members, each byte-identical to its block; format checks and ZIP read-back PASS.')
print(f'Geometric mean of the three ratios: {gm:.5f} (official verifiers at their defaults; '
      f'the leaderboard measures again)')
print(f'Elapsed {summary["elapsed_seconds"]:.0f} s | {WORKING / "submission.zip"}')

```

## Credits and licence

- **invsqrt:** **Kirill Tymchishin (kirilltym)**: the two measurements that read a wire already zero, and their bits set to zero so that their branches never run, in his public circuit of 4 November. **qiuqiuh**: the same saving as our rank cut, two Toffolis fewer at one accumulator site in another placement, in [QCC Refresh v65w-sx-sy7-inverse](https://www.kaggle.com/code/qiuqiuh/qcc-refresh-v65w-sx-sy7-inverse), whose only version ran at 09:09 UTC on 4 November, before ours; we found ours independently by our census and first saw theirs at 11:50 UTC. **Claude**: that census and the rank cut, our version 33, and the port of the two lines. On **Alex Chilton (alexchilton)**'s rewrite of that site, five Toffolis as four, on our circuit of version 32: **Claude**'s ladder and window splice on **Syed Asad Ali (syed3000)**'s circuit, which is the invsqrt line of **mrmeows**, **Akmal Xodarev (busyaprime)** and **yoyobar**, with **Ahmed Berat Özer**'s phase patch, **Ehan Mallick**'s two AND merges and **Kirill Tymchishin (kirilltym)**'s five AND merges, as our block `ladder-15118bfa` credits them.
- **DQI:** As yoyobar's notebook states: **yoyobar**: one further product-cache rewrite of its `748b01a7…`, which saves one more CCZ, 1,481 → 1,480, with the CCX, CSWAP and qubit counts unchanged, so 397,192 → 397,191 static paid gates. As Alex Chilton's notebook states for `748b01a7…`: **yoyobar**: one further paid Toffoli-equivalent saving on its `06aa8ca2…` rewrite of Syed Asad Ali's 891-qubit decoder, shipped first in **Isabe11aM00re**'s portfolio. Below it, as yoyobar's notebook states for `06aa8ca2…`: **yoyobar**: a verified gate-level rewrite of the decoder below that removes one CCZ, 1,483 → 1,482, with the 382,647 CCX and 13,064 CSWAP unchanged, so 397,194 → 397,193 Toffoli-equivalent gates at most; it does not introduce a new decoder. The decoder comes from **Syed Asad Ali (syed3000)**'s notebook [VQCC 24.43 Portfolio](https://www.kaggle.com/code/syed3000/vqcc-24-43-portfolio), which states: with AI agents, a decoder of the C1 line, built with GPT-6 Astra on **SomeJoint**'s kit, with SomeJoint's narrow return; a port of the flag carry of SomeJoint's 892-qubit line, an idea of **Ali Haydar Özdağ**, which takes the width from 902 to 891; measurement-based erasure of recompute steps and flag uncomputes; conditionally clean AND ladders after Khattar and Gidney (2024); and exact product caching, with one rare high-weight error class handled approximately at a small, priced failure rate. Verified there with **manwithacat**'s Rust kickmix engine.
- **Chemistry:** **qwertykeypadapple**: the fifteen angle circuits, compiled by its own kernel-relation search on Lera's tensor lookup compiler, in [QCC Kernel Search 24.65](https://www.kaggle.com/code/qwertykeypadapple/qcc-kernel-search-24-65) (Apache 2.0); that notebook credits Dmitrii Gluzdov's public description of plan and relation search on this compiler ([Quantum Circuit Compilation from Source](https://www.kaggle.com/code/dmitriigluzdov/quantum-circuit-compilation-from-source)) and heliosli for the scratch top-bit idea. **Lera (marculera)**: the tensor lookup compiler, after mrmeows's cached-monomial emitter and our coded low bit, and the DF-THC compact groups pipeline that made this (8, 143, 45) table, its angle words and codes ([DF-THC 10x: Compact Groups From the Hamiltonian](https://www.kaggle.com/code/marculera/df-thc-10x-compact-groups-from-the-hamiltonian)); Lera credits Ahmed Berat Özer (ahmedberatozer), kozykappa, Kozykorpesh and Sumit Chongder, Artem1410 (anazemcev), Phuc Thai, haideptry, somejoint, mrmeows, heliosli, lightningv08, Michael Rustad, k256net and Dmitrii Gluzdov. **Ayodeji (ayodejiibrahimlateef)**: the public notebook that put the table on Kaggle, [Quantum Portfolio | 24.56308 Local](https://www.kaggle.com/code/ayodejiibrahimlateef/quantum-portfolio-24-56308-local). **Claude**: our refit of `W` and `H2_I` with the words, circuits and every other array fixed, by the fixed-word chain our build loop of AI agents wrote on 30 October (exact gauge and whitened tangent steps).

**Inherited lineage**, as the fullest public chain names it: Agniv Banerjee (SomeJoint), Dmitrii Gluzdov, ViberTeam / Artem1410 / anazemcev, manwithacat, Phuc Thai (DePie), Kozykorpesh (kozykappa), Michael Rustad, Akmal Xodarev (busyaprime), marsyas, Sumit Chongder, Rudra Bhaskar, Zongao Bian, Mizero Lucky Gall, Gu et al. and Guang Hao Low.

Thanks to **Google Quantum AI** and the competition authors for the tasks, the verifiers and Kickmix, which keep their own terms. The circuits keep their authors' licences; the notebook code is Apache-2.0. If we have left anyone out of a chain, tell us in the comments and we will add them.

---

## 🔑 Kern-Konzept in 3 Sätzen

Die Angle-Wörter und die Loaders bleiben byte-identisch; nur die kontinuierlichen Gewichte W und H2_I werden neu gefittet, weil die Gewichte zu den Wörtern passen und nicht zu den Circuits. Ein geschützter Tangent-Step mit exakten Gauge-Sweeps dazwischen gibt die anfängliche 3.19-mHa-Marge über dem Limit frei und lässt den zweiten Fehler bis auf wenige 10⁻⁹ Ha an seine Grenze rücken. So fällt λ_eff Pass für Pass: v34 (3. Pass) 47.184697 → v35 (4.) 47.184606 → dieser Lauf (5.) 47.184436.

## 📐 Die Zahlen die zählen

| Parameter | Wert | Bedeutung |
|-----------|------|-----------|
| GM (lokal) | 24.65394 | offizielle Verifikatoren, Default-Seeds |
| Chemie λ_eff | 47.184436 | 5. Refit-Pass |
| Chemie T / Q | 15,347 / 427 | Toffolis pro Step / Qubits |
| Fehler | 11.195 & 19.999999 mHa | gegen 20-mHa-Limit |
| E_gap | 3.9148990 Ha | muss ≥ 3.914898 Ha |
| Cost / Ratio | 309,207,580 / 10.8523 | Reference/cost |
| Loaders | 303 (k0–3) / 281 (k4–14) Toffolis | qwertykeypadapples Kernel-Search |
| Tabelle | Lera (8,143,45), brot=8, 15 Circuits | Compact-Group |
| Refit-Kette | 47.266713 → … → 47.184436 | guarded tangent steps + gauge sweeps |
| invsqrt / DQI | Q62 ratio 21.2085 / Q891 ratio 65.1071 | die anderen beiden Tasks |

## 📝 Lern-Notizen (füll das selbst aus)

- [ ] DF-THC Factorization verstanden: ...
- [ ] (R,B,C) Tabelle nachvollziehbar: ...
- [ ] Loader-Kosten verstanden: ...
- [ ] λ_eff und was es physikalisch bedeutet: ...
- [ ] Verbindung zu invsqrt/DQI: ...
- [ ] Frage die ich noch habe: ...
