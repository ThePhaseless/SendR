import { HttpEventType, httpResource } from '@angular/common/http';
import {
  CUSTOM_ELEMENTS_SCHEMA,
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import type {
  GetChallengeApiAltchaChallengeGet200,
  LimitsResponse,
  QuotaResponse,
} from '../../api/model';
import {
  FilePickerComponent,
  type UploadFileEntry,
} from '../../components/file-picker/file-picker.component';
import { JumpingTextComponent } from '../../components/jumping-text/jumping-text.component';
import {
  type PasswordEntry,
  UploadSettingsComponent,
} from '../../components/upload-settings/upload-settings.component';
import {
  AuthService,
  FileService,
  type FileUploadResponse,
  type MultiFileUploadResponse,
} from '../../services';
import {
  extractDownloadToken,
  filenameToEmoji,
  formatFileSize,
  getErrorDetail,
  resolveAppUrl,
} from '../../utils/index';

interface AltchaStateChangeDetail {
  payload?: string;
  state?: string;
}

type AltchaState = 'unverified' | 'verifying' | 'verified' | 'expired' | 'error' | 'code';
type UploadLimits = LimitsResponse | QuotaResponse;

const PREMIUM_MAX_EXPIRY_HOURS = 720;

function getLimitNumber(limits: UploadLimits | null, key: string): number | null {
  if (!limits) {
    return null;
  }

  const value: unknown = Reflect.get(limits, key);
  return typeof value === 'number' ? value : null;
}

function getLimitBoolean(limits: UploadLimits | null, key: string): boolean {
  if (!limits) {
    return false;
  }

  const value: unknown = Reflect.get(limits, key);
  return typeof value === 'boolean' ? value : false;
}

function isAltchaState(value: string | undefined): value is AltchaState {
  return (
    value === 'code' ||
    value === 'error' ||
    value === 'expired' ||
    value === 'unverified' ||
    value === 'verified' ||
    value === 'verifying'
  );
}

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    JumpingTextComponent,
    FormsModule,
    RouterLink,
    FilePickerComponent,
    UploadSettingsComponent,
  ],
  schemas: [CUSTOM_ELEMENTS_SCHEMA],
  selector: 'app-home',
  standalone: true,
  styleUrl: './home.component.scss',
  templateUrl: './home.component.html',
})
export class HomeComponent {
  private readonly fileService = inject(FileService);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly limitsResource = httpResource<LimitsResponse>(() =>
    this.authService.authenticated() ? undefined : '/api/auth/limits',
  );
  private readonly quotaResource = httpResource<QuotaResponse>(() =>
    this.authService.authenticated() ? '/api/auth/quota' : undefined,
  );
  private readonly altchaChallengeResource = httpResource<GetChallengeApiAltchaChallengeGet200>(
    () => '/api/altcha/challenge',
  );

  isUploading = signal(false);
  uploadProgress = signal(0);
  uploadSpeed = signal(0);
  estimatedTimeRemaining = signal(0);
  uploadResult = signal<MultiFileUploadResponse | null>(null);
  singleUploadResult = signal<FileUploadResponse | null>(null);
  error = signal<string | null>(null);
  copied = signal(false);
  altchaVerified = signal(false);
  altchaState = signal<AltchaState>('unverified');
  altchaChallenge = signal<string | null>(null);
  pendingFiles = signal<UploadFileEntry[]>([]);
  private altchaPayload = '';

  // Auth popup for unauthenticated users
  showAuthPopup = signal(false);
  popupEmail = signal('');
  popupCode = signal('');
  popupCodeSent = signal(false);
  popupCodeRequesting = signal(false);
  popupCodeVerifying = signal(false);
  popupAuthError = signal<string | null>(null);

  // Upload settings
  /** Default 3 days (valid for all tiers) */
  expiryHours = signal(72);
  /** 0 = unlimited */
  maxDownloads = signal(0);
  /** Whether the upload is publicly accessible. */
  isPublic = signal(true);
  /** Password entries for the upload. */
  passwords = signal<PasswordEntry[]>([]);
  /** Email recipients for the upload. */
  emails = signal<string[]>([]);
  /** Whether email recipients can see download stats. */
  showEmailStats = signal(false);
  /** Whether download counts are tracked separately for public vs restricted. */
  separateDownloadCounts = signal(false);
  /** Transfer title. */
  title = signal('');
  /** Transfer description. */
  description = signal('');
  /** Whether upload settings have a validation error. */
  settingsHasError = signal(false);
  /** Whether file picker has a limit warning. */
  fileLimitWarning = computed(() => {
    const files = this.pendingFiles();
    if (files.length === 0) {
      return false;
    }
    const maxBytes = this.maxFileSizeMb() * 1024 * 1024;
    const maxPerUpload = this.maxFilesPerUpload();
    const totalSize = files.reduce((sum, f) => sum + f.size, 0);
    if (maxPerUpload > 0 && files.length > maxPerUpload) {
      return true;
    }
    if (totalSize > maxBytes) {
      return true;
    }
    return false;
  });

