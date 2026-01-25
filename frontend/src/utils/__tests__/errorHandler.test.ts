import { describe, it, expect } from 'vitest';
import { ErrorHandler } from '../errorHandler';

describe('ErrorHandler', () => {
  describe('extractMessage', () => {
    it('extracts message from structured axios error with detail.message', () => {
      const error = {
        response: {
          data: {
            detail: {
              message: 'Invalid project ID',
              error: 'Validation Error',
              type: 'validation_error',
            },
          },
        },
      };

      expect(ErrorHandler.extractMessage(error)).toBe('Invalid project ID');
    });

    it('extracts message from array of validation errors', () => {
      const error = {
        response: {
          data: {
            detail: [
              { loc: ['body', 'name'], msg: 'field required' },
              { loc: ['body', 'email'], msg: 'invalid email format' },
            ],
          },
        },
      };

      const result = ErrorHandler.extractMessage(error);
      expect(result).toContain('body \u2192 name: field required');
      expect(result).toContain('body \u2192 email: invalid email format');
    });

    it('extracts message from string detail', () => {
      const error = {
        response: {
          data: {
            detail: 'Project not found',
          },
        },
      };

      expect(ErrorHandler.extractMessage(error)).toBe('Project not found');
    });

    it('extracts message from standard Error object', () => {
      const error = new Error('Network connection failed');

      expect(ErrorHandler.extractMessage(error)).toBe('Network connection failed');
    });

    it('handles string errors directly', () => {
      const error = 'Something went wrong';

      expect(ErrorHandler.extractMessage(error)).toBe('Something went wrong');
    });

    it('returns fallback message for unknown error format', () => {
      const error = { unknownField: 'data' };

      expect(ErrorHandler.extractMessage(error)).toBe('An unexpected error occurred. Please try again.');
    });

    it('returns fallback for null error', () => {
      expect(ErrorHandler.extractMessage(null)).toBe('An unexpected error occurred. Please try again.');
    });

    it('returns fallback for undefined error', () => {
      expect(ErrorHandler.extractMessage(undefined)).toBe('An unexpected error occurred. Please try again.');
    });

    it('handles validation error with missing loc', () => {
      const error = {
        response: {
          data: {
            detail: [
              { msg: 'field required' },
            ],
          },
        },
      };

      const result = ErrorHandler.extractMessage(error);
      expect(result).toContain('unknown: field required');
    });

    it('handles validation error with missing msg', () => {
      const error = {
        response: {
          data: {
            detail: [
              { loc: ['body', 'name'] },
            ],
          },
        },
      };

      const result = ErrorHandler.extractMessage(error);
      expect(result).toContain('body \u2192 name: Invalid value');
    });
  });

  describe('extractType', () => {
    it('extracts type from error response', () => {
      const error = {
        response: {
          data: {
            detail: {
              type: 'validation_error',
            },
          },
        },
      };

      expect(ErrorHandler.extractType(error)).toBe('validation_error');
    });

    it('returns unknown_error for missing type', () => {
      const error = {
        response: {
          data: {
            detail: {},
          },
        },
      };

      expect(ErrorHandler.extractType(error)).toBe('unknown_error');
    });

    it('returns unknown_error for null error', () => {
      expect(ErrorHandler.extractType(null)).toBe('unknown_error');
    });

    it('returns unknown_error for error without response', () => {
      const error = new Error('Network error');

      expect(ErrorHandler.extractType(error)).toBe('unknown_error');
    });
  });

  describe('isValidationError', () => {
    it('returns true for validation_error type', () => {
      const error = {
        response: {
          data: {
            detail: {
              type: 'validation_error',
            },
          },
        },
      };

      expect(ErrorHandler.isValidationError(error)).toBe(true);
    });

    it('returns true for value_error type', () => {
      const error = {
        response: {
          data: {
            detail: {
              type: 'value_error',
            },
          },
        },
      };

      expect(ErrorHandler.isValidationError(error)).toBe(true);
    });

    it('returns false for other error types', () => {
      const error = {
        response: {
          data: {
            detail: {
              type: 'server_error',
            },
          },
        },
      };

      expect(ErrorHandler.isValidationError(error)).toBe(false);
    });

    it('returns false for unknown error', () => {
      expect(ErrorHandler.isValidationError(null)).toBe(false);
    });
  });

  describe('isServerError', () => {
    it('returns true for server_error type', () => {
      const error = {
        response: {
          data: {
            detail: {
              type: 'server_error',
            },
          },
        },
      };

      expect(ErrorHandler.isServerError(error)).toBe(true);
    });

    it('returns false for validation_error type', () => {
      const error = {
        response: {
          data: {
            detail: {
              type: 'validation_error',
            },
          },
        },
      };

      expect(ErrorHandler.isServerError(error)).toBe(false);
    });

    it('returns false for unknown error', () => {
      expect(ErrorHandler.isServerError(null)).toBe(false);
    });
  });

  describe('formatForDisplay', () => {
    it('returns validation error title for validation errors', () => {
      const error = {
        response: {
          data: {
            detail: {
              message: 'Invalid input data',
              type: 'validation_error',
            },
          },
        },
      };

      const result = ErrorHandler.formatForDisplay(error);

      expect(result.title).toBe('Validation Error');
      expect(result.message).toBe('Invalid input data');
      expect(result.type).toBe('validation_error');
    });

    it('returns server error title for server errors', () => {
      const error = {
        response: {
          data: {
            detail: {
              message: 'Internal server error',
              type: 'server_error',
            },
          },
        },
      };

      const result = ErrorHandler.formatForDisplay(error);

      expect(result.title).toBe('Server Error');
      expect(result.message).toBe('Internal server error');
      expect(result.type).toBe('server_error');
    });

    it('uses error title from response if available', () => {
      const error = {
        response: {
          data: {
            detail: {
              error: 'Custom Error Title',
              message: 'Something went wrong',
              type: 'custom_error',
            },
          },
        },
      };

      const result = ErrorHandler.formatForDisplay(error);

      expect(result.title).toBe('Custom Error Title');
      expect(result.message).toBe('Something went wrong');
    });

    it('returns generic Error title for unknown errors', () => {
      const error = new Error('Unknown problem');

      const result = ErrorHandler.formatForDisplay(error);

      expect(result.title).toBe('Error');
      expect(result.message).toBe('Unknown problem');
      expect(result.type).toBe('unknown_error');
    });

    it('handles null error gracefully', () => {
      const result = ErrorHandler.formatForDisplay(null);

      expect(result.title).toBe('Error');
      expect(result.message).toBe('An unexpected error occurred. Please try again.');
      expect(result.type).toBe('unknown_error');
    });

    it('handles error with value_error type', () => {
      const error = {
        response: {
          data: {
            detail: {
              message: 'Invalid value provided',
              type: 'value_error',
            },
          },
        },
      };

      const result = ErrorHandler.formatForDisplay(error);

      expect(result.title).toBe('Validation Error');
      expect(result.message).toBe('Invalid value provided');
    });
  });
});
