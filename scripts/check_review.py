#!/usr/bin/env python3
"""Check an independent review verdict file.

Not a judgement of the review's content - only that it is a usable verdict:
it exists, it states a verdict, every finding it raises has a disposition, and
no MUST-FIX is left open.

  scripts/check_review.py docs/YYYY-MM-DD-<slug>-review.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

VERDICTS = ("PASS WITH FIXES", "PASS", "FAIL")
FINDING = re.compile(r"^\s*-\s*\[(MUST-FIX|SHOULD-FIX|NOTE)\]\s*(F\d+)\b", re.MULTILINE)
DISPOSITION = re.compile(r"^\s*-\s*(F\d+)\s*:\s*(.+)$", re.MULTILINE)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.exists():
        print(f"  [FAIL] {path} does not exist", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")

    failures: list[str] = []

    # A re-review appends a new verdict rather than editing the old one, so the verdict in
    # force is the last one in the file, not the first.
    verdict_lines = [l for l in text.splitlines() if l.strip().startswith("Verdict:")]
    verdict_line = verdict_lines[-1] if verdict_lines else None
    if len(verdict_lines) > 1:
        print(f"  [ok] {len(verdict_lines)} verdicts; the last one is in force")
    if verdict_line is None:
        failures.append("no 'Verdict:' line")
        verdict = None
    else:
        stated = verdict_line.split(":", 1)[1].strip()
        verdict = next((v for v in VERDICTS if stated.upper().startswith(v)), None)
        if verdict is None:
            failures.append(f"verdict {stated!r} is not one of {VERDICTS}")
        else:
            print(f"  [ok] verdict: {verdict}")

    findings = {m.group(2): m.group(1) for m in FINDING.finditer(text)}
    dispositions = {m.group(1): m.group(2).strip() for m in DISPOSITION.finditer(text)}
    # A disposition line repeats the finding id, so ids that appear only in the
    # findings list are the undisposed ones.
    print(f"  [ok] {len(findings)} finding(s): " + (", ".join(f"{k}={v}" for k, v in sorted(findings.items())) or "none"))

    for fid, severity in sorted(findings.items()):
        text_disp = dispositions.get(fid)
        if not text_disp:
            failures.append(f"{fid} ({severity}) has no disposition")
            continue
        if severity == "MUST-FIX" and not re.search(r"\b(applied|accepted by the operator)\b", text_disp, re.I):
            failures.append(f"{fid} is a MUST-FIX still open: {text_disp!r}")

    if verdict == "FAIL" and not findings:
        failures.append("verdict is FAIL but no finding is listed")

    for f in failures:
        print(f"  [FAIL] {f}", file=sys.stderr)
    print("review check: OK" if not failures else f"review check: {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
