class HoneybadgerbftError(Exception):
    """Base exception class."""


class BroadcastError(HoneybadgerbftError):
    """Base class for broadcast errors.""" 


class UnknownTagError(BroadcastError):
    """Raised when an unknown broadcast tag is detected."""
