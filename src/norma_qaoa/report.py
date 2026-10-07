"""Multi-seed comparison of QAOA runs against classical references (markdown).

Classical numbers (exhaustive, random) are reference data and are labelled as such.
"""

from __future__ import annotations

import copy
import json
import statistics
from pathlib import Path
from typing import Any

from norma_qaoa.baseline import exhaustive_baseline, penalty_check, random_baseline
from norma_qaoa.candidates import ORIGIN_SAMPLE, aggregate_counts
from norma_qaoa.config import EngineConfig
from norma_qaoa.engine import run_job
from norma_qaoa.objective import is_feasible, objective_penalized
from norma_qaoa.problem import Problem
from norma_qaoa.qaoa import derive_seeds
from norma_qaoa.schema import validate_request


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def seed_row(problem: Problem, ex, out, seed: int) -> dict[str, Any]:
    result, manifest = out.result, out.manifest
    counts = manifest.get("final_counts") or {}
    agg = aggregate_counts(problem, counts) if counts else {}
    shots = sum(agg.values())
    feasible_shots = sum(c for x, c in agg.items() if is_feasible(problem, x))
    feasible_fs = [objective_penalized(problem, x) for x in agg if is_feasible(problem, x)]
    best_f = min(feasible_fs) if feasible_fs else None
    opt_vectors = set(ex.optimal_bit_vectors())
    rb = random_baseline(problem, manifest["shots"]["per_circuit"], derive_seeds(seed)["random_baseline"])
    return {
        "seed": seed,
        "status": result["status"],
        "stop_reason": result["stop_reason"],
        "counts_phase": (manifest.get("counts_source") or {}).get("phase"),
        "best_f": best_f,
        "gap": None if best_f is None else best_f - ex.optimum.objective_penalized,
        "rank": None if best_f is None else ex.rank_of(best_f),
        "optimum_count": sum(c for x, c in agg.items() if x in opt_vectors),
        "shots": shots,
        "feasible_ratio_qaoa": feasible_shots / shots if shots else None,
        "distinct_feasible_qaoa": len(feasible_fs),
        "feasible_ratio_random": rb["feasible_ratio"],
        "best_f_random": rb["best_objective_penalized"],
        "rank_random": None if rb["best_objective_penalized"] is None else ex.rank_of(rb["best_objective_penalized"]),
        "n_candidates": len(result["candidates"]),
        "n_candidates_sample": sum(1 for c in result["candidates"] if c["origin"] == ORIGIN_SAMPLE),
        "elapsed_ms": result["execution"]["elapsed_ms"],
        "evaluations": result["execution"]["objective_evaluations"],
        "circuits": result["execution"]["circuits_total"],
        "job_id": result["job_id"],
    }


def _fmt(v: Any, digits: int = 6) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def _stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "median": None, "max": None, "variance": None}
    return {
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
        "variance": statistics.variance(values) if len(values) > 1 else 0.0,
    }


