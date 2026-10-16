"""Container entrypoint behaviour: the mount contract, the exit codes, and the
guarantee that the output directory describes this run and no earlier one.

The last one is why this file exists. A rejected re-run into a directory that still
held an earlier result used to leave that result sitting beside the new error.json,
and a reader would take the stale one for the current one.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from conftest import TOY

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location("norma_entrypoint", ROOT / "docker" / "entrypoint.py")
entrypoint = importlib.util.module_from_spec(_spec)
sys.modules["norma_entrypoint"] = entrypoint
_spec.loader.exec_module(entrypoint)


def _job(tmp_path: Path, request_obj: object | str) -> tuple[Path, Path]:
    in_dir, out_dir = tmp_path / "in", tmp_path / "out"
    in_dir.mkdir()
    text = request_obj if isinstance(request_obj, str) else json.dumps(request_obj)
    (in_dir / "request.json").write_text(text, encoding="utf-8")
    return in_dir, out_dir


@pytest.fixture(scope="module")
def toy_text() -> str:
    return TOY.read_text(encoding="utf-8")


def test_happy_path_writes_both_artifacts(tmp_path, toy_text):
    in_dir, out_dir = _job(tmp_path, toy_text)
    code = entrypoint.run_one(in_dir, out_dir, attempt_id="attempt-1")
    assert code == entrypoint.EXIT_OK
    result = json.loads((out_dir / "result.json").read_text(encoding="utf-8"))
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert result["status"] in ("SUCCEEDED", "PARTIAL")
    assert manifest["attempt_id"] == "attempt-1"
    assert not (out_dir / "error.json").exists()


def test_rejected_rerun_does_not_leave_the_previous_result(tmp_path, toy_text):
    """The output directory describes this run. A stale result must not survive it."""
    in_dir, out_dir = _job(tmp_path, toy_text)
    assert entrypoint.run_one(in_dir, out_dir) == entrypoint.EXIT_OK
    first = json.loads((out_dir / "result.json").read_text(encoding="utf-8"))["job_id"]

    (in_dir / "request.json").write_text('{"schema_version": "9.9"}', encoding="utf-8")
    assert entrypoint.run_one(in_dir, out_dir) == entrypoint.EXIT_INVALID_REQUEST

    assert not (out_dir / "result.json").exists(), f"stale result from job {first} survived a rejected re-run"
    assert not (out_dir / "manifest.json").exists()
    assert json.loads((out_dir / "error.json").read_text(encoding="utf-8"))["error"] == "INVALID_REQUEST"


def test_invalid_request_reports_every_violation_at_once(tmp_path):
    in_dir, out_dir = _job(tmp_path, {"schema_version": "1.0", "request_id": "x"})
    assert entrypoint.run_one(in_dir, out_dir) == entrypoint.EXIT_INVALID_REQUEST
    err = json.loads((out_dir / "error.json").read_text(encoding="utf-8"))
    fields = {i["field"] for i in err["issues"]}
    assert {"data", "constraints", "model", "execution"} <= fields  # not just the first one


def test_missing_request_is_reported_in_error_json(tmp_path):
    in_dir, out_dir = tmp_path / "in", tmp_path / "out"
    in_dir.mkdir()
    assert entrypoint.run_one(in_dir, out_dir) == entrypoint.EXIT_IO
    assert json.loads((out_dir / "error.json").read_text(encoding="utf-8"))["error"] == "REQUEST_NOT_FOUND"


def test_unreadable_request_is_reported(tmp_path):
    in_dir, out_dir = _job(tmp_path, "{not json")
    assert entrypoint.run_one(in_dir, out_dir) == entrypoint.EXIT_IO
    assert json.loads((out_dir / "error.json").read_text(encoding="utf-8"))["error"] == "UNREADABLE_REQUEST"


def test_budget_below_the_grid_is_refused_before_running(tmp_path, toy_text):
    raw = json.loads(toy_text)
    raw["execution"]["max_objective_evaluations"] = 10  # inside 1..60 but under grid 49 + final 1
    in_dir, out_dir = _job(tmp_path, raw)
    assert entrypoint.run_one(in_dir, out_dir) == entrypoint.EXIT_REFUSED
    assert json.loads((out_dir / "error.json").read_text(encoding="utf-8"))["error"] == "REFUSED"


def test_accepted_at_sets_the_queue_wait(tmp_path, toy_text):
    import time

    in_dir, out_dir = _job(tmp_path, toy_text)
    assert entrypoint.run_one(in_dir, out_dir, accepted_at=time.time() - 3.0) == entrypoint.EXIT_OK
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["queue_wait_ms"] >= 3000


def test_bad_accepted_at_still_clears_and_reports(tmp_path, toy_text):
    """A bad value must not take a shortcut past the clearing step (review F13)."""
    in_dir, out_dir = _job(tmp_path, toy_text)
    assert entrypoint.run_one(in_dir, out_dir) == entrypoint.EXIT_OK
    assert (out_dir / "result.json").exists()

    # main() is what argparse feeds, so drive the real path end to end.
    code = entrypoint.main(["--in", str(in_dir), "--out", str(out_dir),
                            "--accepted-at", "2026-10-16T05:00:00Z"])
    assert code == entrypoint.EXIT_IO
    assert not (out_dir / "result.json").exists(), "stale result survived a bad --accepted-at"
    assert not (out_dir / "manifest.json").exists()
    assert json.loads((out_dir / "error.json").read_text(encoding="utf-8"))["error"] == "BAD_ACCEPTED_AT"


def test_accepted_at_accepts_a_numeric_string(tmp_path, toy_text):
    import time

    in_dir, out_dir = _job(tmp_path, toy_text)
    assert entrypoint.main(["--in", str(in_dir), "--out", str(out_dir),
                            "--accepted-at", str(time.time() - 4.0)]) == entrypoint.EXIT_OK
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["queue_wait_ms"] >= 4000
