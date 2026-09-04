"""Structured, agent-repairable errors. A rejected write always says which field and why."""

from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class FieldError:
    field: str
    reason: str

    def as_dict(self) -> dict[str, str]:
        return {"field": self.field, "reason": self.reason}


class MemoryStoreError(Exception):
    """Base for every error the core raises."""

    code = "memory_error"

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "message": str(self)}


class ValidationError(MemoryStoreError):
    code = "validation_error"

    def __init__(self, errors: list[FieldError]):
        self.errors = errors
        super().__init__("; ".join(f"{error.field}: {error.reason}" for error in errors))

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "errors": [error.as_dict() for error in self.errors]}


class NotFoundError(MemoryStoreError):
    code = "not_found"


class LockTimeoutError(MemoryStoreError):
    code = "lock_timeout"
