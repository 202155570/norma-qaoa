"""Annealing-type baselines on the penalised QUBO of the 12 hard problems (what a quantum annealer is given).
Exploratory, not pre-registered. Same problems, same penalty P (sum x - k)^2 as hard_rqaoa.py / hard_sa.py.

  pt    parallel tempering: C independent chains x M temperatures (geometric, T0 .. T0/1000, T0 = median
        |Delta| of a random flip at a random start), single-bit Metropolis sweeps, neighbour exchanges after
        every sweep; best feasible state seen at any sweep end.
  sqa   simulated quantum annealing (path-integral Monte Carlo, Martonak-Santoro-Tosatti 2002): L Trotter
        slices of the Ising form (z = -1 selected), fixed temperature T, transverse field Gamma lowered
        linearly; inter-slice coupling J_perp = -(T/2) ln tanh(Gamma / (L T)); single-spin Metropolis on
        every slice; read-out: every slice of every replica at the end (best feasible, share at optimum).
  emb   classical stand-in for the QPU's handicaps: the logical Ising embedded on the ideal Advantage graph
        (Pegasus P16, clique embedding of K_N by minorminer.busclique, chains of 10 (N=100) / 15 (N=150)),
        chain strength by uniform torque compensation (prefactor sqrt 2), scaled into h in [-4, 4],
        |J| <= 1 as the QPU's auto-scale does, optional Gaussian control error added to every h and J
        (sigma_h, sigma_J in those hardware units, fresh per batch of reads: an assumption, the device's
        actual error is not modelled), then SA on the physical spins with single-qubit flips and whole-chain flips
        (without chain moves, single-flip SA freezes the chains early: an artefact of SA, not of the QPU) and
        majority-vote unembedding; reports the chain-break share.
argv: <out.jsonl> <pt|sqa|emb> [options as key=value]
"""

import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hard  # noqa: E402
import hard_rqaoa as H  # noqa: E402

REL = 1e-9


def penalised(lin, Q, k, P):
    linp = lin + P * (1 - 2 * k); Qp = Q + 2.0 * P; np.fill_diagonal(Qp, 0.0)
    return linp, Qp


def G_of(x, lin, Q):
    return hard.energy(sorted(np.flatnonzero(x).tolist()), lin, Q)


# ---------------------------------------------------------------- parallel tempering
def pt(lin, Q, k, P, rng, chains=8, temps=24, sweeps=1000):
    n = len(lin); linp, Qp = penalised(lin, Q, k, P)
    R = chains * temps
    X = rng.random((R, n)) < k / n
    S = X.astype(float) @ Qp
    E = X @ linp + 0.5 * np.einsum("ri,ri->r", X.astype(float), S)
    ar = np.arange(R)
    i = rng.integers(0, n, R)
    T0 = float(np.median(np.abs(np.where(X[ar, i], -1.0, 1.0) * (linp[i] + S[ar, i])))) or 1.0
    Ts = T0 * (1e-3) ** (np.arange(temps) / (temps - 1))        # slot t of every chain has temperature Ts[t]
    beta = np.tile(1.0 / Ts, chains)
    best_E, best_x = np.inf, None
    for sw in range(sweeps):
        for _ in range(n):
            i = rng.integers(0, n, R)
            sgn = np.where(X[ar, i], -1.0, 1.0)
            d = sgn * (linp[i] + S[ar, i])
            acc = (d <= 0) | (rng.random(R) < np.exp(-np.maximum(d, 0) * beta))
            if acc.any():
                r = ar[acc]
                X[r, i[acc]] = ~X[r, i[acc]]
                S[r] += sgn[acc][:, None] * Qp[i[acc]]
                E[r] += d[acc]
        # replica exchange between neighbouring temperatures (even / odd pairs alternately)
        for c in range(chains):
            base = c * temps
            for t in range(sw % 2, temps - 1, 2):
                a, b = base + t, base + t + 1
                if rng.random() < math.exp(min(0.0, (beta[a] - beta[b]) * (E[a] - E[b]))):
                    X[[a, b]] = X[[b, a]]; S[[a, b]] = S[[b, a]]; E[[a, b]] = E[[b, a]]
        feas = X.sum(1) == k
        if feas.any():
            j = int(np.argmin(np.where(feas, E, np.inf)))
            if E[j] < best_E:
                best_E, best_x = float(E[j]), X[j].copy()
    G = G_of(best_x, lin, Q) if best_x is not None else np.inf
    cold = np.arange(chains) * temps + temps - 1
    Gc = np.array([G_of(X[j], lin, Q) if X[j].sum() == k else np.inf for j in cold])
    return {"best_G": G, "cold_G": Gc.tolist(), "T0": T0}


