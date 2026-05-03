class MesahubError(Exception):
    def __init__(
        self,
        code: str,
        status_code: int,
        message: str,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.details = details or {}

    @classmethod
    def from_response(
        cls, status_code: int, status_text: str, body: dict | None
    ) -> "MesahubError":
        data = body or {}
        code = data.get("code", "UNKNOWN_ERROR")
        message = data.get("message", status_text)
        return cls(code, status_code, message, data)


class AuthenticationError(MesahubError):
    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__("AUTH_ERROR", 401, message)


class AuthorizationError(MesahubError):
    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__("AUTHZ_ERROR", 403, message)


class NotFoundError(MesahubError):
    def __init__(self, resource: str) -> None:
        super().__init__("NOT_FOUND", 404, f"{resource} not found")


class RateLimitError(MesahubError):
    def __init__(self, retry_after: int | None = None) -> None:
        super().__init__(
            "RATE_LIMIT", 429, "Rate limit exceeded", {"retry_after": retry_after}
        )


class ValidationError(MesahubError):
    def __init__(
        self, message: str = "Validation failed", details: dict | None = None
    ) -> None:
        super().__init__("VALIDATION_ERROR", 400, message, details)