  altchaHintText = computed(() => {
    switch (this.altchaState()) {
      case 'code': {
        return 'Please complete the code challenge.';
      }
      case 'error': {
        return 'Verification failed. Please try again.';
      }
      case 'expired': {
        return 'CAPTCHA expired — fetching a new challenge…';
      }
      case 'unverified': {
        return 'Please complete the CAPTCHA to upload.';
      }
      case 'verified': {
        return 'CAPTCHA verified.';
      }
      case 'verifying': {
        return 'Verifying…';
      }
    }
  });

  private uploadStartTime = 0;
  private lastProgressTime = 0;
  private lastProgressBytes = 0;

  private readonly limitsData = computed<UploadLimits | null>(() => {
    if (this.authService.authenticated()) {
      return this.quotaResource.hasValue() ? this.quotaResource.value() : null;
    }

    return this.limitsResource.hasValue() ? this.limitsResource.value() : null;
  });

  constructor() {
    effect(() => {
      if (this.altchaChallengeResource.hasValue()) {
        this.altchaChallenge.set(JSON.stringify(this.altchaChallengeResource.value()));
      }
    });

    effect(() => {
      if (this.altchaChallengeResource.error()) {
        this.altchaChallenge.set(null);
        this.error.set('Unable to load CAPTCHA challenge. Please try again later.');
      }
    });
  }

  maxFileSizeMb = computed<number>(() => {
    const l = this.limitsData();
    if (l) {
      return l.max_file_size_mb;
    }
    return 100;
  });

  isAuthenticated(): boolean {
    return this.authService.authenticated();
  }

  maxFilesPerUpload = computed<number>(() => {
    const l = this.limitsData();
    if (l) {
      return l.max_files_per_upload;
    }
    return 10;
  });

  userTier = computed(() => {
    const l = this.limitsData();
    if (!l) {
      return 'temporary';
    }
    // QuotaResponse has min_expiry_hours for free/premium (non-null number),
    // Null/undefined for temporary tier. LimitsResponse doesn't have it at all.
    if (
      'min_expiry_hours' in l &&
      l.min_expiry_hours !== null &&
      l.min_expiry_hours !== undefined
    ) {
      if (getLimitNumber(l, 'max_expiry_hours') === PREMIUM_MAX_EXPIRY_HOURS) {
        return 'premium';
      }
      return 'free';
    }
    return 'temporary';
  });

  maxPasswordsPerUpload = computed(() => {
    const l = this.limitsData();
    return getLimitNumber(l, 'max_passwords_per_upload') ?? 1;
  });

  maxEmailsPerUpload = computed(() => {
    const l = this.limitsData();
    return getLimitNumber(l, 'max_emails_per_upload') ?? 0;
  });

  // Backend-driven expiry/download options
  expiryOptionsHours = computed<number[] | null>(() => {
    const l = this.limitsData();
    return l?.expiry_options_hours ?? null;
  });

  minExpiryHours = computed<number | null>(() =>
    getLimitNumber(this.limitsData(), 'min_expiry_hours'),
  );

  maxExpiryHours = computed<number | null>(() =>
    getLimitNumber(this.limitsData(), 'max_expiry_hours'),
  );

  backendMaxDownloadsLimit = computed<number | null>(() =>
    getLimitNumber(this.limitsData(), 'max_downloads_limit'),
  );

  backendMaxDownloadsOptions = computed<number[] | null>(() => {
    const l = this.limitsData();
    return l?.max_downloads_options ?? null;
  });

  canUseSeparateDownloadCounts = computed(() =>
    getLimitBoolean(this.limitsData(), 'can_use_separate_download_counts'),
  );

  canUseEmailStats = computed(() => getLimitBoolean(this.limitsData(), 'can_use_email_stats'));

  // Weekly upload quota
  weeklyUploadsUsed = computed(() => getLimitNumber(this.limitsData(), 'weekly_uploads_used') ?? 0);

  weeklyUploadsLimit = computed(() => {
    const l = this.limitsData();
    return l?.weekly_uploads_limit ?? 0;
  });