# ---------------------------------------------------------------- simulated quantum annealing
def sqa(lin, Q, k, P, rng, replicas=8, slices=32, sweeps=1000, LT=0.1, G0=1.0, G1=1e-3):
    """LT, G0, G1 in units of s0 = median |classical flip cost| at a random start."""
    n = len(lin); linp, Qp = penalised(lin, Q, k, P)
    h = -linp / 2.0 - Qp.sum(1) / 4.0; J = Qp / 4.0
    R, L = replicas, slices
    s = np.where(rng.random((R, L, n)) < k / n, -1.0, 1.0)
    F = s @ J + h                                                # local field per slice
    s0 = float(np.median(np.abs(2 * s * F)))
    T = LT * s0 / L
    rr, ll = np.meshgrid(np.arange(R), np.arange(L), indexing="ij"); rr, ll = rr.ravel(), ll.ravel()
    up, dn = (ll + 1) % L, (ll - 1) % L
    for sw in range(sweeps):
        Gam = (G0 + (G1 - G0) * sw / max(sweeps - 1, 1)) * s0
        Jp = -0.5 * T * math.log(math.tanh(Gam / (L * T)))
        for _ in range(n):
            i = rng.integers(0, n, R * L)
            si = s[rr, ll, i]
            dE = -2.0 * si * F[rr, ll, i] / L + 2.0 * Jp * si * (s[rr, up, i] + s[rr, dn, i])
            acc = (dE <= 0) | (rng.random(R * L) < np.exp(-np.maximum(dE, 0) / T))
            if acc.any():
                a_r, a_l, a_i = rr[acc], ll[acc], i[acc]
                F[a_r, a_l] += (-2.0 * si[acc])[:, None] * J[a_i]
                s[a_r, a_l, a_i] = -si[acc]
    X = (s < 0).reshape(R * L, n)
    Gs = np.array([G_of(x, lin, Q) if x.sum() == k else np.inf for x in X])
    return {"G_all": Gs, "s0": s0, "T": T}


# ---------------------------------------------------------------- embedded SA with control error
_EMB = {}


def clique_embedding(N):
    if N not in _EMB:
        path = os.path.join(HERE, f"emb_pegasus16_K{N}.json")
        if os.path.exists(path):
            _EMB[N] = {int(a): b for a, b in json.load(open(path)).items()}
        else:
            import dwave_networkx as dnx
            from minorminer.busclique import find_clique_embedding
            emb = find_clique_embedding(N, dnx.pegasus_graph(16))
            _EMB[N] = {int(a): list(map(int, b)) for a, b in emb.items()}
            json.dump(_EMB[N], open(path, "w"))
    return _EMB[N]


