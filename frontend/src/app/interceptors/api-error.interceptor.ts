import { HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import type { HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';
import { UiNotificationService } from '../services/ui-notification.service';
import { getErrorCode, getErrorDetail } from '../utils/error.utils';

export const apiErrorInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);
  const notifications = inject(UiNotificationService);
  const router = inject(Router);

  return next(req).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse) {
        const code = getErrorCode(error);
        const detail = getErrorDetail(error, 'Something went wrong.');
        const hasSession = authService.authenticated();

        if (error.status === 403 && code === 'ACCOUNT_BANNED' && hasSession) {
          authService.logout();
          notifications.error('Account unavailable', detail, {
            dedupeKey: 'account-banned',
            sticky: true,
          });
          if (router.url !== '/auth') {
            void router.navigate(['/auth']);
          }
        }

        if (
          error.status === 401 &&
          (code === 'SESSION_EXPIRED' || code === 'NOT_AUTHENTICATED') &&
          hasSession
        ) {
          authService.logout();
          notifications.warning('Session expired', detail, {
            dedupeKey: 'session-expired',
          });
          if (router.url !== '/auth') {
            void router.navigate(['/auth']);
          }
        }
      }

      return throwError(() => error);
    }),
  );
};
