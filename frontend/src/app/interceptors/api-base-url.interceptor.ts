import type { HttpInterceptorFn } from '@angular/common/http';
import { resolveApiUrl } from '../utils/url.utils';

export function createApiBaseUrlInterceptor(apiUrl: string): HttpInterceptorFn {
  return (req, next) => {
    if (!req.url.startsWith('/api')) {
      return next(req);
    }

    return next(req.clone({ url: resolveApiUrl(req.url, apiUrl) }));
  };
}