def emb_sa(lin, Q, k, P, rng, reads=50, sweeps=300, sig_h=0.0, sig_J=0.0, batches=5, prefactor=math.sqrt(2), tmin=1e-3, cs_mult=1.0):
    import dwave_networkx as dnx
    n = len(lin); linp, Qp = penalised(lin, Q, k, P)
    h = -linp / 2.0 - Qp.sum(1) / 4.0; J = Qp / 4.0
    emb = clique_embedding(n)
    Gp = dnx.pegasus_graph(16)
    # uniform torque compensation (dwave.embedding.chain_strength), logical units
    iu = np.triu_indices(n, 1); Jv = J[iu]; Jv = Jv[Jv != 0]
    avg_deg = 2 * len(Jv) / n
    cs = cs_mult * prefactor * math.sqrt(float(np.mean(Jv ** 2))) * math.sqrt(avg_deg)
    qubits = sorted(q for c in emb.values() for q in c); qi = {q: a for a, q in enumerate(qubits)}
    owner = np.empty(len(qubits), int)
    for v, c in emb.items():
        for q in c:
            owner[qi[q]] = v
    m = len(qubits)
    hp = np.zeros(m); edges = {}
    for v, c in emb.items():
        for q in c:
            hp[qi[q]] += h[v] / len(c)
    inter = {}
    for a, b in Gp.subgraph(qubits).edges():
        u, v = owner[qi[a]], owner[qi[b]]
        if u == v:
            edges[(qi[a], qi[b])] = -cs
        else:
            inter.setdefault((min(u, v), max(u, v)), []).append((qi[a], qi[b]))
    for (u, v), lst in inter.items():
        for e in lst:
            edges[e] = J[u, v] / len(lst)
    missing = sum(1 for u, v in zip(*iu) if J[u, v] != 0 and (u, v) not in inter)
    assert missing == 0, missing
    E = np.array(list(edges.keys())); W = np.array(list(edges.values()))
    alpha = max(np.abs(hp).max() / 4.0, np.abs(W).max() / 1.0)    # auto-scale into h in [-4, 4], |J| <= 1
    hp_s, W_s = hp / alpha, W / alpha
    deg = np.bincount(E.ravel(), minlength=m); D = int(deg.max())
    nbr = np.full((m, D), m, int); nw_idx = np.zeros((m, D), int); fill = np.zeros(m, int)
    for e, (a, b) in enumerate(E):
        nbr[a, fill[a]] = b; nw_idx[a, fill[a]] = e; fill[a] += 1
        nbr[b, fill[b]] = a; nw_idx[b, fill[b]] = e; fill[b] += 1
    # chains (padded with m) and their intra-chain edges (padded with a zero-weight dummy edge)
    Lmax = max(len(c) for c in emb.values())
    CQ = np.full((n, Lmax), m, int)
    intra_e = {v: [] for v in range(n)}
    for e, (a, b) in enumerate(E):
        if owner[a] == owner[b]:
            intra_e[int(owner[a])].append(e)
    Emax = max(len(x) for x in intra_e.values())
    EA = np.full((n, Emax), m, int); EB = np.full((n, Emax), m, int); EI = np.full((n, Emax), len(E), int)
    for v, c in emb.items():
        CQ[v, :len(c)] = [qi[q] for q in c]
        for t, e in enumerate(intra_e[v]):
            EA[v, t], EB[v, t], EI[v, t] = E[e][0], E[e][1], e
    out_G, breaks = [], []
    per = reads // batches
    for bt in range(batches):
        hn = hp_s + rng.normal(0, sig_h, m) if sig_h else hp_s
        Wn = W_s + rng.normal(0, sig_J, len(W_s)) if sig_J else W_s
        Wpad = np.append(Wn, 0.0)[np.where(nbr < m, nw_idx, len(Wn))]           # (m, D)
        EW_pad = np.append(Wn, 0.0)
        s = rng.choice([-1.0, 1.0], size=(per, m)); s_pad = np.concatenate([s, np.zeros((per, 1))], 1)
        F = hn + (s_pad[:, nbr] * Wpad[None]).sum(2)
        ar = np.arange(per)
        i = rng.integers(0, m, per)
        T0 = float(np.median(np.abs(2 * s[ar, i] * F[ar, i]))) or 1.0
        temps = T0 * tmin ** (np.arange(sweeps) / max(sweeps - 1, 1))

        def flip_qubits(r, q, sold):
            """r, q: flat arrays of (read, qubit) flipped this step (old spins sold); updates s and F."""
            s[r, q] = -sold
            nb = nbr[q]; wv = Wpad[q]; ok = nb < m
            np.add.at(F, (np.repeat(r, D)[ok.ravel()], nb[ok]), (np.repeat(-2.0 * sold, D) * wv.ravel())[ok.ravel()])
        for sw in range(sweeps):
            Tt = temps[sw]
            for _ in range(m):                                   # single-qubit flips
                i = rng.integers(0, m, per)
                si = s[ar, i]
                d = -2.0 * si * F[ar, i]
                acc = (d <= 0) | (rng.random(per) < np.exp(-np.maximum(d, 0) / Tt))
                if acc.any():
                    flip_qubits(ar[acc], i[acc], si[acc])
            for _ in range(n):                                   # whole-chain flips
                v = rng.integers(0, n, per)
                cq = CQ[v]                                       # (per, Lmax), padded with m
                sp = np.concatenate([s, np.zeros((per, 1))], 1)
                Fp = np.concatenate([F, np.zeros((per, 1))], 1)
                sc = sp[ar[:, None], cq]
                intra = (sp[ar[:, None], EA[v]] * sp[ar[:, None], EB[v]] * EW_pad[EI[v]]).sum(1)
                d = -2.0 * ((sc * Fp[ar[:, None], cq]).sum(1) - 2.0 * intra)
                acc = (d <= 0) | (rng.random(per) < np.exp(-np.maximum(d, 0) / Tt))
                if acc.any():
                    ra = np.repeat(ar[acc], CQ.shape[1]); qa = cq[acc].ravel(); ok = qa < m
                    flip_qubits(ra[ok], qa[ok], sc[acc].ravel()[ok])
        for x in s:
            zl = np.zeros(n); br = 0
            for v, c in emb.items():
                vals = x[[qi[q] for q in c]]; sm = vals.sum()
                br += int(abs(sm) != len(c))
                zl[v] = np.sign(sm) if sm != 0 else rng.choice([-1.0, 1.0])
            xl = zl < 0
            out_G.append(G_of(xl, lin, Q) if xl.sum() == k else np.inf); breaks.append(br / n)
    return {"G_all": np.array(out_G), "chain_break_share": float(np.mean(breaks)), "qubits": m,
            "chain_len_mean": float(np.mean([len(c) for c in emb.values()])), "chain_strength_logical": cs,
            "autoscale": float(alpha)}


