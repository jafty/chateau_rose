class DomainError(Exception):
    """Base class for domain-specific errors."""


class ValidationError(DomainError):
    """Raised when inputs violate domain validation rules."""


class InvalidState(DomainError):
    """Raised when a state transition is not allowed."""


class PermissionError(DomainError):
    """Raised when an actor is not allowed to perform an action."""


class NotFound(DomainError):
    """Raised when an aggregate cannot be found."""
