"""
Error Definitions

Defines custom exception classes used in the application for unified error handling.
"""

from typing import Any, Optional


class AppError(Exception):
    """
    Application Base Exception
    
    Base class for all custom exceptions, containing error message, type, and code.
    """
    
    def __init__(
        self,
        message: str,
        error_type: str = "app_error",
        code: str = "internal_error",
        details: Optional[dict[str, Any]] = None,
        status_code: int = 500,
    ):
        """
        Initialize exception
        
        Args:
            message: Error message
            error_type: Error type
            code: Error code
            details: Extra error details
            status_code: HTTP status code
        """
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.code = code
        self.details = details or {}
        self.status_code = status_code
    
    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary format (for API response)
        
        Returns:
            dict: Error information dictionary
        """
        result = {
            "error": {
                "message": self.message,
                "type": self.error_type,
                "code": self.code,
            }
        }
        if self.details:
            result["error"]["details"] = self.details
        return result


class AuthenticationError(AppError):
    """
    Authentication Error
    
    Raised when API Key is invalid or disabled.
    """
    
    def __init__(
        self,
        message: str = "Authentication failed",
        code: str = "invalid_api_key",
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_type="authentication_error",
            code=code,
            details=details,
            status_code=401,
        )


class NotFoundError(AppError):
    """
    Resource Not Found Error
    
    Raised when requested resource (e.g., model, provider) does not exist.
    """
    
    def __init__(
        self,
        message: str = "Resource not found",
        code: str = "not_found",
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_type="not_found_error",
            code=code,
            details=details,
            status_code=404,
        )


class ConflictError(AppError):
    """
    Resource Conflict Error
    
    Raised when resource already exists (e.g., duplicate name) or cannot be deleted due to references.
    """
    
    def __init__(
        self,
        message: str = "Resource conflict",
        code: str = "conflict",
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_type="conflict_error",
            code=code,
            details=details,
            status_code=409,
        )


class ValidationError(AppError):
    """
    Parameter Validation Error
    
    Raised when request parameters do not meet requirements.
    """
    
    def __init__(
        self,
        message: str = "Validation failed",
        code: str = "validation_error",
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_type="validation_error",
            code=code,
            details=details,
            status_code=422,
        )


class UpstreamError(AppError):
    """
    Upstream Service Error
    
    Raised when upstream provider returns an error or all providers fail.
    """
    
    def __init__(
        self,
        message: str = "Upstream service error",
        code: str = "upstream_error",
        details: Optional[dict[str, Any]] = None,
        status_code: int = 502,
    ):
        super().__init__(
            message=message,
            error_type="upstream_error",
            code=code,
            details=details,
            status_code=status_code,
        )


class ServiceError(AppError):
    """
    Service Error
    
    Raised when internal service processing fails (e.g., no available provider).
    """
    
    def __init__(
        self,
        message: str = "Service error",
        code: str = "service_error",
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_type="service_error",
            code=code,
            details=details,
            status_code=503,
        )