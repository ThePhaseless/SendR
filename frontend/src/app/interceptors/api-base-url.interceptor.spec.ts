/// <reference types="jasmine" />

import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { createApiBaseUrlInterceptor } from './api-base-url.interceptor';

describe('createApiBaseUrlInterceptor', () => {
  let http: HttpClient;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([createApiBaseUrlInterceptor('https://api.sendr.app')])),
        provideHttpClientTesting(),
      ],
    });

    http = TestBed.inject(HttpClient);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it('rewrites relative api requests to the configured backend origin', () => {
    http.get('/api/auth/me').subscribe();

    httpTesting.expectOne('https://api.sendr.app/api/auth/me').flush({});
  });

  it('leaves non-api requests unchanged', () => {
    http.get('/assets/logo.svg').subscribe();

    httpTesting.expectOne('/assets/logo.svg').flush('');
  });
});
