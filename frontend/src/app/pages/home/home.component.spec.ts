/// <reference types="jasmine" />

import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { AltchaService } from '../../api/endpoints/altcha/altcha.service';
import type { LimitsResponse, QuotaResponse } from '../../api/model';
import { AuthService } from '../../services/auth.service';
import { FileService } from '../../services/file.service';
import { HomeComponent } from './home.component';

interface AltchaServiceStub {
  getChallengeApiAltchaChallengeGet: jasmine.Spy;
}

interface TestSubscription {
  unsubscribe: () => void;
}

interface TestObserver<T> {
  error?: (error: unknown) => void;
  next?: (value: T) => void;
}

interface TestStream<T> {
  next: (value: T) => void;
  subscribe: (observer: TestObserver<T> | ((value: T) => void)) => TestSubscription;
}

function createEmptyStream(): Pick<TestStream<unknown>, 'subscribe'> {
  return {
    subscribe: () => ({ unsubscribe: () => {} }),
  };
}

function createTestStream<T>(): TestStream<T> {
  const subscribers = new Set<TestObserver<T> | ((value: T) => void)>();

  return {
    next: (value: T) => {
      for (const subscriber of subscribers) {
        if (typeof subscriber === 'function') {
          subscriber(value);
        } else {
          subscriber.next?.(value);
        }
      }
    },
    subscribe: (observer: TestObserver<T> | ((value: T) => void)) => {
      subscribers.add(observer);

      return {
        unsubscribe: () => {
          subscribers.delete(observer);
        },
      };
    },
  };
}

function createAltchaServiceStub(): AltchaServiceStub {
  return {
    getChallengeApiAltchaChallengeGet: jasmine
      .createSpy('getChallengeApiAltchaChallengeGet')
      .and.returnValue(createEmptyStream()),
  };
}

class AuthServiceStub {
  readonly authenticated = signal(false);
  readonly limitsStream = createTestStream<LimitsResponse>();
  readonly quotaStream = createTestStream<QuotaResponse>();

  getLimits() {
    return this.limitsStream;
  }

  getQuota() {
    return this.quotaStream;
  }

  isAuthenticated(): boolean {
    return this.authenticated();
  }
}

describe('HomeComponent', () => {
  let altchaService: AltchaServiceStub = createAltchaServiceStub();
  let authService: AuthServiceStub = new AuthServiceStub();

  beforeEach(async () => {
    authService = new AuthServiceStub();
    altchaService = createAltchaServiceStub();

    await TestBed.configureTestingModule({
      imports: [HomeComponent],
      providers: [
        provideRouter([]),
        {
          provide: AltchaService,
          useValue: altchaService,
        },
        {
          provide: AuthService,
          useValue: authService,
        },
        {
          provide: FileService,
          useValue: {
            upload: jasmine.createSpy('upload'),
            uploadMultiple: jasmine.createSpy('uploadMultiple'),
          },
        },
      ],
    }).compileComponents();
  });

  it('refreshes quota when authentication changes after the page has loaded', async () => {
    const fixture = TestBed.createComponent(HomeComponent);
    const component = fixture.componentInstance;

    await fixture.whenStable();

    authService.limitsStream.next({
      expiry_options_hours: [24, 72],
      max_downloads_options: [1, 10],
      max_file_size_mb: 100,
      max_files_per_upload: 10,
      weekly_uploads_limit: 3,
    });
    await fixture.whenStable();

    expect(component.weeklyUploadsRemaining()).toBe(3);
    expect(component.isQuotaExhausted()).toBeFalse();

    authService.authenticated.set(true);
    await fixture.whenStable();

    authService.quotaStream.next({
      expiry_options_hours: [24, 72],
      max_downloads_options: [1, 10],
      max_file_size_mb: 100,
      max_files_per_upload: 10,
      weekly_upload_size_limit_bytes: 0,
      weekly_upload_size_remaining_bytes: 0,
      weekly_upload_size_used_bytes: 0,
      weekly_uploads_limit: 3,
      weekly_uploads_remaining: 3,
      weekly_uploads_used: 0,
    });
    await fixture.whenStable();

    expect(component.weeklyUploadsRemaining()).toBe(3);
    expect(component.isQuotaExhausted()).toBeFalse();
    expect(fixture.nativeElement.textContent).toContain('0 / 3 (3 left)');
    expect(fixture.nativeElement.textContent).not.toContain(
      'You’ve reached your weekly upload limit',
    );
  });

  it('ignores altcha expiry events while an upload is active', () => {
    const fixture = TestBed.createComponent(HomeComponent);
    const component = fixture.componentInstance;

    component.onAltchaStateChange(
      new CustomEvent('statechange', {
        detail: { payload: 'verified-payload', state: 'verified' },
      }),
    );

    expect(component.altchaVerified()).toBeTrue();
    expect(component.altchaState()).toBe('verified');
    expect(altchaService.getChallengeApiAltchaChallengeGet).toHaveBeenCalledTimes(1);

    component.isUploading.set(true);
    component.onAltchaStateChange(
      new CustomEvent('statechange', {
        detail: { state: 'expired' },
      }),
    );

    expect(component.altchaVerified()).toBeTrue();
    expect(component.altchaState()).toBe('verified');
    expect(altchaService.getChallengeApiAltchaChallengeGet).toHaveBeenCalledTimes(1);
  });
});
