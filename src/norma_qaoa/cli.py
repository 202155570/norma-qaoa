"""Command line interface.

  python -m norma_qaoa run      --input <json> --out <dir> [--config <json>] [--backend aer|quantinuum_local]
  python -m norma_qaoa baseline --input <json> [--out <json>]
  python -m norma_qaoa report   --input <json> --seeds 5 [--out <md>] [--runs-dir <dir>] [--config <json>] [--backend ...]

Exit codes: 0 = job finished with SUCCEEDED/PARTIAL (or baseline/report done),
1 = job FAILED, 2 = invalid input/config or backend refused/unavailable.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from norma_qaoa.backends.registry import BACKEND_NAMES
from norma_qaoa.baseline import exhaustive_baseline, penalty_check
from norma_qaoa.config import EngineConfig
from norma_qaoa.errors import BackendNotAllowedError, BackendUnavailableError, ConfigError, InputValidationError
from norma_qaoa.problem import Problem
from norma_qaoa.schema import validate_request


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _dump(obj) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def _config(args) -> EngineConfig:
    cfg = EngineConfig.load(getattr(args, "config", None))
    if getattr(args, "backend", None):
        cfg = cfg.model_copy(update={"backend": args.backend})
    return cfg


def cmd_run(args) -> int:
    from norma_qaoa.engine import run_job

    out = run_job(_load_json(args.input), _config(args))
    d = Path(args.out)
    d.mkdir(parents=True, exist_ok=True)
    (d / "result.json").write_text(_dump(out.result), encoding="utf-8")
    (d / "manifest.json").write_text(_dump(out.manifest), encoding="utf-8")
    r = out.result
    print(f"status={r['status']} stop_reason={r['stop_reason']} candidates={len(r['candidates'])} "
          f"backend={r['execution']['backend_name']} elapsed_ms={r['execution']['elapsed_ms']} -> {d}")
    return 1 if r["status"] == "FAILED" else 0


def cmd_baseline(args) -> int:
    p = Problem.from_request(validate_request(_load_json(args.input)))
    data = exhaustive_baseline(p).to_dict(p)
    data["penalty_check"] = penalty_check(p)
    text = _dump(data)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        opt = data["optimum"]
        print(f"n_feasible={data['n_feasible']} n_k_subsets={data['n_k_subsets']} "
              f"optimum={opt['selected_asset_ids']} F={opt['objective_penalized']!r} -> {args.out}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_report(args) -> int:
    from norma_qaoa.report import build_report

    cfg = _config(args)
    stem = Path(args.input).stem
    runs_dir = Path(args.runs_dir or f"out/report_{stem}_{cfg.backend}")
    md, data = build_report(_load_json(args.input), args.seeds, cfg, runs_dir, Path(args.input).as_posix())
    out = Path(args.out or f"reports/{stem}_report.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    (runs_dir / "report_data.json").write_text(_dump(data), encoding="utf-8")
    print(f"report -> {out} (runs: {runs_dir})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="norma_qaoa")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run one QAOA job on a circuit simulator")
    r.add_argument("--input", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--config")
    r.add_argument("--backend", choices=BACKEND_NAMES)
    r.set_defaults(fn=cmd_run)

    b = sub.add_parser("baseline", help="classical exhaustive baseline (comparison only)")
    b.add_argument("--input", required=True)
    b.add_argument("--out")
    b.set_defaults(fn=cmd_baseline)

    p = sub.add_parser("report", help="multi-seed comparison report (markdown)")
    p.add_argument("--input", required=True)
    p.add_argument("--seeds", type=int, default=5)
    p.add_argument("--out")
    p.add_argument("--runs-dir")
    p.add_argument("--config")
    p.add_argument("--backend", choices=BACKEND_NAMES)
    p.set_defaults(fn=cmd_report)
    return ap


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except InputValidationError as exc:
        sys.stderr.write(_dump(exc.to_dict()))
        return 2
    except (ConfigError, BackendNotAllowedError, BackendUnavailableError) as exc:
        sys.stderr.write(_dump({"error": type(exc).__name__, "message": str(exc)}))
        return 2
