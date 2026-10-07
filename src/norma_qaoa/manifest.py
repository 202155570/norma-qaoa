"""Canonical hashing and environment versions.

Hash rule: SHA-256 of canonical JSON = json.dumps(sort_keys=True, separators=(",", ":"),
allow_nan=False, ensure_ascii=False) encoded as UTF-8. Floats are serialized with repr
(Python's json default); numpy scalars/arrays are converted to Python types first.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import numpy as np

HASH_RULE = (
    "sha256(canonical_json); canonical_json = json.dumps(obj, sort_keys=True, "
    "separators=(',',':'), allow_nan=False, ensure_ascii=False); floats via repr"
)


def to_jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return to_jsonable(obj.tolist())
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    return obj


def canonical_json(obj: Any) -> str:
    return json.dumps(to_jsonable(obj), sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=False)


def sha256_of(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def environment_versions() -> dict[str, Any]:
    out: dict[str, Any] = {"python": sys.version.split()[0], "platform": platform.platform()}
    for pkg in ("qiskit", "qiskit-aer", "numpy", "scipy", "pydantic", "rustworkx"):
        try:
            out[pkg] = version(pkg)
        except PackageNotFoundError:
            out[pkg] = None
    return out
