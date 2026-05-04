import { HttpErrorResponse } from '@angular/common/http';

const ERROR_CODE_MAP: Record<string, string> = {
  ACCOUNT_BANNED: 'This account has been banned. Contact support if you believe this is a mistake.',
  NOT_AUTHENTICATED: 'Sign in to continue.',
  SESSION_EXPIRED: 'Your session expired. Sign in again to continue.',
};

const ERROR_MESSAGE_MAP: Record<string, string> = {
  'Account is banned':
    'This account has been banned. Contact support if you believe this is a mistake.',
  'Invalid or expired token': 'Your session expired. Sign in again to continue.',
  'Not authenticated': 'Sign in to continue.',
};

export function toUserFacingErrorMessage(message: string): string {
  return ERROR_CODE_MAP[message] ?? ERROR_MESSAGE_MAP[message] ?? message;
}

export function getErrorCode(error: unknown): string | null {
  if (
    !(error instanceof HttpErrorResponse) ||
    typeof error.error !== 'object' ||
    error.error === null
  ) {
    return null;
  }

  const detail: unknown = Reflect.get(error.error, 'detail');
  if (typeof detail !== 'object' || detail === null) {
    return null;
  }

  const code: unknown = Reflect.get(detail, 'code');
  return typeof code === 'string' ? code : null;
}

/**
 * Extract the `detail` field from a backend error response and normalize it
 * into a user-facing message, falling back to the given message if unavailable.
 */
export function getErrorDetail(error: unknown, fallback: string): string {
  if (
    !(error instanceof HttpErrorResponse) ||
    typeof error.error !== 'object' ||
    error.error === null
  ) {
    return toUserFacingErrorMessage(fallback);
  }

  const detail: unknown = Reflect.get(error.error, 'detail');
  if (typeof detail === 'object' && detail !== null) {
    const message: unknown = Reflect.get(detail, 'message');
    if (typeof message === 'string') {
      return toUserFacingErrorMessage(message);
    }
  }

  if (typeof detail === 'string') {
    return toUserFacingErrorMessage(detail);
  }

  return toUserFacingErrorMessage(fallback);
}