  weeklyUploadsRemaining = computed(() => {
    const l = this.limitsData();
    if (!l) {
      return 0;
    }

    if ('weekly_uploads_remaining' in l && l.weekly_uploads_remaining !== undefined) {
      return l.weekly_uploads_remaining ?? 0;
    }

    const weeklyLimit = l.weekly_uploads_limit ?? 0;
    const weeklyUsed = 'weekly_uploads_used' in l ? (l.weekly_uploads_used ?? 0) : 0;
    return weeklyLimit > 0 ? Math.max(0, weeklyLimit - weeklyUsed) : 0;
  });

  // Weekly upload size quota (bytes)
  weeklyUploadSizeLimitBytes = computed(
    () => getLimitNumber(this.limitsData(), 'weekly_upload_size_limit_bytes') ?? 0,
  );

  weeklyUploadSizeUsedBytes = computed(
    () => getLimitNumber(this.limitsData(), 'weekly_upload_size_used_bytes') ?? 0,
  );

  weeklyUploadSizeRemainingBytes = computed(() => {
    const l = this.limitsData();
    if (!l) {
      return 0;
    }

    if (
      'weekly_upload_size_remaining_bytes' in l &&
      l.weekly_upload_size_remaining_bytes !== undefined
    ) {
      return l.weekly_upload_size_remaining_bytes ?? 0;
    }

    const sizeLimit =
      'weekly_upload_size_limit_bytes' in l ? (l.weekly_upload_size_limit_bytes ?? 0) : 0;
    const sizeUsed =
      'weekly_upload_size_used_bytes' in l ? (l.weekly_upload_size_used_bytes ?? 0) : 0;
    return sizeLimit > 0 ? Math.max(0, sizeLimit - sizeUsed) : 0;
  });

  isSizeQuotaExhausted = computed(() => {
    const limit = this.weeklyUploadSizeLimitBytes();
    if (limit <= 0) {
      return false;
    }
    return this.weeklyUploadSizeRemainingBytes() <= 0;
  });

  isQuotaExhausted = computed(() => {
    const countLimit = this.weeklyUploadsLimit();
    const countExhausted = countLimit > 0 && this.weeklyUploadsRemaining() <= 0;
    return countExhausted || this.isSizeQuotaExhausted();
  });

  onAltchaStateChange(event: Event): void {
    if (this.isUploading()) {
      return;
    }

    const detail = this.getAltchaStateDetail(event);
    const state = isAltchaState(detail?.state) ? detail.state : 'unverified';
    this.altchaState.set(state);
    switch (state) {
      case 'verified': {
        if (detail?.payload) {
          this.altchaPayload = detail.payload;
          this.altchaVerified.set(true);
        }
        break;
      }
      case 'expired': {
        this.altchaVerified.set(false);
        this.altchaPayload = '';
        this.altchaChallenge.set(null);
        this.loadAltchaChallenge();
        break;
      }
      case 'error': {
        this.altchaVerified.set(false);
        this.altchaPayload = '';
        this.altchaChallenge.set(null);
        this.loadAltchaChallenge();
        break;
      }
      case 'unverified': {
        this.altchaVerified.set(false);
        this.altchaPayload = '';
        break;
      }
      case 'verifying':
      case 'code': {
        break;
      }
    }
  }

  onFilesChanged(): void {
    this.error.set(null);
    this.uploadResult.set(null);
    this.singleUploadResult.set(null);
  }

  startUpload(): void {
    if (this.pendingFiles().length === 0) {
      return;
    }
    if (!this.isAuthenticated()) {
      this.showAuthPopup.set(true);
      return;
    }
    this.uploadFiles(this.pendingFiles());
  }

  openAuthPopup(): void {
    this.showAuthPopup.set(true);
  }

  closeAuthPopup(): void {
    this.showAuthPopup.set(false);
    this.popupAuthError.set(null);
  }

  goToLogin(): void {
    const email = this.popupEmail().trim();
    void this.router.navigate(['/auth'], { queryParams: email ? { email } : {} });
  }

  goToRegister(): void {
    const email = this.popupEmail().trim();
    void this.router.navigate(['/auth'], {
      queryParams: { mode: 'register', ...(email ? { email } : {}) },
    });
  }

  requestPopupCode(): void {
    const email = this.popupEmail().trim();
    if (!email) {
      this.popupAuthError.set('Please enter your email address.');
      return;
    }
    this.popupCodeRequesting.set(true);
    this.popupAuthError.set(null);
    this.authService.requestCode(email).subscribe({
      error: (err) => {
        this.popupAuthError.set(this.getErrorDetail(err, 'Failed to send verification code.'));
        this.popupCodeRequesting.set(false);
      },
      next: () => {
        this.popupCodeSent.set(true);
        this.popupCodeRequesting.set(false);
      },
    });
  }

