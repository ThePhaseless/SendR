import { provideHttpClient, withInterceptors } from "@angular/common/http";
import type { ApplicationConfig } from "@angular/core";
import { authInterceptor } from "./interceptors/auth.interceptor";
import { provideApi } from "./api";
import { provideRouter } from "@angular/router";
import { provideZoneChangeDetection } from "@angular/core";
import { routes } from "./app.routes";
import { environment } from "../environments/environment";

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(withInterceptors([authInterceptor])),
    provideApi({ basePath: environment.apiUrl }),
  ],
};
