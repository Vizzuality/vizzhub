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

/** The backend's `detail` message when it is a plain string, otherwise `fallback`. */
export function getApiErrorDetail(error: unknown, fallback: string): string {
  const detail = (error as AxiosError<ApiErrorResponse> | null)?.response?.data?.detail;
  return typeof detail === 'string' ? detail : fallback;
}
