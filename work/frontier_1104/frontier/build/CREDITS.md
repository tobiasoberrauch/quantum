# Credits for frontier/build/submission.zip

All three components are public Kaggle work by others. This build only selects them; nothing here was compiled by us.
Licences are as stated by the sources on 2026-11-05. Flags are listed below.

Official verifier, salt "notebook-verification", re-extracted from the zip: invsqrt 21.208526, dqi 65.113949,
dfthcsos 11.027334, GM 24.786680.

## invsqrt.kmb (sha256 af4698478fbad775a5a271690cf4c2d8783caf0b8d12048106d1973c4ac6862e)

- Author: Agniv Banerjee (SomeJoint) version 33 circuit with Kirill Tymchishin's two forced idle phase bits.
- Sources: https://www.kaggle.com/datasets/somejoint/qcc-ladder-parts (Kaggle licence metadata: Apache-2.0),
  https://www.kaggle.com/code/somejoint/quantum-circuits-24-59-local-gm-chem-refit,
  https://www.kaggle.com/code/kirilltym/quantum-circuits-four-loaders-eight-toffolis
- Lineage as credited upstream: Kirill Tymchishin, qiuqiuh, SomeJoint, Alex Chilton, Leo Tang, Malachi W. Moody,
  Syed Asad Ali, Isabe11aM00re, Ehan Mallick, yoyobar, Akmal Xodarev (busyaprime), mrmeows / team selenium,
  Phuc Thai / DePie, Dmitrii Gluzdov, marsyas, Ahmed Berat Ozer.

## dqi.kmb (sha256 1c43b7ff2fcf2aaa9a4e13b276cdf6e621a5dbb8f5e6119856cad3c807ecd472)

- Publisher: Leo Tang (leotang09), output of https://www.kaggle.com/code/leotang09/vqcc-t7421-submission
  (notebook header: "Dataset license: apache-2.0", files under Apache-2.0).
- Lineage as credited in that header and upstream: Alex Chilton, yoyobar, Syed Asad Ali (891-qubit decoder), Agniv Banerjee /
  SomeJoint, Ali Haydar Ozdag (ahoirg), Akmal Xodarev (busyaprime), manwithacat, jday96314 (QuantumAI), mrmeows,
  Dmitrii Gluzdov, ViberTeam, Phuc Thai (DePie), Isabe11aM00re; David Pilny reported the decoder counterexample; cites
  Khattar and Gidney (2024).

## dfthcsos/angle_k_0..14.kmb and dfthcsos/submission.npz (hashes in build_manifest.json; npz sha256 b1f2a9c52463...)

- Published by: Heliosli, https://www.kaggle.com/datasets/heliosli/qcc-circuits-live portfolio v71u_k5_ay3 (Kaggle licence
  metadata: Apache-2.0; LICENSE.md: own work Apache-2.0, every other component keeps upstream terms) and
  https://www.kaggle.com/code/heliosli/the-dataset-is-public-now-enjoy
- Angle words and 15 angle circuits: Atakan Aldemir's pi-gauge Givens tree,
  https://www.kaggle.com/code/atakanaldemir/qcc-gap-3-residue-repair-and-c43-native-compiler (version 8),
  https://www.kaggle.com/datasets/atakanaldemir/qcc-repaired-dqi-native-cache (Apache-2.0), integrated in
  https://www.kaggle.com/code/kirilltym/quantum-compilation-19 (version 6).
- Table: Syed Asad Ali's (8, 143, 45) table, https://www.kaggle.com/code/syed3000/vqcc-own-circuit-portfolio-notebook
  (Apache-2.0), building on Lera / marculera's DF-THC pipeline,
  https://www.kaggle.com/code/marculera/df-thc-10x-compact-groups-from-the-hamiltonian (Apache-2.0), and Ahmed Berat Ozer's
  progressive rounding.
- Weights (W, H2_I): as stated by the publisher, its refinement of Akmal Xodarev's (busyaprime) refit,
  https://www.kaggle.com/code/busyaprime/lb-24-73387-top-30-qcc-notebooks-re-verified (version 18),
  https://www.kaggle.com/datasets/busyaprime/33-qcc-v8-members (Apache-2.0).
- Lera's sources as credited there: Ahmed Berat Ozer, SomeJoint, mrmeows, Heliosli, lightningv08, kozykappa, Kozykorpesh and
  Sumit Chongder, Artem1410 (anazemcev), haideptry via phucthaiv02, Michael Rustad, k256net, Dmitrii Gluzdov, and the hosts.

## Licence flags

- No clear licence: the historical DQI design in jday96314's QuantumAI repository states no licence. Upstream authors say
  only the already-public compiled circuit is reused. Every public DQI at this level inherits this. Leo Tang's header cites
  informal permission (topic 753660) and a pending host ruling (topic 754677); this was not independently confirmed.
- Provenance mismatch to resolve: Leo Tang's notebook header describes the DQI as sha256 993c7038, but the file it actually
  outputs and logs is 1c43b7ff, with 42 fewer static Toffoli-like gates (397,149 against 397,191). The notebook does not
  explain the extra saving, so the author of that delta is not stated.
- Kaggle licence metadata for atakan's kernel and for kirilltym/q19-checked-pi-gauge-and-product-cache-data was not read as
  Apache by us beyond the statements above (the q19 dataset reports "unknown").

## Tools

Verifiers, kickmix and reference circuits: Google Quantum AI / Qualtran (Apache-2.0).
