import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { environment } from '../environments/environment';
import { apiErrorInterceptor } from './interceptors/api-error.interceptor';
import { createApiBaseUrlInterceptor } from './interceptors/api-base-url.interceptor';
import { authInterceptor } from './interceptors/auth.interceptor';

const apiBaseUrlInterceptor = createApiBaseUrlInterceptor(environment.apiUrl);

export const appHttpProviders = [
  provideHttpClient(
    withInterceptors([apiBaseUrlInterceptor, authInterceptor, apiErrorInterceptor]),
  ),
];
