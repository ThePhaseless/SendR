import type { ApplicationConfig } from '@angular/core';
import { provideRouter } from '@angular/router';
import { routes } from './app.routes';
import { appHttpProviders } from './http-providers';

export const appConfig: ApplicationConfig = {
  providers: [provideRouter(routes), ...appHttpProviders],
};
