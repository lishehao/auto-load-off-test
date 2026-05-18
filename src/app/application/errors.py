from __future__ import annotations


class ApplicationError(Exception):
    pass


class ValidationAppError(ApplicationError):
    pass


class InstrumentAppError(ApplicationError):
    pass


class PersistenceAppError(ApplicationError):
    pass


def describe_exception(exc: BaseException) -> str:
    message = str(exc)
    exc_type = type(exc).__name__
    if message:
        return f"{exc_type}: {message}"
    return exc_type