def build_report(raw: dict, n_seeds: int, config: EngineConfig, runs_dir: Path, input_label: str) -> tuple[str, dict]:
    req = validate_request(raw, config)
    problem = Problem.from_request(req)
    ex = exhaustive_baseline(problem)
    pc = penalty_check(problem)
    base_seed = req.execution.seed
    seeds = [base_seed + i for i in range(n_seeds)]

    rows = []
    for s in seeds:
        r = copy.deepcopy(raw)
        r["execution"]["seed"] = s
        out = run_job(r, config)
        _write_json(runs_dir / f"seed_{s}" / "result.json", out.result)
        _write_json(runs_dir / f"seed_{s}" / "manifest.json", out.manifest)
        rows.append(seed_row(problem, ex, out, s))

    worst = ex.ranking[-1].objective_penalized
    opt = ex.optimum
    best_fs = [r["best_f"] for r in rows if r["best_f"] is not None]
    gaps = [r["gap"] for r in rows if r["gap"] is not None]
    data = {
        "input": input_label,
        "backend": config.backend,
        "seeds": seeds,
        "n_k_subsets": ex.n_k_subsets,
        "n_feasible": ex.n_feasible,
        "classical_optimum": opt.to_dict(problem),
        "feasible_f_range": [opt.objective_penalized, worst],
        "penalty_check": pc,
        "rows": rows,
        "best_f_stats": _stats(best_fs),
        "gap_stats": _stats(gaps),
    }

    inc = [problem.asset_ids[i] for i in problem.include]
    exc = [problem.asset_ids[i] for i in problem.exclude]
    L = []
    L.append(f"# QAOA 실행 비교 리포트: `{input_label}`\n")
    L.append("이 리포트는 시뮬레이터 실행 결과와 고전 기준값(전수 탐색, 균등 무작위)을 같은 F로 비교합니다. "
             "고전 기준값은 비교용이며 양자 실행 결과가 아닙니다. sample_count와 비율은 회로 출력 분포를 센 값입니다.\n")
    L.append("## 문제와 실행 설정\n")
    L.append(f"- N = {problem.n}, K = {problem.K}, must_include = {inc}, must_exclude = {exc}")
    L.append(f"- K개 부분집합 전체: C({problem.n},{problem.K}) = {ex.n_k_subsets}개, 그중 feasible: **{ex.n_feasible}개** (순위의 분모)")
    L.append(f"- 백엔드: `{config.backend}`, depth = {req.execution.depth}, shots/circuit = {req.execution.shots_per_circuit}, "
             f"평가 예산 = {req.execution.max_objective_evaluations} (격자 {config.grid_size}x{config.grid_size}, "
             f"최종 샘플링 예산 포함 = {config.count_final_in_budget})")
    L.append(f"- seed: {seeds}")
    L.append(f"- 벌점 계수: Lk = {problem.Lk}, Lf = {problem.Lf}\n")
    L.append("## 고전 기준 (classical_baseline)\n")
    L.append(f"- 전수 최적: {opt.to_dict(problem)['selected_asset_ids']}, F = {opt.objective_penalized:.6f}")
    L.append(f"- feasible {ex.n_feasible}개의 F 범위: [{opt.objective_penalized:.6f}, {worst:.6f}] (폭 {worst - opt.objective_penalized:.6f})")
    L.append(f"- 벌점 충분성 검사 (2^{problem.n}개 전체): {'통과' if pc['passed'] else '미통과'}, "
             f"infeasible 최저 F − feasible 최저 F = {_fmt(pc['margin_infeasible_minus_feasible'])}\n")
    L.append("## seed별 결과\n")
    L.append("| seed | status / stop_reason | 최선 F (표본) | 최적 대비 격차 | 순위 (/" + str(ex.n_feasible) + ") | 최적해 출현 횟수 | "
             "feasible 비율 QAOA | feasible 비율 random | random 최선 F (순위) | 유효 후보 수 | 실행시간 (ms) |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        L.append(
            f"| {r['seed']} | {r['status']} / {r['stop_reason']} | {_fmt(r['best_f'])} | {_fmt(r['gap'])} | {_fmt(r['rank'])} | "
            f"{r['optimum_count']} / {r['shots']} | {_fmt(r['feasible_ratio_qaoa'], 4)} | {_fmt(r['feasible_ratio_random'], 4)} | "
            f"{_fmt(r['best_f_random'])} ({_fmt(r['rank_random'])}) | {r['n_candidates']} | {r['elapsed_ms']} |"
        )
    L.append("")
    L.append("- 최선 F (표본): 최종 샘플링에서 관측된 feasible 비트열 중 가장 낮은 F")
    L.append("- 순위: feasible 조합 중 F 경쟁 순위 (1 = 전수 최적, 동점 허용오차 1e-9)")
    L.append("- random: QAOA와 같은 shots 수의 균등 무작위 비트열 (seed는 master seed에서 파생)\n")
    L.append("## seed 전체 요약\n")
    bs, gs = data["best_f_stats"], data["gap_stats"]
    L.append(f"- 최선 F: 최소 {_fmt(bs['min'])}, 중앙값 {_fmt(bs['median'])}, 최대 {_fmt(bs['max'])}, 표본분산(ddof=1) {_fmt(bs['variance'], 10)}")
    L.append(f"- 최적 대비 격차: 최소 {_fmt(gs['min'])}, 중앙값 {_fmt(gs['median'])}, 최대 {_fmt(gs['max'])}")
    n_hit = sum(1 for r in rows if r["optimum_count"] > 0)
    L.append(f"- 최종 표본에 전수 최적 조합이 한 번 이상 나온 seed: {n_hit} / {len(rows)}")
    fq = [r["feasible_ratio_qaoa"] for r in rows if r["feasible_ratio_qaoa"] is not None]
    fr = [r["feasible_ratio_random"] for r in rows]
    if fq:
        L.append(f"- feasible 비율 중앙값: QAOA {statistics.median(fq):.4f}, random {statistics.median(fr):.4f}")
    L.append("")
    L.append(f"seed별 result.json / manifest.json: `{runs_dir.as_posix()}`\n")
    return "\n".join(L), data
