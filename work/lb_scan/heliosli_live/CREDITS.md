# Sources and credits

- **invsqrt** — Ehan Mallick's 62-qubit file, byte for byte, from the output of Alex Chilton's portfolio
  https://www.kaggle.com/code/alexchilton/22-57-lb-verified-three-task-portfolio (Apache-2.0), which credits it to
  https://www.kaggle.com/code/ehanmallick/invsqrt-20-65-two-3-to-2-and-merges-on-y6225 and builds it on yoyobar's
  62-qubit circuit (https://www.kaggle.com/code/yoyobar/lb-22-99-invsqrt-101-62-qubits, Apache-2.0; dataset
  https://www.kaggle.com/datasets/yoyobar/qcc-local-sota-20261031). Earlier lineage, as credited in our previous
  versions: yoyobar's own 62-qubit work on Akmal Xodarev's (busyaprime) and mrmeows / team selenium's circuits, with
  Ahmed Berat Özer's patch as distributed in manwithacat's Quantum Voodoo; earlier: Phuc Thai (DePie), Dmitrii
  Gluzdov, marsyas.

- **dqi** — busyaprime's (Akmal Xodarev) third update of somejoint's (Agniv Banerjee) newer 892-qubit decoder, byte for
  byte, from the 2 November output of https://www.kaggle.com/code/busyaprime/23-910-local-gm-exact-dqi-rewrites-892-qubits
  (Apache-2.0). As credited there: manwithacat (Hedge Wizardry HW-07, https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook);
  Ahmed Berat Özer for the idea it builds on; somejoint's decoder
  (https://www.kaggle.com/code/somejoint/quantum-circuits-23-85-local-gm-892-qubit-dqi), whose notebook credits GPT-6
  Astra Pro, Claude, Ali Haydar Özdağ (ahoirg), yoyobar's one-carry history and the earlier decoder line (Alex
  Chilton, jday96314 (QuantumAI), mrmeows, manwithacat, Dmitrii Gluzdov, ViberTeam, Phuc Thai (DePie)).
- **dfthcsos** — Lera's (marculera) second (9, 143, 40) factorization: its angle words and thirteen of its angle
  circuits (k = 1 to 13), byte for byte, from https://www.kaggle.com/code/marculera/df-thc-10x-compact-groups-from-the-hamiltonian?scriptVersionId=364385620
  (Apache-2.0); the angle circuits for k = 0 and k = 14 by Dmitrii Gluzdov, from version 44 of
  https://www.kaggle.com/code/dmitriigluzdov/quantum-circuit-compilation-from-source, byte for byte as assembled in
  manwithacat's https://www.kaggle.com/code/manwithacat/the-real-150k-was-the-friends-we-made (thanks to manwithacat
  for the assembly). Lera's sources, as credited there: Ahmed Berat Özer (ahmedberatozer), somejoint, mrmeows,
  heliosli, lightningv08, kozykappa, Kozykorpesh and Sumit Chongder, Artem1410 (anazemcev), haideptry via phucthaiv02,
  Michael Rustad, k256net and Dmitrii Gluzdov, and the hosts. The table weights (W, H2_I) are ours, starting from
  Lera's.
  This version continues from Ahmed Berat Özer's refinement of our weights in
  https://www.kaggle.com/code/ahmedberatozer/quantum-ai-df-thc-group-compression (1 November).
  With thanks to Atakan Aldemir, whose
  https://www.kaggle.com/code/atakanaldemir/qcc-gap-3-residue-repair-and-c43-native-compiler pointed us to Lera's
  tables.
- **Organizers** — task definitions, verifiers and kickmix (Google Quantum AI / Qualtran, competition data).
