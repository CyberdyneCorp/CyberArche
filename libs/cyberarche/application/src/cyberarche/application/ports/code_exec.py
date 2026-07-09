"""Code-execution port (code-execution spec): run Python in a sandbox and get
back its output plus any figures/tables it produced. The adapter owns the
provider (the Cyberdyne Python Interpreter); use cases stay provider-agnostic."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CodeImage:
    filename: str
    content: bytes
    content_type: str


@dataclass(frozen=True, slots=True)
class CodeExecutionResult:
    success: bool
    stdout: str
    stderr: str
    result: str | None
    error: str | None
    images: list[CodeImage] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)  # inline text/HTML/JSON outputs


class CodeExecutionPort(Protocol):
    async def run(
        self, code: str, *, auth_token: str | None = None
    ) -> CodeExecutionResult:
        """Execute Python. Never raises for user-code errors — those come back as
        success=False with the detail in `error`/`stderr`. May raise only for
        transport/infrastructure failures.

        `auth_token`, when given, is the caller's bearer to run as (the
        interpreter authorizes per-user); adapters fall back to a service token
        when it is absent.
        """
        ...
