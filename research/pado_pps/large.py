"""Large-N map: train on the PADO surrogate at w_train, check at w_train+1 (w-convergence) and,
where the light cone fits (largest ball <= 20 qubits), against the exact energy and the
exact-trained chain.

Universes as in build.py (N=50 original 50; N=100 + every other added; N=150 all).
One (N, d) per call so a stop line can cut a single configuration.

argv: <N> <d> <pmax> <w_train> <out.jsonl>
"""

import json
import os
import sys
import threading
import time

import numpy as np

import ppsl
from lc import LightCone

HERE = os.path.dirname(os.path.abspath(__file__))
PX = json.load(open(os.path.join(HERE, "prices.json")))
ALL = PX["syms"]; P_ALL = np.array(PX["prices"]).T
base = PX["base50"]; added = [s for s in ALL if s not in base]
UNIV = {50: base, 100: base + added[0::2], 150: ALL}


def peak_rss_gb():
    """peak resident memory of this process so far (Windows peak working set, Linux ru_maxrss)"""
    try:
        import psutil
        mi = psutil.Process().memory_info()
        if hasattr(mi, "peak_wset"):
            return round(mi.peak_wset / 2 ** 30, 2)
        import resource
        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 20, 2)
    except Exception:
        return None


def gpu_gb(peak=False):
    """torch caching-allocator memory on the GPU (padopauli allocates through torch); 0 on CPU"""
    import torch
    if not torch.cuda.is_available():
        return 0.0
    return (torch.cuda.max_memory_reserved() if peak else torch.cuda.memory_reserved()) / 2 ** 30


GPU_TRUST_GB = float(os.environ.get("PPS_GPU_TRUST_GB", "160"))
# padopauli 2.0.2 on ROCm returns wrong values without an error when a compile runs into the GPU
# memory ceiling (N=50 d=3 p=4 w=6: -9.38 / -78.88 depending on chunk_size, peak 191 GB, vs a
# chunk-invariant -83.67 at w=5, peak 28 GB). A stage whose GPU peak exceeds GPU_TRUST_GB is not used.


def stage_reset():
    import torch
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()


def infeasible(out, base, p, w, stage, why, t0):
    row = dict(base, p=p, w=w, stage=stage, infeasible=why, elapsed_s=time.time() - t0,
               peak_rss_gb=peak_rss_gb(), peak_gpu_gb=round(gpu_gb(peak=True), 2))
    open(out, "a").write(json.dumps(row) + "\n")
    print("INFEASIBLE", json.dumps(row), flush=True)
    os._exit(3)


class Watchdog(threading.Thread):
    """Enforces the "infeasible" rule (README 6.8): a compile longer than PPS_COMPILE_S seconds, a
    resident set above PPS_MEM_GB, or GPU memory above PPS_GPU_MEM_GB marks the current
    (p, w, stage) infeasible. The compile is one blocking native call, so the thread writes the row
    itself and ends the process. A GPU out-of-memory error is caught in the main loop instead."""

    def __init__(self, out, base):
        super().__init__(daemon=True)
        self.out, self.base, self.phase, self.pending = out, base, None, None
        self.mem_gb = float(os.environ.get("PPS_MEM_GB", "64"))
        self.gpu_mem_gb = float(os.environ.get("PPS_GPU_MEM_GB", "170"))
        self.compile_s = float(os.environ.get("PPS_COMPILE_S", "2400"))

    def enter(self, p, w, stage):
        self.phase = (p, w, stage, time.time())

    def run(self):
        import psutil
        proc = psutil.Process()
        while True:
            time.sleep(2)
            if self.phase is None:
                continue
            p, w, stage, t0 = self.phase
            rss, gpu = proc.memory_info().rss / 2 ** 30, gpu_gb()
            why = None
            if rss > self.mem_gb:
                why = f"rss {rss:.1f} GB > {self.mem_gb:g} GB"
            elif gpu > self.gpu_mem_gb and stage != "compile_check":
                why = f"gpu {gpu:.1f} GB > {self.gpu_mem_gb:g} GB"
            elif stage.startswith("compile") and time.time() - t0 > self.compile_s:
                why = f"compile > {self.compile_s:g} s"
            if why and stage == "compile_check" and self.pending is not None:
                row = dict(self.pending, check_infeasible=why, E_pps_check=None, w_gap_over_extra_gain=None,
                           peak_rss_gb=peak_rss_gb(), peak_gpu_gb=round(gpu_gb(peak=True), 2))
                open(self.out, "a").write(json.dumps(row) + "\n")
                print("CHECK_INFEASIBLE", json.dumps({k: v for k, v in row.items() if k != "angles"}), flush=True)
                os._exit(4)
            if why:
                infeasible(self.out, self.base, p, w, stage, why, t0)


def max_ball(n, J, p):
    """largest reverse-light-cone ball over all terms, without building any state"""
    adj = [[] for _ in range(n)]
    for i, j, _ in J:
        adj[i].append(j); adj[j].append(i)
    best = 0
    for sup in [(i,) for i in range(n)] + [(i, j) for i, j, _ in J]:
        seen = set(sup); front = set(sup)
        for _ in range(p):
            front = {v for u in front for v in adj[u]} - seen
            seen |= front
        best = max(best, len(seen))
    return best


