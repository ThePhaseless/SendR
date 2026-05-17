import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { apiErrorInterceptor } from './interceptors/api-error.interceptor';
import { authInterceptor } from './interceptors/auth.interceptor';

export const appHttpProviders = [
  provideHttpClient(withInterceptors([authInterceptor, apiErrorInterceptor])),
];