  verifyPopupCode(): void {
    const email = this.popupEmail().trim();
    const code = this.popupCode().trim();
    if (!code) {
      this.popupAuthError.set('Please enter the verification code.');
      return;
    }
    this.popupCodeVerifying.set(true);
    this.popupAuthError.set(null);
    this.authService.verifyCode(email, code).subscribe({
      error: (err) => {
        this.popupAuthError.set(this.getErrorDetail(err, 'Verification failed. Please try again.'));
        this.popupCodeVerifying.set(false);
      },
      next: () => {
        this.popupCodeVerifying.set(false);
        this.showAuthPopup.set(false);
      },
    });
  }

  navigateToDownload(): void {
    const link = this.getShareableLink();
    if (!link) {
      return;
    }
    const url = new URL(link);
    void this.router.navigateByUrl(url.pathname);
  }

  private uploadFiles(entries: UploadFileEntry[]): void {
    if (!this.altchaPayload) {
      this.error.set('Please complete the CAPTCHA verification first.');
      return;
    }

    this.isUploading.set(true);
    this.uploadProgress.set(0);
    this.uploadSpeed.set(0);
    this.estimatedTimeRemaining.set(0);
    this.error.set(null);
    this.uploadResult.set(null);
    this.singleUploadResult.set(null);

    this.uploadStartTime = Date.now();
    this.lastProgressTime = this.uploadStartTime;
    this.lastProgressBytes = 0;

    const totalSize = entries.reduce((sum, entry) => sum + entry.size, 0);

    if (entries.length === 1) {
      this.fileService
        .upload(entries[0].file, this.altchaPayload, {
          description: this.description(),
          emails: this.emails().filter((e) => e.trim()),
          expiryHours: this.expiryHours(),
          isPublic: this.isPublic(),
          maxDownloads: this.maxDownloads(),
          passwords: this.getSubmittedPasswords(),
          separateDownloadCounts: this.separateDownloadCounts(),
          showEmailStats: this.showEmailStats(),
          title: this.title(),
        })
        .subscribe({
          error: (err) => {
            this.error.set(this.getErrorDetail(err, 'Upload failed. Please try again.'));
            this.isUploading.set(false);
            this.uploadProgress.set(0);
            this.resetAltcha();
          },
          next: (event) => {
            if (event.type === HttpEventType.UploadProgress && event.total !== undefined) {
              const progress =
                event.total === 0 ? 100 : Math.round((100 * event.loaded) / event.total);
              this.uploadProgress.set(progress);
              this.updateSpeedAndEta(event.loaded, totalSize);
            } else if (event.type === HttpEventType.Response && event.body) {
              this.singleUploadResult.set(event.body);
              this.isUploading.set(false);
              this.uploadProgress.set(0);
              this.reloadLimits();
              this.resetAltcha();
            }
          },
        });
      return;
    }

    this.fileService
      .uploadMultiple(entries, this.altchaPayload, {
        description: this.description(),
        emails: this.emails().filter((e) => e.trim()),
        expiryHours: this.expiryHours(),
        isPublic: this.isPublic(),
        maxDownloads: this.maxDownloads(),
        passwords: this.getSubmittedPasswords(),
        separateDownloadCounts: this.separateDownloadCounts(),
        showEmailStats: this.showEmailStats(),
        title: this.title(),
      })
      .subscribe({
        error: (err) => {
          this.error.set(this.getErrorDetail(err, 'Upload failed. Please try again.'));
          this.isUploading.set(false);
          this.uploadProgress.set(0);
          this.resetAltcha();
        },
        next: (event) => {
          if (event.type === HttpEventType.UploadProgress && event.total !== undefined) {
            const progress =
              event.total === 0 ? 100 : Math.round((100 * event.loaded) / event.total);
            this.uploadProgress.set(progress);
            this.updateSpeedAndEta(event.loaded, totalSize);
          } else if (event.type === HttpEventType.Response && event.body) {
            this.uploadResult.set(event.body);
            this.isUploading.set(false);
            this.uploadProgress.set(0);
            this.reloadLimits();
            this.resetAltcha();
          }
        },
      });
  }

