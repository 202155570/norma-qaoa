#!/usr/bin/env python3
"""Container entrypoint: one job per run.

Reads a request from <in>/request.json, writes <out>/result.json and
<out>/manifest.json. This is the same work the `norma_qaoa run` CLI does; the
entrypoint exists to fix the mount contract and the exit codes so a batch
scheduler can act on the outcome without parsing JSON.

Mount contract (spec p.5, "동일 입출력 계약을 유지한 컨테이너 배치 연동"):

    docker run --rm -v ./job:/in:ro -v ./out:/out norma-qaoa:<tag>

Paths come from NORMA_IN_DIR / NORMA_OUT_DIR (defaults /in and /out) and may be
overridden with --in/--out, which is how the self-test runs it off a container.

Exit codes - a result file was produced iff the code is 0 or 1:

      0  result.json written, status SUCCEEDED or PARTIAL
      1  result.json written, status FAILED (no usable candidate)
     10  request rejected: schema, dimension, version or constraint conflict
     11  refused by configuration or policy (e.g. a backend this build may not use)
     12  input/output problem: request missing or unreadable, output not writable
     13  unexpected failure

On any code >= 10 an error.json is written to the output directory instead of a
result, carrying the same issue list the engine raises. Nothing is ever written
to the output directory on code 12 when the directory itself is the problem.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
import uuid
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_FAILED_STATUS = 1
EXIT_INVALID_REQUEST = 10
EXIT_REFUSED = 11
EXIT_IO = 12
EXIT_UNEXPECTED = 13

REQUEST_NAME = "request.json"
RESULT_NAME = "result.json"
MANIFEST_NAME = "manifest.json"
ERROR_NAME = "error.json"


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def _error_doc(code: str, message: str, issues: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "error": code,
        "message": message,
        "issues": issues or [],
        "engine": "norma-qaoa",
        "recorded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def run_one(in_dir: Path, out_dir: Path, *, attempt_id: str | None = None) -> int:
    """Run the request in `in_dir` and write the artifacts to `out_dir`. Returns an exit code."""
    accepted_at = time.time()  # the request is accepted the moment we can read it

    request_path = in_dir / REQUEST_NAME
    try:
        raw = json.loads(request_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"no request at {request_path}", file=sys.stderr)
        return EXIT_IO
    except (OSError, json.JSONDecodeError) as exc:
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            _write_json(out_dir / ERROR_NAME, _error_doc("UNREADABLE_REQUEST", f"{type(exc).__name__}: {exc}"))
        except OSError:
            pass
        print(f"request at {request_path} is not readable JSON: {exc}", file=sys.stderr)
        return EXIT_IO

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        probe = out_dir / ".write-probe"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        print(f"output directory {out_dir} is not writable: {exc}", file=sys.stderr)
        return EXIT_IO

    # Imported here so that --help and an I/O failure do not pay for loading qiskit.
    from norma_qaoa.config import EngineConfig
    from norma_qaoa.engine import run_job
    from norma_qaoa.errors import BackendNotAllowedError, BackendUnavailableError, ConfigError, InputValidationError

    config_path = os.environ.get("NORMA_CONFIG") or None
    try:
        config = EngineConfig.load(config_path)
    except (ConfigError, OSError, ValueError) as exc:
        _write_json(out_dir / ERROR_NAME, _error_doc("CONFIG_ERROR", f"{type(exc).__name__}: {exc}"))
        print(f"configuration rejected: {exc}", file=sys.stderr)
        return EXIT_REFUSED

    try:
        out = run_job(raw, config, attempt_id=attempt_id, accepted_at=accepted_at)
    except InputValidationError as exc:
        _write_json(out_dir / ERROR_NAME, _error_doc("INVALID_REQUEST", str(exc), [i.to_dict() for i in exc.issues]))
        print(f"request rejected: {exc}", file=sys.stderr)
        return EXIT_INVALID_REQUEST
    except (BackendNotAllowedError, BackendUnavailableError, ConfigError) as exc:
        _write_json(out_dir / ERROR_NAME, _error_doc("REFUSED", f"{type(exc).__name__}: {exc}"))
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except Exception as exc:  # noqa: BLE001 - the container must report, not crash silently
        _write_json(
            out_dir / ERROR_NAME,
            _error_doc("UNEXPECTED", f"{type(exc).__name__}: {exc}",
                       [{"code": "TRACEBACK", "field": "-", "message": traceback.format_exc()}]),
        )
        print(f"unexpected failure: {exc}", file=sys.stderr)
        return EXIT_UNEXPECTED

    _write_json(out_dir / RESULT_NAME, out.result)
    _write_json(out_dir / MANIFEST_NAME, out.manifest)
    (out_dir / ERROR_NAME).unlink(missing_ok=True)

    status = out.result["status"]
    print(
        "status={status} candidates={n} job_id={job} attempt={attempt} elapsed_ms={ms}".format(
            status=status,
            n=len(out.result["candidates"]),
            job=out.result["job_id"],
            attempt=out.manifest["attempt_id"],
            ms=out.result["execution"]["elapsed_ms"],
        )
    )
    return EXIT_FAILED_STATUS if status == "FAILED" else EXIT_OK


def selftest() -> int:
    """Run the bundled fixture through the real path and check the artifacts.

    This is the container's own acceptance check: it proves the mount contract and the
    schema, and it runs identically on a developer machine and inside the image.
    """
    import tempfile

    fixture = Path(__file__).resolve().parent.parent / "fixtures" / "synthetic_12_6.json"
    if not fixture.exists():
        print(f"selftest: fixture not found at {fixture}", file=sys.stderr)
        return EXIT_IO

    with tempfile.TemporaryDirectory() as tmp:
        in_dir, out_dir = Path(tmp) / "in", Path(tmp) / "out"
        in_dir.mkdir()
        (in_dir / REQUEST_NAME).write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

        code = run_one(in_dir, out_dir, attempt_id="attempt-selftest")
        if code not in (EXIT_OK, EXIT_FAILED_STATUS):
            print(f"selftest: entrypoint returned {code}", file=sys.stderr)
            return code

        result = json.loads((out_dir / RESULT_NAME).read_text(encoding="utf-8"))
        manifest = json.loads((out_dir / MANIFEST_NAME).read_text(encoding="utf-8"))

        from norma_qaoa.schema import Result

        Result.model_validate(result)  # raises if the shape drifted from the contract

        checks: list[tuple[str, bool]] = [
            ("result validates against the Result schema", True),
            ("request_id echoed", result["request_id"] == "synthetic-12-6-001"),
            ("asset_order has 12 entries", len(result["asset_order"]) == 12),
            ("at least one candidate", len(result["candidates"]) >= 1),
            ("manifest attempt_id honoured", manifest["attempt_id"] == "attempt-selftest"),
            ("manifest records queue wait", isinstance(manifest["queue_wait_ms"], int)),
            ("manifest records container identity", "image_digest" in manifest["container"]),
            ("manifest records cpu seconds", isinstance(manifest["resources"]["cpu_seconds"], float)),
            ("manifest hashes present", len(manifest["input_hash"]) == 64),
        ]
        bad = [name for name, ok in checks if not ok]
        for name, ok in checks:
            print(f"  [{'ok' if ok else 'FAIL'}] {name}")
        if bad:
            print(f"selftest: {len(bad)} check(s) failed", file=sys.stderr)
            return EXIT_UNEXPECTED

    print("selftest: OK")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="norma-qaoa-container", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--in", dest="in_dir", default=os.environ.get("NORMA_IN_DIR", "/in"),
                        help="directory holding request.json (default: /in, or NORMA_IN_DIR)")
    parser.add_argument("--out", dest="out_dir", default=os.environ.get("NORMA_OUT_DIR", "/out"),
                        help="directory for result.json and manifest.json (default: /out, or NORMA_OUT_DIR)")
    parser.add_argument("--attempt-id", default=os.environ.get("NORMA_ATTEMPT_ID") or None,
                        help="identifier for this attempt; a retry of the same request uses a new one")
    parser.add_argument("--selftest", action="store_true",
                        help="run the bundled fixture end to end and verify the artifacts")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    attempt_id = args.attempt_id or f"attempt-{uuid.uuid4()}"
    return run_one(Path(args.in_dir), Path(args.out_dir), attempt_id=attempt_id)


if __name__ == "__main__":
    sys.exit(main())
