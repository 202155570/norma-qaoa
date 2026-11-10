"""Sample the PPS-trained QAOA circuits on IBM hardware and score the samples (README 8).

Runs in .venv-ibm (qiskit, qiskit-ibm-runtime, qiskit-aer). Reads ibm/spec.json (ibm_prep.py).
Circuit: |+>^n, p x [exp(-i g C) exp(-i b sum X)], C = sum h Z + sum J ZZ; bit 1 = ETF selected
(Z = -1). Qiskit bitstrings are little-endian: qubit i is character -1-i.

IBM_SET=hard switches every file to the coupling-strengthened set of ibm_hard_prep.py, scored on
raw shots (no repair): ground-state hits, top-0.1%/1% energy shares, approximation ratio.

  local  <shots>            noiseless Aer sampling; mean energy must match E_exact (5 sigma)
  submit <backend> <shots>  transpile (level 3) and submit ONE SamplerV2 job; writes ibm/job.json
  fetch                     download the job's samples (ibm/samples_<key>.json) and analyse
  analyse                   analyse saved samples (ibm/samples_*.json) -> ibm/result.json

Analysis per circuit:
  energy  - mean C over shots vs the exact prediction; retained = E_hw / E_exact (0 = uniform
            random bitstrings, 1 = noiseless circuit)
  pick    - each shot is repaired to k=6 with the ORIGINAL objective (exp_a.repair); reported:
            best G, share of shots landing in the original top 1%, and best-of-s over small budgets
  baselines (same shot counts, same repair): uniform random bits; independent bits with the
            hardware marginals randomly permuted over ETFs; the same marginals in score order
            (exp_a's baselines); and, for the local run, the noiseless circuit itself.
"""

import itertools
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "ibm")
INSTANCE = os.environ.get("IBM_INSTANCE", "P_QARS_Pusan_univ")
BUDGETS, RUNS = (10, 100, 1000), 50
# IBM_SET selects a circuit set: "" -> spec.json / job.json / samples_hw.json (first run);
# "hard" -> spec_hard.json / job_hard.json / samples_hard_hw.json (ibm_hard_prep.py).
SET = os.environ.get("IBM_SET", "")
SFX = f"_{SET}" if SET else ""


def load_spec():
    return json.load(open(os.path.join(D, f"spec{SFX}.json")))


def analyse_raw(s, X, w, rng):
    """raw shots, no repair (hard set): ground-state hits and low-energy shares vs noiseless/uniform"""
    E = ising(X, s); m = w.sum()
    gs = np.array([(s["gs_index"] >> i) & 1 for i in range(s["n"])], dtype=np.uint8)
    hit = (X == gs).all(1)
    out = {"P_gs": float(w[hit].sum() / m), "share_q001": float(w[E <= s["E_q001"] + 1e-12].sum() / m),
           "share_q01": float(w[E <= s["E_q01"] + 1e-12].sum() / m),
           "approx_ratio": float(((E * w).sum() / m - s["E_max"]) / (s["E_gs"] - s["E_max"])),
           "mean_selected": float((X.sum(1) * w).sum() / m)}
    Es = np.repeat(E, w)
    for b in BUDGETS:
        if b < len(Es):
            out[f"best_of_{b}_hits_gs"] = float(np.mean([Es[rng.choice(len(Es), b, replace=False)].min() <= s["E_gs"] + 1e-9
                                                         for _ in range(RUNS)]))
    return out


def circuit(s):
    from qiskit import QuantumCircuit
    n, x = s["n"], s["angles"]; p = len(x) // 2
    qc = QuantumCircuit(n, name=s["key"]); qc.h(range(n))
    for l in range(p):
        g, b = x[l], x[p + l]
        for i, hi in enumerate(s["h"]):
            qc.rz(2 * g * hi, i)
        for i, j, v in s["J"]:
            qc.rzz(2 * g * v, i, j)
        qc.rx(2 * b, range(n))
    qc.measure_all()
    return qc


