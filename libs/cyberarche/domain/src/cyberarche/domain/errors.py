"""Domain errors. The single inbound seam maps these to transport codes."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain errors."""


class NotFound(DomainError):
    """The referenced resource does not exist (or is outside the caller's scope)."""


class NotAuthorized(DomainError):
    """The caller lacks the permission required for this action."""


class NotAuthenticated(DomainError):
    """The caller could not be identified (missing/invalid credentials)."""


class ValidationFailed(DomainError):
    """The request is structurally valid but violates a domain invariant."""


class Conflict(DomainError):
    """The action conflicts with current state (e.g. duplicate, stale)."""
