/// <reference types="jasmine" />

import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import type { FileUploadResponse, QuotaResponse, UserResponse } from '../../api/model';
import { AuthService, ConfirmDialogService, FileService } from '../../services';
import { DashboardComponent } from './dashboard.component';

function createUser(tier: string): UserResponse {
  return {
    email: `${tier}@sendr.local`,
    has_password: false,
    id: tier === 'premium' ? 2 : 1,
    is_admin: false,
    is_banned: false,
    tier,
  };
}

function createFile(uploadGroup: string | null = 'group-1'): FileUploadResponse {
  return {
    download_count: 0,
    download_url: 'https://sendr.local/download/token-1',
    expires_at: '2030-01-02T00:00:00Z',
    file_size_bytes: 4,
    group_download_only: false,
    has_email_recipients: false,
    has_passwords: false,
    id: 1,
    is_active: true,
    is_public: true,
    max_downloads: null,
    original_filename: 'report.txt',
    upload_group: uploadGroup,
    viewer_is_owner: true,
  };
}

function createQuota(): QuotaResponse {
  return {
    can_use_email_stats: true,
    can_use_separate_download_counts: true,
    expiry_options_hours: [24, 72],
    max_downloads_limit: 10,
    max_downloads_options: [1, 10],
    max_emails_per_upload: 3,
    max_expiry_hours: 168,
    max_file_size_mb: 1024,
    max_files_per_upload: 50,
    max_passwords_per_upload: 3,
    min_expiry_hours: 1,
    weekly_upload_size_limit_bytes: 0,
    weekly_upload_size_remaining_bytes: 0,
    weekly_upload_size_used_bytes: 0,
    weekly_uploads_limit: 5,
    weekly_uploads_remaining: 5,
    weekly_uploads_used: 0,
  };
}

function flushExpandedGroupRequests(httpTesting: HttpTestingController): void {
  httpTesting.expectOne('/api/files/group/group-1/stats').flush({
    stats: [],
    total_downloads: 0,
  });
  httpTesting.expectOne('/api/files/group/group-1').flush({
    description: null,
    file_count: 1,
    files: [createFile()],
    title: null,
    total_size_bytes: 4,
    upload_group: 'group-1',
    viewer_is_owner: true,
    will_zip: false,
  });
  httpTesting.expectOne('/api/files/group/group-1/access-info').flush({
    emails: [],
    is_public: true,
    passwords: [],
    show_email_stats: false,
  });
}

function flushInitialRequests(httpTesting: HttpTestingController): void {
  httpTesting.expectOne('/api/files/').flush({ files: [createFile()] });
  httpTesting.expectOne('/api/auth/quota').flush(createQuota());
}

function getExpandedActionButtons(root: HTMLElement): string[] {
  return [...root.querySelectorAll<HTMLButtonElement>('.expanded-actions-row button')].map(
    (button) => button.textContent?.trim() ?? '',
  );
}

function getExpandedHeadings(root: HTMLElement): string[] {
  return [...root.querySelectorAll<HTMLElement>('.expanded-section h4')].map(
    (heading) => heading.textContent?.trim() ?? '',
  );
}

class AuthServiceStub {
  readonly authenticated = signal(true);
  readonly currentUser = signal<UserResponse | null>(createUser('free'));

  readonly changePassword = jasmine
    .createSpy('changePassword')
    .and.callFake((_currentPassword: string, _newPassword: string) =>
      of(this.currentUser() ?? createUser('free')),
    );

  readonly setPassword = jasmine
    .createSpy('setPassword')
    .and.callFake((_newPassword: string) => of(this.currentUser() ?? createUser('free')));

  syncSession(): void {}
}

