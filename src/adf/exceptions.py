"""Application-specific exceptions."""


class ADFError(Exception):
    """Base exception for expected ADF failures."""


class ConfigError(ADFError):
    """Raised when configuration cannot be loaded or validated."""


class OrganizationError(ADFError):
    """Raised when a file cannot be organized safely."""
