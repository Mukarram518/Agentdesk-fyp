"""AgentDesk Core Exceptions."""


class AgentDeskException(Exception):
    """Base exception for all AgentDesk domain errors."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ConfigurationError(AgentDeskException):
    """Raised when environment or service configuration is invalid."""

    def __init__(self, message: str):
        super().__init__(message, status_code=500)


class ServiceUnavailableError(AgentDeskException):
    """Raised when an infrastructure dependency is unavailable."""

    def __init__(self, service_name: str, details: str = ""):
        msg = f"Service '{service_name}' is unavailable"
        if details:
            msg += f": {details}"
        super().__init__(msg, status_code=503)
