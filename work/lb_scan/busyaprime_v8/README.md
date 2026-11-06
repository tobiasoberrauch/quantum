# 33 QCC V8 members, version 9: the 18 files of our notebook V14

The 18 files of the zip our notebook busyaprime/lb-22-72431-22x-cheaper-than-google-s-circuits writes from version 14
on, byte for byte. One file is ours: `dqi.kmb`, SomeJoint's 892-qubit decoder of 2026-11-01 16:58 UTC with two exact rewrites by us:
24 clearing blocks replaced by measurement-based uncomputation (12 of them the sites of manwithacat's HW-07, 12 more
three-input flags), then exact product caching, run twice. Mean Toffolis per shot 399,969.71 against 402,772.30 for their file
at its default seed (-0.70%), still 892 qubits. The other 17 files are other authors' public circuits, unchanged.

| file here | path in submission.zip | bytes | SHA-256 |
|---|---|---:|---|
| `dfthcsos__angle_k_0.kmb` | `dfthcsos/angle_k_0.kmb` | 451,672 | `8b698f14b339bd282e0332a1f105b41d60bfa5218d107c775db2532fbd88f774` |
| `dfthcsos__angle_k_1.kmb` | `dfthcsos/angle_k_1.kmb` | 448,085 | `0d16c5108e48e40931d87f1e3ee12d4486e932b341989ce909a47b032e5a7745` |
| `dfthcsos__angle_k_10.kmb` | `dfthcsos/angle_k_10.kmb` | 400,612 | `e2668bf5666ca1e49541bef7a255b2100a8a513188fadef3a8dd4e892cfe2094` |
| `dfthcsos__angle_k_11.kmb` | `dfthcsos/angle_k_11.kmb` | 406,276 | `5f69f385cb2040e7124e11e1cedb7cea0e0ffa6ad13abe81b2a337744cb9c2ac` |
| `dfthcsos__angle_k_12.kmb` | `dfthcsos/angle_k_12.kmb` | 400,502 | `f86995a0ea1990a11a43f1812f47e00a77658f71cc544d44bd5003e616111272` |
| `dfthcsos__angle_k_13.kmb` | `dfthcsos/angle_k_13.kmb` | 401,708 | `4390c8114e191b0c74ccd8b6302e5e0ded4e8cb412a3f146eea9887551658876` |
| `dfthcsos__angle_k_14.kmb` | `dfthcsos/angle_k_14.kmb` | 401,890 | `9e596deb120f20d1c92c350456ce9847314ba943a4d196e7942bac518a229f6c` |
| `dfthcsos__angle_k_2.kmb` | `dfthcsos/angle_k_2.kmb` | 451,996 | `b7b73491d3aeb59c70d023704df9f2ad69eb96c9d1f9e9920d33d60bd7852d11` |
| `dfthcsos__angle_k_3.kmb` | `dfthcsos/angle_k_3.kmb` | 456,266 | `c2437ad406d3772e961e7229580fba7b68c036b97ce36b4067c865e3af729f00` |
| `dfthcsos__angle_k_4.kmb` | `dfthcsos/angle_k_4.kmb` | 397,777 | `0df35ae1cb26d3bc09f022b2a397a8b07e5c322283d2c8cf0a53a4bb11b9dd47` |
| `dfthcsos__angle_k_5.kmb` | `dfthcsos/angle_k_5.kmb` | 401,580 | `a9a649997bf0696a659c8cbf9e778f92bee2816b6212febc898ed51450ae42c3` |
| `dfthcsos__angle_k_6.kmb` | `dfthcsos/angle_k_6.kmb` | 404,097 | `715673382c491b796865dbba235687eafebd16c745872d20f7ae1808f88a62ae` |
| `dfthcsos__angle_k_7.kmb` | `dfthcsos/angle_k_7.kmb` | 404,041 | `31e004f932d42750e1dda98abdf3e0097941cb1b1bbd353ed692e52098119cfb` |
| `dfthcsos__angle_k_8.kmb` | `dfthcsos/angle_k_8.kmb` | 400,918 | `046ac97b8c6ac9e1895a1da5dc89ea5df55bf487b1822d2ba11697c948145ff9` |
| `dfthcsos__angle_k_9.kmb` | `dfthcsos/angle_k_9.kmb` | 402,097 | `10c37a55ab902357cf60c5cf529de0eec9e9497a03f0b2ad7a9888d26d9c1e63` |
| `dfthcsos__submission.npz` | `dfthcsos/submission.npz` | 2,033,028 | `335c08fcb6c121fdd767516fd637b6a8ba31287723c88221ef54cabe9357e432` |
| `dqi.kmb` | `dqi.kmb` | 579,768,900 | `92750bd64525924ef84c8cd1b379b2c2d3914d87347bbe1bc40c804efff3ccdc` |
| `invsqrt.kmb` | `invsqrt.kmb` | 468,731 | `bce2948ff24e20fe59666d131f7fc4316a905103937272c52fdd39d494b6fe47` |