describe('DashboardComponent', () => {
  let authService: AuthServiceStub;
  let confirmDialog: jasmine.SpyObj<ConfirmDialogService>;
  let fileService: jasmine.SpyObj<FileService>;
  let httpTesting: HttpTestingController;

  beforeEach(async () => {
    authService = new AuthServiceStub();
    confirmDialog = jasmine.createSpyObj<ConfirmDialogService>('ConfirmDialogService', ['confirm']);
    fileService = jasmine.createSpyObj<FileService>('FileService', [
      'addFilesToGroup',
      'deleteFile',
      'editAccess',
      'editFile',
      'editGroup',
      'refreshFile',
      'refreshGroup',
    ]);

    fileService.addFilesToGroup.and.returnValue(
      of({
        description: null,
        files: [],
        title: null,
        total_size_bytes: 0,
        upload_group: 'group-1',
      }),
    );
    fileService.deleteFile.and.returnValue(of({ message: 'deleted' }));
    fileService.editAccess.and.returnValue(
      of({ emails: [], is_public: true, passwords: [], show_email_stats: false }),
    );
    fileService.editFile.and.returnValue(of(createFile(null)));
    fileService.editGroup.and.returnValue(
      of({
        description: null,
        files: [createFile()],
        title: null,
        total_size_bytes: 4,
        upload_group: 'group-1',
      }),
    );
    fileService.refreshFile.and.returnValue(of(createFile(null)));
    fileService.refreshGroup.and.returnValue(
      of({
        description: null,
        files: [createFile()],
        title: null,
        total_size_bytes: 4,
        upload_group: 'group-1',
      }),
    );

    await TestBed.configureTestingModule({
      imports: [DashboardComponent],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: AuthService,
          useValue: authService,
        },
        {
          provide: ConfirmDialogService,
          useValue: confirmDialog,
        },
        {
          provide: FileService,
          useValue: fileService,
        },
      ],
    }).compileComponents();

    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it('hides in-place edit controls for free users', async () => {
    authService.currentUser.set(createUser('free'));
    const fixture = TestBed.createComponent(DashboardComponent);
    const component = fixture.componentInstance;

    fixture.detectChanges();
    flushInitialRequests(httpTesting);
    await fixture.whenStable();

    component.toggleExpanded(component.uploadGroups()[0].key);
    fixture.detectChanges();
    flushExpandedGroupRequests(httpTesting);
    await fixture.whenStable();
    fixture.detectChanges();

    const headings = getExpandedHeadings(fixture.nativeElement as HTMLElement);
    const actions = getExpandedActionButtons(fixture.nativeElement as HTMLElement);

    expect(headings).not.toContain('Add Files');
    expect(actions).not.toContain('Save');
    expect(actions).toContain('Refresh');
  });

  it('shows in-place edit controls for premium users', async () => {
    authService.currentUser.set(createUser('premium'));
    const fixture = TestBed.createComponent(DashboardComponent);
    const component = fixture.componentInstance;

    fixture.detectChanges();
    flushInitialRequests(httpTesting);
    await fixture.whenStable();

    component.toggleExpanded(component.uploadGroups()[0].key);
    fixture.detectChanges();
    flushExpandedGroupRequests(httpTesting);
    await fixture.whenStable();
    fixture.detectChanges();

    const headings = getExpandedHeadings(fixture.nativeElement as HTMLElement);
    const actions = getExpandedActionButtons(fixture.nativeElement as HTMLElement);

    expect(headings).toContain('Add Files');
    expect(actions).toContain('Save');
    expect(actions).toContain('Refresh');
  });

  it('refuses staged file additions during refresh for free users', async () => {
    authService.currentUser.set(createUser('free'));
    const fixture = TestBed.createComponent(DashboardComponent);
    const component = fixture.componentInstance;

    fixture.detectChanges();
    flushInitialRequests(httpTesting);
    await fixture.whenStable();

    component.newFiles.set([
      {
        file: new File(['extra'], 'extra.txt', { type: 'text/plain' }),
        mimeType: 'text/plain',
        name: 'extra.txt',
        size: 5,
      },
    ]);

    component.executeRefresh(component.uploadGroups()[0]);

    expect(component.error()).toBe('Upgrade to Premium to add files to an existing upload.');
    expect(component.isSaving()).toBeFalse();
    expect(fileService.addFilesToGroup.calls.any()).toBeFalse();
    expect(fileService.refreshGroup.calls.any()).toBeFalse();
  });
});