class _LC:
    def __init__(self, m):
        self.m = m

    def energy(self, x):
        return self.m.energy(x)

    def fg(self, x):
        e = self.m.energy(x)
        g = np.array([(self.m.energy(x + 1e-6 * np.eye(len(x))[k]) - self.m.energy(x - 1e-6 * np.eye(len(x))[k])) / 2e-6
                      for k in range(len(x))])
        return e, g


if __name__ == "__main__":
    n, d, pmax, wt, out = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
    syms = UNIV[n]
    pb = ppsl.tune_lambda(ppsl.make_problem(P_ALL[:, [ALL.index(s) for s in syms]], syms, d))
    h, J = pb["h"], pb["J"]
    # resume: rows already written for this (N, d, w_train) give the chain's last angles
    prev = []
    if os.path.exists(out):
        prev = [r for r in map(json.loads, open(out)) if (r["N"], r["d"], r["w_train"]) == (n, d, wt)]
    if any("infeasible" in r for r in prev):
        print(f"N={n} d={d} w={wt}: infeasible row present, skipping", flush=True); sys.exit()
    done = {r["p"]: r for r in prev}
    base = {"N": n, "d": d, "max_degree": pb["max_degree"], "lambda": pb["lambda"], "edges": len(J), "w_train": wt,
            "preset": ppsl.PADO_PRESET, "device": str(ppsl.DEVICE)}
    dog = Watchdog(out, base); dog.start()
    lc_ok = {p: LightCone(n, h, J, p) for p in (1, 2) if max_ball(n, J, p) <= 20}
    ex_x, E1, x = None, None, None
    for p in range(1, pmax + 1):
        if p in lc_ok:   # exact-trained chain where the light cone fits (p <= 2)
            ex_x = ppsl.step(_LC(lc_ok[p]), ex_x).x
        if p in done:
            x, E1 = np.array(done[p]["angles"]), done[p]["E1_ref"]
            continue
        t0 = time.time()   # train_s includes the compile, as in ppsl.chain
        stage_reset()
        try:
            dog.enter(p, wt, "compile_train")
            m = ppsl.PPS(n, h, J, p, wt)
            dog.enter(p, wt, "train")
            r = ppsl.step(m, x)
        except RuntimeError as err:   # torch.OutOfMemoryError is a RuntimeError
            if "out of memory" not in str(err).lower():
                raise
            pp, ww, stage, ts = dog.phase
            infeasible(out, base, pp, ww, stage, "gpu out of memory", ts)
        train_peak = gpu_gb(peak=True)
        if train_peak > GPU_TRUST_GB:
            infeasible(out, base, p, wt, "train", f"gpu peak {train_peak:.1f} GB > trust {GPU_TRUST_GB:g} GB", t0)
        dog.phase = None
        x = r.x
        row = dict(base, p=p, E_pps_train=float(r.fun), w_check=wt + 1, compile_train_s=m.compile_s,
                   train_s=time.time() - t0, angles=x.tolist(), train_peak_gpu_gb=round(train_peak, 2))
        del m
        if p in lc_ok:
            row["E_exact_of_pps_angles"] = lc_ok[p].energy(np.array(x))
            row["E_exact_trained"] = lc_ok[p].energy(np.array(ex_x))
            row["max_ball"] = lc_ok[p].max_ball
        if p == 1:
            E1 = row.get("E_exact_of_pps_angles", row["E_pps_train"])
        row["E1_ref"] = E1
        # w-convergence check at w_train + 1. It is costlier than training, so its failure is recorded
        # on the row and does not stop the chain; once it fails, deeper p skip it (only gets larger).
        skip = next((r_["check_infeasible"] for r_ in prev if r_.get("check_infeasible")), None)
        e_chk = None
        if skip:
            row["check_infeasible"] = f"skipped: {skip}"
        else:
            dog.pending = row
            stage_reset()
            try:
                dog.enter(p, wt + 1, "compile_check")
                chk = ppsl.PPS(n, h, J, p, wt + 1)
                e_chk = chk.energy(x)
                row["compile_check_s"] = chk.compile_s
                del chk
            except RuntimeError as err:
                if "out of memory" not in str(err).lower():
                    raise
                row["check_infeasible"] = f"gpu out of memory at p={p}"
                chk = None
                import torch, gc
                gc.collect(); torch.cuda.empty_cache()
            dog.phase = dog.pending = None
            row["check_peak_gpu_gb"] = round(gpu_gb(peak=True), 2)
            if e_chk is not None and row["check_peak_gpu_gb"] > GPU_TRUST_GB:
                row["E_pps_check_untrusted"] = e_chk; e_chk = None
                row["check_infeasible"] = f"gpu peak {row['check_peak_gpu_gb']:.1f} GB > trust {GPU_TRUST_GB:g} GB"
        row["E_pps_check"] = e_chk
        row["peak_rss_gb"] = peak_rss_gb()
        row["peak_gpu_gb"] = max(row["train_peak_gpu_gb"], row.get("check_peak_gpu_gb", 0.0))
        extra = None if e_chk is None else E1 - e_chk
        row["w_gap_over_extra_gain"] = abs(e_chk - row["E_pps_train"]) / extra if p > 1 and extra and extra > 1e-9 else None
        open(out, "a").write(json.dumps(row) + "\n")
        prev.append(row)
        print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items() if k != "angles"}),
              flush=True)
