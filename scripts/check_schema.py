#!/usr/bin/env python3
"""Generate and verify the published JSON Schemas for the request and result documents.

The schemas under docs/schema/ are generated from the same pydantic models the engine
validates with, so they cannot drift from what the engine actually accepts. This script
is both the generator (`--write`) and the check:

  * regenerate from the models and compare byte for byte with the committed files
  * validate the shipped fixture as a request
  * run the fixture through the engine and validate the produced result

No JSON Schema library is used, and none is needed: the models are the source of truth,
so validating through them is stronger than validating against their own output.

Shape is all a JSON Schema can carry. Dimension agreement, matrix symmetry, positive
semidefiniteness and constraint consistency are checked by the engine, not by the
schema - docs/io-contract.md lists them.

  scripts/check_schema.py            verify (exit 1 on any mismatch)
  scripts/check_schema.py --write    regenerate the committed schemas
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "docs" / "schema"
FIXTURE = ROOT / "fixtures" / "synthetic_12_6.json"

sys.path.insert(0, str(ROOT / "src"))

from norma_qaoa.schema import Request, Result  # noqa: E402

DOCS = (("request", Request), ("result", Result))


def render(model) -> str:
    schema = model.model_json_schema(mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = f"norma-qaoa {model.__name__} (schema_version 1.0)"
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="regenerate the committed schema files")
    args = ap.parse_args(argv)

    failures: list[str] = []
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)

    for name, model in DOCS:
        path = SCHEMA_DIR / f"{name}.schema.json"
        text = render(model)
        if args.write:
            path.write_text(text, encoding="utf-8")
            print(f"  wrote {path.relative_to(ROOT)} ({len(text)} bytes)")
            continue
        if not path.exists():
            failures.append(f"{path.relative_to(ROOT)} is missing (run with --write)")
        elif path.read_text(encoding="utf-8") != text:
            failures.append(f"{path.relative_to(ROOT)} is stale; regenerate with --write")
        else:
            print(f"  [ok] {path.relative_to(ROOT)} matches the model")

    if args.write:
        print("schemas written")
        return 0

    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    try:
        Request.model_validate(raw)
        print(f"  [ok] {FIXTURE.relative_to(ROOT)} validates as a request")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"fixture does not validate as a request: {exc}")

    from norma_qaoa.engine import run_job

    out = run_job(raw)
    try:
        Result.model_validate(out.result)
        print(f"  [ok] produced result validates (status {out.result['status']}, "
              f"{len(out.result['candidates'])} candidates)")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"produced result does not validate: {exc}")

    spec_top = {"schema_version", "request_id", "job_id", "status", "stop_reason", "snapshot_id",
                "model_version", "asset_order", "candidates", "execution", "artifact_manifest_id",
                "proven_infeasible"}
    missing = spec_top - set(out.result)
    extra = set(out.result) - spec_top
    if missing:
        failures.append(f"result is missing spec p.12 fields: {sorted(missing)}")
    if extra:
        failures.append(f"result carries fields the spec's example does not: {sorted(extra)}")
    if not missing and not extra:
        print("  [ok] result top level matches the spec's example exactly (no missing, no extra)")

    for f in failures:
        print(f"  [FAIL] {f}", file=sys.stderr)
    print("schema check: OK" if not failures else f"schema check: {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
