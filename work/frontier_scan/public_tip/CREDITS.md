# Sources and credits

- **invsqrt** — somejoint's (Agniv Banerjee) newest 62-qubit file, byte for byte, from https://www.kaggle.com/code/somejoint/quantum-circuits-24-53-local-gm-window-merges (the circuits keep
  their authors' terms; made there with Claude), an edit of syed3000's newer file from https://www.kaggle.com/code/syed3000/vqcc-24-43-portfolio (Apache-2.0), with
  parts from Ehan Mallick's circuit as Alex Chilton's notebook ships it. Lineage, as credited there: mrmeows (team
  selenium), busyaprime (Akmal Xodarev), yoyobar, Kirill Tymchishin (kirilltym); earlier: Ahmed Berat Özer's phase
  patch, Phuc Thai (DePie), Dmitrii Gluzdov, marsyas.

- **dqi** — yoyobar's second rewrite of syed3000's 891-qubit decoder, byte for byte, from
  https://www.kaggle.com/code/yoyobar/lb-22-99-invsqrt-101-62-qubits (its license scope retained there; the circuits keep
  their authors' terms). syed3000's decoder, from the notebook above (Apache-2.0), builds on their own
  decoder line (made with GPT-6 Astra on SomeJoint's kit, as credited there) with ports of SomeJoint's (Agniv Banerjee)
  892-qubit work and of Ali Haydar Özdağ's (ahoirg) idea, and cites Khattar & Gidney (2024). SomeJoint's notebook credits
  GPT-6 Astra Pro, Claude, Ali Haydar Özdağ (ahoirg), yoyobar and the earlier decoder line (Alex Chilton, jday96314
  (QuantumAI), mrmeows, manwithacat, Dmitrii Gluzdov, ViberTeam, Phuc Thai (DePie)).

- **dfthcsos** — syed3000's (9, 143, 39) table and its angle words, from
  https://www.kaggle.com/code/syed3000/vqcc-24-43-portfolio (Apache-2.0), with syed3000's newest angle loaders k = 0-14 for those words, byte for byte, from
  https://www.kaggle.com/code/syed3000/vqcc-own-circuit-portfolio-notebook (Apache-2.0); built on Lera's (marculera) DF-THC pipeline
  (https://www.kaggle.com/code/marculera/df-thc-10x-compact-groups-from-the-hamiltonian, Apache-2.0) and Ahmed Berat
  Özer's (ahmedberatozer) progressive rounding, and verified there with manwithacat's kickmix engine.
  The table weights (W, H2_I) in this version are ours, refined from syed3000's.
  Lera's sources, as credited there: Ahmed Berat Özer (ahmedberatozer), somejoint, mrmeows, heliosli, lightningv08,
  kozykappa, Kozykorpesh and Sumit Chongder, Artem1410 (anazemcev), haideptry via phucthaiv02, Michael Rustad, k256net
  and Dmitrii Gluzdov, and the hosts.

- **Organizers** — task definitions, verifiers and kickmix (Google Quantum AI / Qualtran, competition data).