def bits(counts, n):
    """counts {bitstring: c} -> (X uint8 [m, n], weights [m])"""
    keys = list(counts)
    X = np.array([[int(k[-1 - i]) for i in range(n)] for k in keys], dtype=np.uint8)
    return X, np.array([counts[k] for k in keys], dtype=np.int64)


def ising(X, s):
    Z = 1.0 - 2.0 * X
    E = Z @ np.array(s["h"])
    for i, j, v in s["J"]:
        E = E + v * Z[:, i] * Z[:, j]
    return E


# ---- scoring with the original objective (same repair as exp_a.py) ----
def G(T, lin, Q):
    T = list(T)
    return float(lin[T].sum() + Q[np.ix_(T, T)][np.triu_indices(len(T), 1)].sum())


def repair(T, lin, Q, k):
    T = list(T)
    while len(T) > k:
        a = np.array(T)
        T.pop(int(np.argmax(lin[a] + Q[np.ix_(a, a)].sum(1))))
    while len(T) < k:
        gain = lin + (Q[T].sum(0) if T else 0.0)
        gain[T] = np.inf
        T.append(int(np.argmin(gain)))
    return tuple(sorted(T))


def reference(s, lin, Q):
    """sorted G over all k-subsets (n <= 50) or 1e6 uniform k-subsets (seed 99, as exp_a)"""
    n, k = s["n"], s["k"]
    if n <= 50:
        G_ = []
        for first in range(n - k + 1):
            rest = np.array(list(itertools.combinations(range(first + 1, n), k - 1)), dtype=np.int64)
            c = np.concatenate([np.full((len(rest), 1), first), rest], axis=1)
            e = lin[c].sum(1)
            for a, b in itertools.combinations(range(k), 2):
                e = e + Q[c[:, a], c[:, b]]
            G_.append(e)
        return np.sort(np.concatenate(G_)), "exhaustive"
    rs = np.random.default_rng(99)
    c = np.concatenate([np.argpartition(rs.random((100_000, n)), k, axis=1)[:, :k] for _ in range(10)])
    e = lin[c].sum(1)
    for a, b in itertools.combinations(range(k), 2):
        e = e + Q[c[:, a], c[:, b]]
    return np.sort(e), "1e6 uniform samples, seed 99"


def shot_G(X, s, lin, Q, cache):
    """G after repair, one value per row of X"""
    out = np.empty(len(X))
    for r, row in enumerate(X):
        key = row.tobytes()
        if key not in cache:
            cache[key] = G(repair(np.flatnonzero(row), lin, Q, s["k"]), lin, Q)
        out[r] = cache[key]
    return out


def score_samples(name, X, w, s, lin, Q, ref, cache, rng):
    g = shot_G(X, s, lin, Q, cache)
    gs = np.repeat(g, w)                                  # one value per shot
    top1 = ref[int(0.01 * len(ref))]
    pct = lambda v: float(np.searchsorted(ref, v, side="left") / len(ref))
    out = {"shots": int(w.sum()), "best_G": float(g.min()), "best_percentile": pct(g.min()),
           "median_G": float(np.median(gs)), "share_top1pct": float((gs <= top1).mean()),
           "mean_selected_raw": float((X.sum(1) * w).sum() / w.sum())}
    for b in BUDGETS:
        if b < len(gs):
            best = [gs[rng.choice(len(gs), b, replace=False)].min() for _ in range(RUNS)]
            out[f"best_of_{b}_median_G"] = float(np.median(best))
    return out


