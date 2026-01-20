/**
 * Centralized error handling utilities for API errors.
 */

export interface APIError {
  error: string;
  message: string;
  type: string;
}

export class ErrorHandler {
  /**
   * Extract user-friendly error message from various error formats.
   */
  static extractMessage(error: any): string {
    // Handle axios errors
    if (error?.response?.data?.detail) {
      const detail = error.response.data.detail;

      // Structured error response (from our backend)
      if (typeof detail === 'object' && detail.message) {
        return detail.message;
      }

      // Array of validation errors (FastAPI default format)
      if (Array.isArray(detail)) {
        const messages = detail.map((err: any) => {
          const loc = err.loc?.join(' → ') || 'unknown';
          const msg = err.msg || 'Invalid value';
          return `${loc}: ${msg}`;
        });
        return messages.join('\n');
      }

      // String error response
      if (typeof detail === 'string') {
        return detail;
      }
    }

    // Handle standard Error objects
    if (error?.message) {
      return error.message;
    }

    // Handle string errors
    if (typeof error === 'string') {
      return error;
    }

    // Fallback
    return 'An unexpected error occurred. Please try again.';
  }

  /**
   * Extract error type from error response.
   */
  static extractType(error: any): string {
    if (error?.response?.data?.detail?.type) {
      return error.response.data.detail.type;
    }
    return 'unknown_error';
  }

  /**
   * Check if error is a validation error.
   */
  static isValidationError(error: any): boolean {
    const type = ErrorHandler.extractType(error);
    return type === 'validation_error' || type === 'value_error';
  }

  /**
   * Check if error is a server error.
   */
  static isServerError(error: any): boolean {
    const type = ErrorHandler.extractType(error);
    return type === 'server_error';
  }

  /**
   * Format error for display in UI.
   */
  static formatForDisplay(error: any): {
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

    // Extract title from error response if available
    if (error?.response?.data?.detail?.error) {
      title = error.response.data.detail.error;
    }

    return { title, message, type };
  }
}
