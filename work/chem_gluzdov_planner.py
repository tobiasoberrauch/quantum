"""Run Gluzdov's round11_lookup planner on yoyobar's dfthcsos angle words.

For each batch k: table[x] = packed delta word (J*brot bits). Planner returns
expected AND count (= CCX count, since del_and is free). Compare vs baseline
per-circuit CCX: [301,301,301,301,279,258,279,258,279,258,279,258,279,258,279].
"""
import math
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path("/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum")
GLUZ = Path("/Users/tobiasoberrauch/.cache/kagglehub/datasets/dmitriigluzdov/vqcc-femoco-public-factorization/versions/39/circuit_sources")
sys.path.insert(0, str(REPO / "work"))
sys.path.insert(0, str(GLUZ))

from chem_recompile import load_words  # noqa: E402
import rank_parity as core  # noqa: E402
import round11_lookup as r11  # noqa: E402

BASELINE_CCX = [301, 301, 301, 301, 279, 258, 279, 258, 279, 258, 279, 258, 279, 258, 279]


def main():
    words, brot, edges = load_words()
    D = len(words)
    J = 5
    K = math.ceil(words.shape[1] // J)
    total = 0
    for k in range(K):
        delta = core.delta_batch(words, J, k)
        # pack each row into one integer (J*brot bits, little-endian over (j,bit))
        table = np.zeros(D, dtype=np.int64)
        for j in range(J):
            for bit in range(brot):
                table |= ((delta[:, j] >> bit) & 1) << (j * brot + bit)
        t0 = time.time()
        cost, plan, info = r11.planner(table.tolist())
        dt = time.time() - t0
        total += cost
        print(f"k={k:<2} planned_ANDs={cost:<4} baseline={BASELINE[k]:<4} "
              f"misses={info['misses']} hits={info['hits']} {dt:.1f}s")
    print(f"TOTAL planned={total} baseline={sum(BASELINE_CCX)}")


if __name__ == "__main__":
    main()
