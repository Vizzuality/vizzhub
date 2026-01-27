/**
 * Centralized error handling utilities for API errors.
 */

export interface APIError {
  error: string;
  message: string;
  type: string;
}

interface ValidationErrorItem {
  loc?: string[];
  msg?: string;
}

interface StructuredErrorDetail {
  message?: string;
  type?: string;
  error?: string;
}

interface AxiosErrorResponse {
  response?: {
    data?: {
      detail?: string | ValidationErrorItem[] | StructuredErrorDetail;
    };
  };
  message?: string;
}

function isAxiosError(error: unknown): error is AxiosErrorResponse {
  return typeof error === 'object' && error !== null && 'response' in error;
}

function isStructuredDetail(detail: unknown): detail is StructuredErrorDetail {
  return (
    typeof detail === 'object' &&
    detail !== null &&
    ('message' in detail || 'type' in detail || 'error' in detail)
  );
}

function isValidationErrorArray(detail: unknown): detail is ValidationErrorItem[] {
  return Array.isArray(detail);
}

export class ErrorHandler {
  /**
   * Extract user-friendly error message from various error formats.
   */
  static extractMessage(error: unknown): string {
    if (isAxiosError(error) && error.response?.data?.detail) {
      const detail = error.response.data.detail;

      if (isStructuredDetail(detail) && detail.message) {
        return detail.message;
      }

      if (isValidationErrorArray(detail)) {
        const messages = detail.map((err) => {
          const loc = err.loc?.join(' → ') || 'unknown';
          const msg = err.msg || 'Invalid value';
          return `${loc}: ${msg}`;
        });
        return messages.join('\n');
      }

      if (typeof detail === 'string') {
        return detail;
      }
    }

    if (error instanceof Error) {
      return error.message;
    }

    if (typeof error === 'string') {
      return error;
    }

    return 'An unexpected error occurred. Please try again.';
  }

  /**
   * Extract error type from error response.
   */
  static extractType(error: unknown): string {
    if (isAxiosError(error)) {
      const detail = error.response?.data?.detail;
      if (isStructuredDetail(detail) && detail.type) {
        return detail.type;
      }
    }
    return 'unknown_error';
  }

  /**
   * Check if error is a validation error.
   */
  static isValidationError(error: unknown): boolean {
    const type = ErrorHandler.extractType(error);
    return type === 'validation_error' || type === 'value_error';
  }

  /**
   * Check if error is a server error.
   */
  static isServerError(error: unknown): boolean {
    const type = ErrorHandler.extractType(error);
    return type === 'server_error';
  }

  /**
   * Format error for display in UI.
   */
  static formatForDisplay(error: unknown): {
    title: string;
    message: string;
    type: string;
  } {
    const message = ErrorHandler.extractMessage(error);
    const type = ErrorHandler.extractType(error);

    let title = 'Error';

    if (ErrorHandler.isValidationError(error)) {
      title = 'Validation Error';
    } else if (ErrorHandler.isServerError(error)) {
      title = 'Server Error';
    }

    if (isAxiosError(error)) {
      const detail = error.response?.data?.detail;
      if (isStructuredDetail(detail) && detail.error) {
        title = detail.error;
      }
    }

    return { title, message, type };
  }
}