def analyse(samples, tag):
    """samples: {key: counts}. Returns and writes the analysis."""
    spec = {s["key"]: s for s in load_spec()}
    res = {}
    rng = np.random.default_rng(7)
    refs = {}
    for key, counts in samples.items():
        s = spec[key]; n = s["n"]
        if "lin" not in s:                                 # hard set: raw shots only
            X, w = bits(counts, n); E = ising(X, s); m = w.sum()
            Ehw = float((E * w).sum() / m)
            r = {"n": n, "p": s["p"], "seed": s["seed"], "E_exact": s["E_exact"], "E_sampled": Ehw,
                 "E_sampled_sem": float(np.sqrt(((E - Ehw) ** 2 * w).sum() / (m - 1) / m)),
                 "retained": Ehw / s["E_exact"], "E_gs": s["E_gs"], "noiseless": s["noiseless"],
                 "uniform": {"P_gs": 2.0 ** -n, "share_q001": 1e-3, "share_q01": 1e-2},
                 "descent_hit_rate": s["descent_hit_rate"], "samples": analyse_raw(s, X, w, rng)}
            res[key] = r; sm = r["samples"]
            print(f"{key}: E {Ehw:+.3f} vs noiseless {s['E_exact']:+.3f} (retained {r['retained']:.3f}) | "
                  f"P_gs {sm['P_gs']:.4f} (noiseless {s['noiseless']['P_gs']:.4f}, uniform {2.0 ** -n:.1e}) | "
                  f"top0.1% {sm['share_q001']:.3f} (noiseless {s['noiseless']['share_q001']:.3f}) | "
                  f"best-of-100 hits GS {sm.get('best_of_100_hits_gs')}", flush=True)
            continue
        lin, Q = np.array(s["lin"]), np.array(s["Q"])
        if n not in refs:
            refs[n] = reference(s, lin, Q)
        ref, ref_kind = refs[n]
        X, w = bits(counts, n)
        E = ising(X, s); m = w.sum()
        Ehw = float((E * w).sum() / m)
        sem = float(np.sqrt(((E - Ehw) ** 2 * w).sum() / (m - 1) / m))
        r = {"n": n, "p": s["p"], "E_exact": s["E_exact"], "E_exact_source": s["E_exact_source"],
             "E_sampled": Ehw, "E_sampled_sem": sem, "retained": Ehw / s["E_exact"],
             "percentile_reference": ref_kind, "original_best_G": float(ref[0]) if ref_kind == "exhaustive" else None}
        cache = {}
        r["samples"] = score_samples("samples", X, w, s, lin, Q, ref, cache, rng)
        q = (X * w[:, None]).sum(0) / m                    # marginals of the samples
        S = np.array(s["score"])
        q_score = np.empty(n); q_score[np.argsort(-S)] = q[np.argsort(-q)]
        ones = np.ones(int(m), dtype=np.int64)
        for name, qq in (("uniform", np.full(n, 0.5)), ("random_marginals", rng.permutation(q)),
                         ("score_order_marginals", q_score)):
            Xb = (rng.random((int(m), n)) < qq).astype(np.uint8)
            r[name] = score_samples(name, Xb, ones, s, lin, Q, ref, cache, rng)
        greedy = repair([], lin, Q, s["k"])
        r["greedy_from_empty_G"] = G(greedy, lin, Q)
        best_row = X[int(np.argmin(shot_G(X, s, lin, Q, cache)))]
        r["best_pick"] = [s["syms"][i] for i in repair(np.flatnonzero(best_row), lin, Q, s["k"])]
        res[key] = r
        sm = r["samples"]
        print(f"{key}: E {Ehw:+.3f}±{sem:.3f} vs exact {s['E_exact']:+.3f} (retained {r['retained']:.3f})  "
              f"best G {sm['best_G']:.3f} (pct {sm['best_percentile']:.2e}), top1% share {sm['share_top1pct']:.3f} | "
              f"uniform {r['uniform']['share_top1pct']:.3f}  rand-marg {r['random_marginals']['share_top1pct']:.3f}  "
              f"score-marg {r['score_order_marginals']['share_top1pct']:.3f}", flush=True)
    json.dump(res, open(os.path.join(D, f"result{SFX}_{tag}.json"), "w"), indent=1, ensure_ascii=False)
    return res


