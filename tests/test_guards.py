"""Guards: no hardware/cloud SDK imports, and no wording that recasts sample counts."""

import json
import re
import subprocess
import sys
from pathlib import Path

from conftest import ROOT, TOY

HARDWARE_MODULES = ("qiskit_ibm_runtime", "qnexus", "qiskit_ibm_provider")
# Spec p.9/p.14: sample counts are not chances of investment outcomes. "SUCCEEDED" (a spec
# status literal) does not match these patterns.
FORBIDDEN = re.compile(r"확률|성공|수익|probabilit|success|profit", re.IGNORECASE)


def _texts():
    files = list((ROOT / "src").rglob("*.py")) + list((ROOT / "scripts").rglob("*.py"))
    files += [f for f in (ROOT / "tests").rglob("*.py") if f.name != "test_guards.py"]
    files += list((ROOT / "reports").glob("*.md"))
    return files


def test_no_hardware_imports_in_source():
    pattern = re.compile(r"^\s*(from|import)\s+(" + "|".join(HARDWARE_MODULES) + r")\b", re.MULTILINE)
    for f in (ROOT / "src").rglob("*.py"):
        assert not pattern.search(f.read_text(encoding="utf-8")), f


def test_hardware_modules_not_loaded_after_job():
    code = (
        "import json, sys; from norma_qaoa.engine import run_job; "
        f"run_job(json.load(open(r'{TOY}', encoding='utf-8'))); "
        f"print(json.dumps([m for m in {HARDWARE_MODULES!r} if m in sys.modules]))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert json.loads(out.stdout.strip().splitlines()[-1]) == []


def test_forbidden_wording():
    hits = []
    for f in _texts():
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if FORBIDDEN.search(line):
                hits.append(f"{f.relative_to(ROOT)}:{n}: {line.strip()}")
    assert not hits, "\n".join(hits)


def test_forbidden_wording_in_outputs(tmp_path):
    from norma_qaoa.engine import run_job

    out = run_job(json.loads(Path(TOY).read_text(encoding="utf-8")))
    blob = json.dumps(out.result, ensure_ascii=False) + json.dumps(out.manifest, ensure_ascii=False)
    assert not FORBIDDEN.search(blob)
