# qvc-008 — STATUS

**SUBMISSION-READY: yes**

## Source

- Dataset: **`heliosli/qcc-circuits-live`** (Kaggle, apache-2.0), downloaded 2026-11-04 to `work/qvc008/src/`
- Manifest portfolio: **`v65w_sx_sy7`** (asserted, matches heliosli's notebook "The dataset is public now. Enjoy!")
- Salt: `notebook-verification`
- All 18 files extracted per manifest (`dqi.kmb` stored as `dqi.kmb.xz`, lzma-decompressed) and SHA-256-verified against the manifest. No mismatches.
- Zip layout mirrors prior submissions (`invsqrt.kmb`, `dqi.kmb`, `dfthcsos/angle_k_0..14.kmb`, `dfthcsos/submission.npz`).

## Per-file SHA-256 (verified on disk AND inside qvc-008.zip)

| file | sha256 |
|---|---|
| invsqrt.kmb | `15118bfa94a4084cd853c752100442ec41d8a80bae0f483af98a0cac2677e64c` |
| dqi.kmb | `748b01a7a07662c3f7e389b844e313a3d55dfb3b3d993414e5ad3dfac6fe154c` |
| dfthcsos/angle_k_0.kmb | `956dc0b494a85b72aacc830b45e10e52a65a11454207fb76072b43c050016f8e` |
| dfthcsos/angle_k_1.kmb | `cf0291d59ba246eb2bbf61f56b7128a69bdca36d740f2bf8487fe4b0fa77c88c` |
| dfthcsos/angle_k_2.kmb | `7d2038cea60c2a9484d51e4ea60521e254dd4c3e2f29133ed62a101a3d088557` |
| dfthcsos/angle_k_3.kmb | `9937a233c65981c29aa923f2821819dac54faac17a55d1dfc06353bff09ba681` |
| dfthcsos/angle_k_4.kmb | `063aa910bb8e3f3cd4864762ea4accecc4f043ddf6ab8d55dc3461a858af88fb` |
| dfthcsos/angle_k_5.kmb | `b381c166926b4196ab26e1a428bf8d530ce18af86453a5c9cb8824a8f0980c99` |
| dfthcsos/angle_k_6.kmb | `6dd19bf59ca80deacf851f42eeee3d785d8334346642bb94e22c99904060010c` |
| dfthcsos/angle_k_7.kmb | `2375754fa132843532bf075b56bf9a4d3ab877cedbb8cc22777a59867cd850f8` |
| dfthcsos/angle_k_8.kmb | `5708aea25df768f3c58daa759af70c5e4cadeb38b7e3680d67e93312cba5607e` |
| dfthcsos/angle_k_9.kmb | `f1f1cc1cbe2ad7d74a425888bdee3780956c2ba555b12e5f00b2aaf71b6c7cc1` |
| dfthcsos/angle_k_10.kmb | `8c31a64784c3d0ecb6bf71c5e67a4f27bdf63ce0f4dd4e213ff4ee20029d9ba9` |
| dfthcsos/angle_k_11.kmb | `402ebdf216abae95c91ae2aee37078a2bbb13ef59bf0db66f4af9f057161e310` |
| dfthcsos/angle_k_12.kmb | `7707330d587dfc5609e3f2b7ebca3dfacf64afb77d462050457671e80bcc168c` |
| dfthcsos/angle_k_13.kmb | `451cc5acbe1bbefd0affef3622a7e611eb7d3cd784c6d26a59d7312354f91c39` |
| dfthcsos/angle_k_14.kmb | `c36fef91c85080a9b686c8c81d995c0569fead3f79960673d7d26ccce9dd3217` |
| dfthcsos/submission.npz | `85c420b68e0aaf58354954a93aea4d231db33f7aa5be9f82b883a3277bbe760a` |

## Verification (official verifiers, unmodified, default shot counts, salt from manifest)

| task | status | cost (score) | ratio (ref/cost) | target | details |
|---|---|---:|---:|---:|---|
| invsqrt | PASS | 98185.11378958142 | **21.15162** | 21.1516 | 62 qubits, 1583.6 Toffoli-eq, 64 shots/x × 27648 x = 1,769,472 shots |
| dqi | PASS | 375374152177.88104 | **65.10694** | 65.1069 | 891 qubits, 396,919 mean Toffolis, 0 value / 0 phase errors, repetition_factor 1.19126, m=4095 n=70 degree=12, 102,400 shots |
| dfthcsos | PASS | 312443243.84047496 | **10.73987** | 10.740 | λ_eff 47.0214, 15,525 Toffolis, 428 qubits, 87,232 verified shots (64/address) |

Reference costs (from manifest): invsqrt 2076774.233715282 · dqi 24439463583672.93 · dfthcsos 3355599588.3155375.

## Local GM

GM = (21.15162 × 65.10694 × 10.73987)^(1/3) = **24.54652** (target ≈ 24.54651 ✓)

## Artifact

- Path: `/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/work/qvc008/qvc-008.zip`
- Size: 28,366,980 bytes (27.1 MiB)
- Members: exactly 18 (re-verified from inside the zip against manifest SHA-256)
- Compression: ZIP_DEFLATED, manifest order (same as heliosli's notebook / prior qvc zips)

## Reproducibility

```bash
.venv/bin/kaggle datasets download -d heliosli/qcc-circuits-live -p work/qvc008/src --unzip
.venv/bin/python work/qvc008/extract.py        # 18 files, SHA-verified
.venv/bin/python work/qvc008/verify_all.py dqi # ~145 s (slowest)
.venv/bin/python work/qvc008/verify_all.py invsqrt   # ~143 s
.venv/bin/python work/qvc008/verify_all.py dfthcsos  # ~14 s
.venv/bin/python work/qvc008/package.py        # qvc-008.zip + in-zip SHA check
```

Raw results: `work/qvc008/verify_results.json`, `work/qvc008/verify_dqi.log`.
