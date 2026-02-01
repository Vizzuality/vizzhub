import { AxiosError } from 'axios';
import type { ApiErrorResponse } from '../types';

interface ErrorMessageDefaults {
  conflict?: string;
  badRequest?: string;
  fallback: string;
}

export function getApiErrorMessage(
  error: Error,
  defaults: ErrorMessageDefaults,
): string {
  const axiosError = error as AxiosError<ApiErrorResponse>;
  const detail = axiosError.response?.data?.detail;

  if (axiosError.response?.status === 409) {
    return detail ?? defaults.conflict ?? 'Resource conflict';
  }
  if (axiosError.response?.status === 400) {
    return detail ?? defaults.badRequest ?? 'Invalid request';
  }
  return defaults.fallback;
}
