"""Centralized error handling utilities."""

from pydantic import ValidationError
from fastapi import HTTPException


class ValidationErrorHandler:
    """Handles validation errors with user-friendly messages."""

    @staticmethod
    def format_pydantic_error(error: ValidationError) -> str:
        """Convert Pydantic validation errors to user-friendly messages."""
        messages = []

        for err in error.errors():
            error_type = err["type"]
            msg = err.get("msg", "")

            # If error message already includes parameter name (from our custom validator)
            # use it directly
            if error_type == "value_error" and "Parameter '" in msg:
                messages.append(msg)
                continue

            # Otherwise, build the message
            field_path = " → ".join(str(loc) for loc in err["loc"])
            value = err.get("input")

            if error_type == "decimal_parsing":
                messages.append(
                    f"Parameter '{field_path}': Expected a numeric value, "
                    f"got '{value}' instead. Please enter a valid number (e.g., 0.5, 100, 3.14)."
                )
            elif error_type == "decimal_type":
                messages.append(
                    f"Parameter '{field_path}': Expected a numeric value, "
                    f"got {type(value).__name__} instead. Please enter a valid number."
                )
            elif error_type == "missing":
                messages.append(f"Parameter '{field_path}': This field is required.")
            elif error_type == "string_type":
                messages.append(
                    f"Parameter '{field_path}': Invalid value '{value}'. {msg}"
                )
            else:
                # Generic fallback - use message from validator if available
                if msg:
                    messages.append(msg)
                else:
                    messages.append(f"Parameter '{field_path}': Invalid value")

        return "\n".join(messages)

    @staticmethod
    def to_http_exception(
        error: Exception, status_code: int = 400
    ) -> HTTPException:
        """Convert various errors to HTTPException with structured response."""

        if isinstance(error, ValidationError):
            message = ValidationErrorHandler.format_pydantic_error(error)
            return HTTPException(
                status_code=status_code,
                detail={
                    "error": "Validation Error",
                    "message": message,
                    "type": "validation_error",
                },
            )

        elif isinstance(error, ValueError):
            return HTTPException(
                status_code=status_code,
                detail={
                    "error": "Invalid Input",
                    "message": str(error),
                    "type": "value_error",
                },
            )

        else:
            # Don't expose internal errors to users
            return HTTPException(
                status_code=500,
                detail={
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred. Please try again or contact support.",
                    "type": "server_error",
                },
            )
