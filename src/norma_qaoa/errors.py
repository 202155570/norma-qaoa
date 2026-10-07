"""Error types. Every error carries a machine-readable code and the offending field."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Issue:
    code: str
    field: str
    message: str

    def to_dict(self) -> dict:
        return {"code": self.code, "field": self.field, "message": self.message}


class InputValidationError(ValueError):
    """The request violates the contract (spec Appendix A). Nothing is auto-corrected."""

    def __init__(self, issues: list[Issue]):
        self.issues = list(issues)
        super().__init__("; ".join(f"[{i.code}] {i.field}: {i.message}" for i in self.issues))

    def to_dict(self) -> dict:
        return {"error": "INPUT_VALIDATION", "issues": [i.to_dict() for i in self.issues]}


class ConfigError(ValueError):
    """Engine configuration is inconsistent with the request (e.g. budget too small for the grid)."""


class BackendNotAllowedError(RuntimeError):
    """A backend was refused by the execution policy (QPU / external transfer)."""


class BackendUnavailableError(RuntimeError):
    """A backend's optional dependencies are missing or cannot be loaded."""
