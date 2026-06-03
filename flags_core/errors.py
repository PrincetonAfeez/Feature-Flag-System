"""Domain errors for feature flag evaluation and validation."""


class FlagError(Exception):
    """Base error for feature flag domain failures."""


class FlagNotFoundError(FlagError):
    """Raised when a flag key is not present in a source that should contain it."""


class FlagAlreadyExistsError(FlagError):
    """Raised when creating a flag whose key is already active in the environment."""


class RuleNotFoundError(FlagError):
    """Raised when a rule id is not present on the flag it should belong to."""


class EnvironmentNotFoundError(FlagError):
    """Raised when an environment slug does not exist and must not be auto-created."""


class SchemaError(FlagError):
    """Base error for invalid flag definitions."""


class FlagValidationError(SchemaError):
    """Raised when a flag definition is invalid."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


class SnapshotError(FlagError):
    """Raised when snapshot serialization or parsing fails."""


class StaleConfigError(FlagError):
    """Reserved for the V1 client SDK when a caller requires a fresh snapshot.

    Not raised by the MVP server or core; see ``docs/roadmap.md``.
    """
