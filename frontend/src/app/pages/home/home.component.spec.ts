/// <reference types="jasmine" />

import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ScanStatus } from '../../api/model';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { FileService } from '../../services/file.service';
import { HomeComponent } from './home.component';

class AuthServiceStub {
  readonly authenticated = signal(false);

  isAuthenticated(): boolean {
    return this.authenticated();
  }
}

describe('HomeComponent', () => {
  let authService: AuthServiceStub = new AuthServiceStub();
  let httpTesting: HttpTestingController;

  beforeEach(async () => {
    authService = new AuthServiceStub();

    await TestBed.configureTestingModule({
      imports: [HomeComponent],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
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

    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it('refreshes quota when authentication changes after the page has loaded', async () => {
    const fixture = TestBed.createComponent(HomeComponent);
    const component = fixture.componentInstance;

    fixture.detectChanges();

    httpTesting.expectOne('/api/altcha/challenge').flush({ challenge: 'challenge' });
    httpTesting.expectOne('/api/auth/limits').flush({
      expiry_options_hours: [24, 72],
      max_downloads_options: [1, 10],
      max_file_size_mb: 100,
      max_files_per_upload: 10,
      weekly_uploads_limit: 3,
    });
    await fixture.whenStable();
    fixture.detectChanges();

    expect(component.weeklyUploadsRemaining()).toBe(3);
    expect(component.isQuotaExhausted()).toBeFalse();

    authService.authenticated.set(true);
    fixture.detectChanges();

    httpTesting.expectOne('/api/auth/quota').flush({
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
    fixture.detectChanges();

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

    fixture.detectChanges();

    httpTesting.expectOne('/api/altcha/challenge').flush({ challenge: 'challenge' });
    httpTesting.expectOne('/api/auth/limits').flush({
      expiry_options_hours: [24, 72],
      max_downloads_options: [1, 10],
      max_file_size_mb: 100,
      max_files_per_upload: 10,
      weekly_uploads_limit: 3,
    });

    component.onAltchaStateChange(
      new CustomEvent('statechange', {
        detail: { payload: 'verified-payload', state: 'verified' },
      }),
    );

    expect(component.altchaVerified()).toBeTrue();
    expect(component.altchaState()).toBe('verified');

    component.isUploading.set(true);
    component.onAltchaStateChange(
      new CustomEvent('statechange', {
        detail: { state: 'expired' },
      }),
    );

    expect(component.altchaVerified()).toBeTrue();
    expect(component.altchaState()).toBe('verified');
    httpTesting.expectNone('/api/altcha/challenge');
  });

  it('disables upload settings fields while upload is in progress', async () => {
    const fixture = TestBed.createComponent(HomeComponent);
    const component = fixture.componentInstance;

    fixture.detectChanges();

    httpTesting.expectOne('/api/altcha/challenge').flush({ challenge: 'challenge' });
    httpTesting.expectOne('/api/auth/limits').flush({
      expiry_options_hours: [24, 72],
      max_downloads_options: [1, 10],
      max_file_size_mb: 100,
      max_files_per_upload: 10,
      weekly_uploads_limit: 3,
    });
    await fixture.whenStable();

    component.pendingFiles.set([
      {
        file: new File(['demo'], 'demo.txt', { type: 'text/plain' }),
        mimeType: 'text/plain',
        name: 'demo.txt',
        size: 4,
      },
    ]);
    component.isUploading.set(true);
    fixture.detectChanges();

    const root = fixture.nativeElement as HTMLElement;
    const titleInput = root.querySelector<HTMLInputElement>('#title');
    const descriptionInput = root.querySelector<HTMLTextAreaElement>('#description');
    const expirySelect = root.querySelector<HTMLSelectElement>('#expiry');

    expect(titleInput).not.toBeNull();
    expect(descriptionInput).not.toBeNull();
    expect(expirySelect).not.toBeNull();
    expect(titleInput!.matches(':disabled')).toBeTrue();
    expect(descriptionInput!.matches(':disabled')).toBeTrue();
    expect(expirySelect!.matches(':disabled')).toBeTrue();
  });

  it('shows a background scan notice after upload succeeds with a queued status', async () => {
    const fixture = TestBed.createComponent(HomeComponent);
    const component = fixture.componentInstance;

    fixture.detectChanges();

    httpTesting.expectOne('/api/altcha/challenge').flush({ challenge: 'challenge' });
    httpTesting.expectOne('/api/auth/limits').flush({
      expiry_options_hours: [24, 72],
      max_downloads_options: [1, 10],
      max_file_size_mb: 100,
      max_files_per_upload: 10,
      weekly_uploads_limit: 3,
    });
    await fixture.whenStable();

    component.singleUploadResult.set({
      download_count: 0,
      download_url: 'https://sendr.local/api/files/token-1',
      expires_at: '2030-01-02T00:00:00Z',
      file_size_bytes: 128,
      id: 1,
      is_active: true,
      original_filename: 'queued.txt',
      scan_status: ScanStatus.queued,
      upload_group: 'group-1',
    });
    fixture.detectChanges();

    const root = fixture.nativeElement as HTMLElement;

    expect(root.textContent).toContain('Queued for scan');
    expect(root.textContent).toContain('Background scanning continues even if you close this page');
    expect(root.textContent).toContain('Link is already live');
    expect(component.getShareableLink()).toContain('/download/token-1');
  });
});
