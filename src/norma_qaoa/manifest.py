"""Canonical hashing and environment versions.

Hash rule: SHA-256 of canonical JSON = json.dumps(sort_keys=True, separators=(",", ":"),
allow_nan=False, ensure_ascii=False) encoded as UTF-8. Floats are serialized with repr
(Python's json default); numpy scalars/arrays are converted to Python types first.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import numpy as np

# The process cannot read its own image digest, so the container entrypoint injects it.
CONTAINER_ENV = ("NORMA_IMAGE_REF", "NORMA_IMAGE_DIGEST", "NORMA_IMAGE_BUILT_UTC")

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


def container_identity() -> dict[str, Any]:
    """Which image produced this result (spec p.19: "SDK/컨테이너 digest").

    A process cannot read its own image digest, so the entrypoint passes it in as
    environment variables at container start. Every field is null outside a container;
    that is a true record of "not run from an image", not a measurement failure.
    """
    ref = os.environ.get("NORMA_IMAGE_REF") or None
    digest = os.environ.get("NORMA_IMAGE_DIGEST") or None
    return {
        "image_ref": ref,
        "image_digest": digest,
        "image_built_utc": os.environ.get("NORMA_IMAGE_BUILT_UTC") or None,
        "in_container": bool(ref or digest) or os.path.exists("/.dockerenv"),
        "source": "environment: " + ", ".join(CONTAINER_ENV),
    }


def resource_usage(cpu_seconds: float) -> dict[str, Any]:
    """Resource usage for this job (spec p.19: "자원 사용량"), standard library only.

    `cpu_seconds` is this job's own CPU time, measured as a `time.process_time` delta.
    `max_rss_bytes` is the process-wide high-water mark the OS reports, not this job's
    alone - there is no interval form of it - and it is null off POSIX, where the
    `resource` module does not exist. GPU is never measured: the simulator runs on CPU.
    """
    out: dict[str, Any] = {
        "cpu_seconds": round(float(cpu_seconds), 6),
        "cpu_user_seconds": None,
        "cpu_system_seconds": None,
        "max_rss_bytes": None,
        "max_rss_scope": "process high-water mark, not this job alone",
        "gpu": None,
        "gpu_note": "not measured; the simulator backend runs on CPU",
        "source": "time.process_time",
    }
    try:
        import resource  # POSIX only; absent on Windows
    except ImportError:
        out["max_rss_note"] = f"resource module unavailable on {sys.platform}"
        return out
    ru = resource.getrusage(resource.RUSAGE_SELF)
    # ru_maxrss is kilobytes on Linux and bytes on macOS.
    out["max_rss_bytes"] = int(ru.ru_maxrss) * (1 if sys.platform == "darwin" else 1024)
    out["cpu_user_seconds"] = round(float(ru.ru_utime), 6)
    out["cpu_system_seconds"] = round(float(ru.ru_stime), 6)
    out["source"] = "time.process_time + resource.getrusage(RUSAGE_SELF)"
    return out
