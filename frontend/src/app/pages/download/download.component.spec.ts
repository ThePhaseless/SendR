/// <reference types="jasmine" />

import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap } from '@angular/router';
import type { FileUploadResponse } from '../../api/model';
import { FileService } from '../../services';
import { DownloadComponent } from './download.component';

function createRoute(token: string): ActivatedRoute {
  return {
    snapshot: {
      fragment: null,
      paramMap: convertToParamMap({ token }),
      queryParamMap: convertToParamMap({}),
    },
  } as ActivatedRoute;
}

function createFileInfo(scanStatus: FileUploadResponse['scan_status']): FileUploadResponse {
  return {
    download_count: 0,
    download_url: 'https://sendr.local/api/files/token-1',
    expires_at: '2030-01-02T00:00:00Z',
    file_size_bytes: 128,
    group_download_only: false,
    has_email_recipients: false,
    has_passwords: false,
    id: 1,
    is_active: true,
    is_public: true,
    max_downloads: null,
    original_filename: 'report.txt',
    scan_status: scanStatus,
    upload_group: 'group-1',
    viewer_is_owner: false,
  };
}

describe('DownloadComponent', () => {
  let httpTesting: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DownloadComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: ActivatedRoute,
          useValue: createRoute('token-1'),
        },
        {
          provide: FileService,
          useValue: jasmine.createSpyObj<FileService>('FileService', [
            'getDownloadUrlWithPassword',
            'getGroupDownloadUrlWithPassword',
          ]),
        },
      ],
    }).compileComponents();

    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it('polls while a file is queued for scanning and enables download once clean', async () => {
    let pollCallback: (() => void) | null = null;
    spyOn(window, 'clearInterval');
    spyOn(window, 'setInterval').and.callFake((handler: TimerHandler) => {
      pollCallback = typeof handler === 'function' ? (handler as () => void) : null;
      return 1;
    });

    const fixture = TestBed.createComponent(DownloadComponent);

    fixture.detectChanges();
    httpTesting.expectOne('/api/files/token-1/info').flush(createFileInfo('queued'));
    await fixture.whenStable();
    fixture.detectChanges();

    let root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('Queued for scan');
    expect(root.textContent).toContain('refreshes automatically');
    expect(root.textContent).not.toContain('Download File');

    const runPoll = pollCallback;
    expect(runPoll).not.toBeNull();
    (runPoll as unknown as () => void)();
    fixture.detectChanges();
    httpTesting.expectOne('/api/files/token-1/info').flush(createFileInfo('clean'));
    await fixture.whenStable();
    fixture.detectChanges();

    root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).not.toContain('Queued for scan');
    expect(root.textContent).toContain('Download File');
  });

  it('shows a malware blocked message for infected files', async () => {
    const fixture = TestBed.createComponent(DownloadComponent);

    fixture.detectChanges();
    httpTesting.expectOne('/api/files/token-1/info').flush(createFileInfo('infected'));
    await fixture.whenStable();
    fixture.detectChanges();

    const root = fixture.nativeElement as HTMLElement;

    expect(root.textContent).toContain('Malware detected');
    expect(root.textContent).toContain('blocked because malware was detected');
    expect(root.textContent).not.toContain('Download File');
  });
});