def main(out, method, opts):
    Pq = {json.loads(l)["key"]: json.loads(l)["lam"] for l in open(os.path.join(HERE, "hard_rqaoa.jsonl"))
          if json.loads(l)["penalty"] == "quad"}
    only = opts.pop("keys", None)
    tag = opts.pop("tag", method)
    fo = open(os.path.join(HERE, out), "a")
    for ref in H.problems():
        if only and ref["key"] not in only.split(","):
            continue
        N, k = ref["N"], ref["k"]
        lin, Q = hard.make(N, k, ref["family"], ref["density"], ref["strength"])
        Gopt = ref["milp_G"]; tol = REL * abs(Gopt); P = Pq[ref["key"]]
        rng = np.random.default_rng([N, k, int(ref["strength"] * 100), len(ref["family"]), 7])
        t0 = time.time()
        row = {"key": ref["key"], "N": N, "k": k, "method": method, "tag": tag, "opts": opts, "G_opt": Gopt, "P": P}
        if method == "pt":
            r = pt(lin, Q, k, P, rng, **opts)
            G = np.array([r["best_G"]]); row.update(cold_hit_share=float(np.mean(np.array(r["cold_G"]) <= Gopt + tol)))
            row["cold_feasible_share"] = float(np.mean(np.isfinite(r["cold_G"])))
        elif method == "sqa":
            r = sqa(lin, Q, k, P, rng, **opts); G = r["G_all"]; row.update(s0=r["s0"], T=r["T"])
        else:
            r = emb_sa(lin, Q, k, P, rng, **opts); G = r["G_all"]
            row.update({a: r[a] for a in ("chain_break_share", "qubits", "chain_len_mean", "chain_strength_logical", "autoscale")})
        best = float(G.min())
        row.update(best_G=best if np.isfinite(best) else None, hit=bool(best <= Gopt + tol),
                   hit_share=float(np.mean(G <= Gopt + tol)), feasible_share=float(np.mean(np.isfinite(G))),
                   rel_gap=(best - Gopt) / abs(Gopt) if np.isfinite(best) else None, seconds=time.time() - t0)
        fo.write(json.dumps(row) + "\n"); fo.flush()
        extra = f" breaks {row['chain_break_share']:.2f}" if method == "emb" else ""
        print(f"{ref['key']:26s} {tag:10s} hit {row['hit']!s:5} share {row['hit_share']:.2f} feasible {row['feasible_share']:.2f} "
              f"gap {row['rel_gap'] if row['rel_gap'] is not None else float('nan'):+.2e}{extra} {row['seconds']:.0f}s", flush=True)


if __name__ == "__main__":
    out, method = sys.argv[1], sys.argv[2]
    opts = {}
    for a in sys.argv[3:]:
        key, v = a.split("=")
        opts[key] = v if key in ("keys", "tag") else (int(v) if v.lstrip("-").isdigit() else float(v))
    main(out, method, opts)