if __name__ == "__main__":
    cmd = sys.argv[1]
    spec = load_spec()
    if cmd == "local":
        from qiskit import transpile
        from qiskit_aer import AerSimulator
        shots = int(sys.argv[2]); samples = {}
        for s in spec:
            method = "statevector" if s["n"] <= 24 else "matrix_product_state"
            sim = AerSimulator(method=method, seed_simulator=11)
            t0 = time.time()
            qc = transpile(circuit(s), sim) if s["n"] <= 24 else circuit(s)   # transpile caps width at 63
            c = sim.run(qc, shots=shots).result().get_counts()
            X, w = bits(c, s["n"]); E = ising(X, s); m = w.sum()
            mu = (E * w).sum() / m; sem = np.sqrt(((E - mu) ** 2 * w).sum() / (m - 1) / m)
            ok = abs(mu - s["E_exact"]) < 5 * sem
            print(f"{s['key']} [{method}, {time.time() - t0:.0f}s]: sampled {mu:+.4f} ± {sem:.4f}  exact {s['E_exact']:+.4f}  "
                  f"{'OK' if ok else 'MISMATCH'}", flush=True)
            assert ok, s["key"]
            samples[s["key"]] = c
        json.dump(samples, open(os.path.join(D, f"samples{SFX}_local.json"), "w"))
        analyse(samples, "local")
    elif cmd == "submit":
        from qiskit.transpiler import generate_preset_pass_manager
        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
        be_name, shots = sys.argv[2], int(sys.argv[3])
        if os.path.exists(os.path.join(D, f"job{SFX}.json")):
            sys.exit(f"ibm/job{SFX}.json exists: a job was already submitted (fetch it, or move the file)")
        svc = QiskitRuntimeService(instance=INSTANCE)
        be = svc.backend(be_name)
        pm = generate_preset_pass_manager(optimization_level=3, backend=be, seed_transpiler=1)
        isa = [pm.run(circuit(s)) for s in spec]
        stats = {}
        for s, c in zip(spec, isa):
            ops = c.count_ops()
            stats[s["key"]] = {"cz": int(ops.get("cz", 0)), "depth_2q": c.depth(lambda i: i.operation.num_qubits == 2),
                               "layout": c.layout.final_index_layout() if c.layout else None}
            print(s["key"], stats[s["key"]]["cz"], "CZ, 2q depth", stats[s["key"]]["depth_2q"], flush=True)
        sampler = SamplerV2(mode=be)
        sampler.options.default_shots = shots
        sampler.options.dynamical_decoupling.enable = True
        sampler.options.dynamical_decoupling.sequence_type = "XY4"
        sampler.options.twirling.enable_gates = True
        sampler.options.twirling.enable_measure = True
        job = sampler.run(isa)
        meta = {"job_id": job.job_id(), "backend": be_name, "instance": INSTANCE, "shots": shots,
                "submitted": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "keys": [s["key"] for s in spec],
                "options": {"dynamical_decoupling": "XY4", "twirling": "gates+measure", "optimization_level": 3},
                "transpiled": stats}
        json.dump(meta, open(os.path.join(D, f"job{SFX}.json"), "w"), indent=1)
        print("submitted", meta["job_id"], flush=True)
    elif cmd == "fetch":
        from qiskit_ibm_runtime import QiskitRuntimeService
        meta = json.load(open(os.path.join(D, f"job{SFX}.json")))
        job = QiskitRuntimeService(instance=meta["instance"]).job(meta["job_id"])
        st = job.status(); print("status", st, flush=True)
        if str(st) not in ("DONE", "JobStatus.DONE"):
            sys.exit(2)
        result = job.result()
        samples = {k: result[i].data.meas.get_counts() for i, k in enumerate(meta["keys"])}
        json.dump(samples, open(os.path.join(D, f"samples{SFX}_hw.json"), "w"))
        try:
            meta["usage"] = job.usage(); meta["metrics"] = job.metrics()
        except Exception as e:
            meta["usage_error"] = str(e)
        json.dump(meta, open(os.path.join(D, f"job{SFX}.json"), "w"), indent=1, default=str)
        analyse(samples, "hw")
    elif cmd == "analyse":
        tag = sys.argv[2] if len(sys.argv) > 2 else "hw"
        analyse(json.load(open(os.path.join(D, f"samples{SFX}_{tag}.json"))), tag)
