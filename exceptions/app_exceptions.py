class SIAMException(Exception):
    """Base exception for all SIAM application errors."""

    status_code: int = 500
    description: str = "Error interno del servidor"

    def __init__(self, description: str | None = None, status_code: int | None = None) -> None:
        if description is not None:
            self.description = description
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.description)


class NotFoundException(SIAMException):
    status_code: int = 404
    description: str = "Recurso no encontrado"


class ValidationException(SIAMException):
    status_code: int = 400
    description: str = "Error de validación"

    def __init__(self, errors: dict[str, list[str]] | None = None, **kwargs) -> None:
        self.errors: dict[str, list[str]] = errors or {}
        super().__init__(**kwargs)


class BusinessRuleException(SIAMException):
    status_code: int = 409
    description: str = "Regla de negocio violada"


class AuthenticationException(SIAMException):
    status_code: int = 401
    description: str = "No autenticado"


class AuthorizationException(SIAMException):
    status_code: int = 403
    description: str = "No autorizado"
