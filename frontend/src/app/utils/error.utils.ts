import { HttpErrorResponse } from '@angular/common/http';

/**
 * Extract the `detail` field from a backend error response,
 * falling back to the given message if unavailable.
 */
export function getErrorDetail(error: unknown, fallback: string): string {
  if (
    !(error instanceof HttpErrorResponse) ||
    typeof error.error !== 'object' ||
    error.error === null
  ) {
    return fallback;
  }

  const detail: unknown = Reflect.get(error.error, 'detail');
  if (typeof detail === 'string') {
    return detail;
  }

  return fallback;
}
