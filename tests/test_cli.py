import json

from conftest import SYNTH, TOY
from norma_qaoa.cli import main


def test_run_writes_outputs(tmp_path):
    assert main(["run", "--input", str(TOY), "--out", str(tmp_path / "toy")]) == 0
    r = json.loads((tmp_path / "toy" / "result.json").read_text(encoding="utf-8"))
    m = json.loads((tmp_path / "toy" / "manifest.json").read_text(encoding="utf-8"))
    assert r["job_id"] == m["job_id"] and r["status"] == "PARTIAL"


def test_run_invalid_input_exit_2(tmp_path, capsys, toy_raw):
    toy_raw["execution"]["allow_qpu"] = True
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(toy_raw), encoding="utf-8")
    assert main(["run", "--input", str(bad), "--out", str(tmp_path / "o")]) == 2
    err = json.loads(capsys.readouterr().err)
    assert err["issues"][0]["code"] == "QPU_NOT_ALLOWED"
    assert not (tmp_path / "o").exists()


def test_baseline_cli(tmp_path):
    out = tmp_path / "b.json"
    assert main(["baseline", "--input", str(SYNTH), "--out", str(out)]) == 0
    d = json.loads(out.read_text(encoding="utf-8"))
    assert d["n_feasible"] == 462 and d["n_k_subsets"] == 924 and d["origin"] == "classical_baseline"
    assert d["penalty_check"]["passed"] is True


def test_report_cli(tmp_path):
    md = tmp_path / "r.md"
    runs = tmp_path / "runs"
    assert main(["report", "--input", str(TOY), "--seeds", "2", "--out", str(md), "--runs-dir", str(runs)]) == 0
    text = md.read_text(encoding="utf-8")
    assert "| seed |" in text and "/3)" in text
    assert (runs / "seed_7" / "result.json").exists() and (runs / "seed_8" / "manifest.json").exists()
