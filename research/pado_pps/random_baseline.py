"""Null baseline for scoring a (hardware) quantum sampler on the 12 hard problems: if the device output is
indistinguishable from uniform random k-subsets, its best-of-S objective looks like this. Exploratory.

Per problem: draw S uniform random k-subsets (S = 100, 1,000, 10,000, 100,000), take the best objective G, report
the relative gap (G - G_opt) / |G_opt| to the MILP-certified optimum. 20 repetitions per S (median, min, max).
Also: the mean random subset's gap, and the gap of the score-greedy pick (top-k linear term). No local search.
argv: <out.jsonl>
"""

import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hard  # noqa: E402
import hard_rqaoa as H  # noqa: E402

SIZES = (100, 1_000, 10_000, 100_000)
REPS = 20


def energies(X, lin, Q):
    Xf = X.astype(float)
    return Xf @ lin + 0.5 * np.einsum("ri,ri->r", Xf @ Q, Xf)


def sample(n, k, S, rng):
    keys = rng.random((S, n))
    idx = np.argpartition(keys, k, axis=1)[:, :k]
    X = np.zeros((S, n), bool); np.put_along_axis(X, idx, True, axis=1)
    return X


def main(out):
    fo = open(os.path.join(HERE, out), "w")
    for ref in H.problems():
        N, k = ref["N"], ref["k"]
        lin, Q = hard.make(N, k, ref["family"], ref["density"], ref["strength"])
        Gopt = ref["milp_G"]; gap = lambda G: (G - Gopt) / abs(Gopt)
        rng = np.random.default_rng([N, k, int(ref["strength"] * 100), len(ref["family"]), 77])
        t0 = time.time()
        greedy = sorted(np.argsort(lin)[:k].tolist())
        rec = {"key": ref["key"], "N": N, "k": k, "G_opt": Gopt, "greedy_gap": gap(hard.energy(greedy, lin, Q))}
        X = sample(N, k, 100_000, rng)
        rec["mean_random_gap"] = float(gap(energies(X, lin, Q)).mean())
        for S in SIZES:
            best = []
            for _ in range(REPS):
                G = energies(sample(N, k, S, rng), lin, Q)
                best.append(float(gap(G.min())))
            rec[f"best_of_{S}"] = {"median": float(np.median(best)), "min": min(best), "max": max(best)}
        rec["seconds"] = time.time() - t0
        fo.write(json.dumps(rec) + "\n"); fo.flush()
        print(f"{ref['key']:28s} greedy {rec['greedy_gap']:7.1%}  mean {rec['mean_random_gap']:7.1%}  " +
              "  ".join(f"best/{S}: {rec[f'best_of_{S}']['median']:6.1%}" for S in SIZES) + f"  {rec['seconds']:.0f}s",
              flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