  private updateSpeedAndEta(loaded: number, total: number): void {
    const now = Date.now();
    const timeDiff = (now - this.lastProgressTime) / 1000;
    if (timeDiff > 0.5) {
      const bytesDiff = loaded - this.lastProgressBytes;
      const speed = bytesDiff / timeDiff;
      this.uploadSpeed.set(Math.round(speed));
      const remaining = total - loaded;
      this.estimatedTimeRemaining.set(speed > 0 ? Math.round(remaining / speed) : 0);
      this.lastProgressTime = now;
      this.lastProgressBytes = loaded;
    }
  }

  getShareableLink(): string {
    const singleResult = this.singleUploadResult();
    if (singleResult) {
      return resolveAppUrl(`download/${extractDownloadToken(singleResult.download_url)}`);
    }

    const multiResult = this.uploadResult();
    if (multiResult) {
      return resolveAppUrl(`download/group/${multiResult.upload_group}`);
    }

    return '';
  }

  copyLink(): void {
    void navigator.clipboard
      .writeText(this.getShareableLink())
      .then(() => {
        this.copied.set(true);
        return setTimeout(() => {
          this.copied.set(false);
        }, 2000);
      })
      .catch(() => {
        this.error.set('Failed to copy link to clipboard.');
      });
  }

  formatSize(bytes: number): string {
    return formatFileSize(bytes);
  }

  /** Get emoji for a result file (by filename). */
  getResultFileEmoji(filename: string): string {
    return filenameToEmoji(filename);
  }

  formatSpeed(bytesPerSec: number): string {
    return formatFileSize(bytesPerSec) + '/s';
  }

  formatTime(seconds: number): string {
    if (seconds < 60) {
      return `${seconds}s`;
    }
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  }

  hasResult(): boolean {
    return this.uploadResult() !== null || this.singleUploadResult() !== null;
  }

  getResultFiles(): FileUploadResponse[] {
    const multi = this.uploadResult();
    if (multi) {
      return multi.files;
    }
    const single = this.singleUploadResult();
    if (single) {
      return [single];
    }
    return [];
  }

  getTotalResultSize(): number {
    const multi = this.uploadResult();
    if (multi) {
      return (
        multi.total_size_bytes ?? multi.files.reduce((sum, f) => sum + (f.file_size_bytes ?? 0), 0)
      );
    }
    const single = this.singleUploadResult();
    if (single) {
      return single.file_size_bytes ?? 0;
    }
    return 0;
  }

  /** Password visibility toggles in post-upload view. */
  postUploadPasswordVisibility: boolean[] = [];

  togglePostPasswordVisibility(index: number): void {
    this.postUploadPasswordVisibility[index] = !this.postUploadPasswordVisibility[index];
  }

  /** Get passwords that were submitted (non-empty). */
  getSubmittedPasswords(): PasswordEntry[] {
    return this.passwords()
      .filter((p) => p.password.trim())
      .map((p) => ({ label: p.label.trim(), password: p.password.trim() }));
  }

  /** Get emails that were submitted (non-empty). */
  getSubmittedEmails(): string[] {
    return this.emails().filter((e) => e.trim());
  }

  /** Get the title of the uploaded group/file. */
  getResultTitle(): string {
    const multi = this.uploadResult();
    if (multi?.title) {
      return multi.title;
    }
    return this.title();
  }

  resetUpload(): void {
    this.uploadResult.set(null);
    this.singleUploadResult.set(null);
    this.error.set(null);
    this.pendingFiles.set([]);
    this.resetAltcha();
  }

  private resetAltcha(): void {
    this.altchaVerified.set(false);
    this.altchaState.set('unverified');
    this.altchaPayload = '';
    this.altchaChallenge.set(null);
    this.loadAltchaChallenge();
  }

  private loadAltchaChallenge(): void {
    this.altchaChallenge.set(null);
    this.altchaChallengeResource.reload();
  }

  private reloadLimits(): void {
    if (this.authService.authenticated()) {
      this.quotaResource.reload();
      return;
    }

    this.limitsResource.reload();
  }

  private getAltchaStateDetail(event: Event): AltchaStateChangeDetail | null {
    if (
      !(event instanceof CustomEvent) ||
      typeof event.detail !== 'object' ||
      event.detail === null
    ) {
      return null;
    }

    const state: unknown = Reflect.get(event.detail, 'state');
    const payload: unknown = Reflect.get(event.detail, 'payload');

    return {
      payload: typeof payload === 'string' ? payload : undefined,
      state: typeof state === 'string' ? state : undefined,
    };
  }

  private getErrorDetail(error: unknown, fallback: string): string {
    return getErrorDetail(error, fallback);
  }
}
