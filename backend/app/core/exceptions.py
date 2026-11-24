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


class ChannelDisabledError(AgentDeskException):
    """Raised when an operation is attempted on a disabled communication channel."""

    def __init__(self, message: str = "Channel is currently disabled for this business.", status_code: int = 403):
        super().__init__(message=message, status_code=status_code)


class ChatDisabledError(ChannelDisabledError):
    """Raised when chat execution is attempted for a business with chat_enabled=False."""

    def __init__(self, message: str = "Chat is currently disabled for this business."):
        super().__init__(message=message, status_code=403)


class VoiceDisabledError(ChannelDisabledError):
    """Raised when voice execution or session creation is attempted with voice_enabled=False."""

    def __init__(self, message: str = "Voice is currently disabled for this business."):
        super().__init__(message=message, status_code=403)
