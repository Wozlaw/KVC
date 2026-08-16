"""Repository-level persistence contracts."""


class PersistenceInvariantError(RuntimeError):
    """Raised when a repository operation would violate a persistence invariant."""