## Credits

| author | what | source | licence |
|---|---|---|---|
| **busyaprime** (Akmal Xodarev) | exact product caching on the DQI decoder (`dqi.kmb`); earlier, the 63-qubit invsqrt line (XAG2C) the invsqrt file descends from | this dataset; [notebook](https://www.kaggle.com/code/busyaprime/lb-22-72431-22x-cheaper-than-google-s-circuits) | Apache 2.0 |
| manwithacat | the clean two-wire ladder for measurement-based uncomputation of six-input flags (Hedge Wizardry HW-07), used at 12 of our 24 sites | [notebook](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook) | Apache 2.0 (dataset metadata) |
| Ahmed Berat Ozer | the idea of product caching on the DQI line (a Toffoli whose product was computed earlier becomes a CNOT from a cached copy), as manwithacat's briefing of 2026-10-31 describes his 900-qubit circuit; the invsqrt phase patch | [discussion](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion/754605) | idea; his files are not in this zip |
| SomeJoint (Agniv Banerjee's team) | the 892-qubit DQI decoder our `dqi.kmb` is built on, byte for byte before our caching; their notebook credits GPT-6 Astra Pro, Claude, Ali Haydar Ozdag (flag carry), yoyobar (one-carry history) and the earlier decoder line | [notebook](https://www.kaggle.com/code/somejoint/quantum-circuits-23-85-local-gm-892-qubit-dqi), output of 2026-11-01 16:58 UTC; [dataset](https://www.kaggle.com/datasets/somejoint/qcc-dqi-892-q26) | Apache 2.0 (dataset metadata, read 2026-11-01 18:13 UTC) |
| Ehan Mallick, yoyobar, Ahmed Berat Ozer, mrmeows | `invsqrt.kmb`, unchanged: Ehan Mallick's two 3-to-2 AND merges on yoyobar's 62-qubit circuit, after Ahmed Berat Ozer's phase patch and the busyaprime and mrmeows line | as heliosli's output of 2026-11-01 08:18 UTC ships it ([notebook](https://www.kaggle.com/code/heliosli/the-dataset-is-public-now-enjoy), [dataset](https://www.kaggle.com/datasets/heliosli/qcc-circuits-live)) | Apache 2.0 (dataset metadata) |
| heliosli; Lera (marculera); Dmitrii Gluzdov; manwithacat; Ahmed Berat Ozer | the 16 chemistry files, unchanged: Lera's second (9, 143, 40) factorization, its words and angle circuits k = 1 to 13; the circuits k = 0 and 14 by Dmitrii Gluzdov as manwithacat assembled them; table weights by heliosli, continuing Ahmed Berat Ozer's refinement (as heliosli's notebook credits them) | [heliosli's notebook](https://www.kaggle.com/code/heliosli/the-dataset-is-public-now-enjoy), output of 2 November 00:13 UTC ([dataset](https://www.kaggle.com/datasets/heliosli/qcc-circuits-live)) | Apache 2.0 (dataset metadata) |
| Google Quantum AI | the three verifiers and kickmix, unchanged | [competition data](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/data) | Apache 2.0 (`verifiers/LICENSE.txt`) |

See NOTICE.md for licences.
