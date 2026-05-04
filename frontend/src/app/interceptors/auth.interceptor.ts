import type { HttpInterceptorFn } from '@angular/common/http';

const UNSAFE_METHODS = new Set(['DELETE', 'PATCH', 'POST', 'PUT']);
const CSRF_COOKIE_NAME = 'sendr_csrf';
const CSRF_HEADER_NAME = 'X-CSRF-Token';

function getCookie(name: string): string | null {
  const prefix = `${name}=`;
  const value = document.cookie
    .split(';')
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));
  return value ? decodeURIComponent(value.slice(prefix.length)) : null;
}

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const csrfToken = UNSAFE_METHODS.has(req.method.toUpperCase())
    ? getCookie(CSRF_COOKIE_NAME)
    : null;
  const headers = csrfToken ? req.headers.set(CSRF_HEADER_NAME, csrfToken) : req.headers;

  return next(req.clone({ headers, withCredentials: true }));
};
