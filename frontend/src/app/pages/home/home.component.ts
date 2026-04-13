import { HttpErrorResponse, HttpEventType } from "@angular/common/http";
import { CUSTOM_ELEMENTS_SCHEMA, Component, computed, inject, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router, RouterLink } from "@angular/router";
import { AltchaService } from "../../api/endpoints/altcha/altcha.service";
import {
  getLimitsApiAuthLimitsGetResource,
  getQuotaApiAuthQuotaGetResource,
} from "../../api/endpoints/filename.resource";
import type { UploadFileEntry } from "../../components/file-picker/file-picker.component";
import { FilePickerComponent } from "../../components/file-picker/file-picker.component";
import { JumpingTextComponent } from "../../components/jumping-text/jumping-text.component";
import type { PasswordEntry } from "../../components/upload-settings/upload-settings.component";
import { UploadSettingsComponent } from "../../components/upload-settings/upload-settings.component";
import { AuthService } from "../../services/auth.service";
import type { FileUploadResponse, MultiFileUploadResponse } from "../../services/file.service";
import { FileService } from "../../services/file.service";
import {
  extractDownloadToken,
  filenameToEmoji,
  formatFileSize,
  resolveAppUrl,
} from "../../utils/file.utils";

interface AltchaStateChangeDetail {
  payload?: string;
  state?: string;
}

type AltchaState = "unverified" | "verifying" | "verified" | "expired" | "error" | "code";

@Component({
  imports: [
    JumpingTextComponent,
    FormsModule,
    RouterLink,
    FilePickerComponent,
    UploadSettingsComponent,
  ],
  schemas: [CUSTOM_ELEMENTS_SCHEMA],
  selector: "app-home",
  styleUrl: "./home.component.scss",
  templateUrl: "./home.component.html",
})
export class HomeComponent {
  private readonly fileService = inject(FileService);
  private readonly authService = inject(AuthService);
  private readonly altchaService = inject(AltchaService);
  private readonly router = inject(Router);

  isUploading = signal(false);
  uploadProgress = signal(0);
  uploadSpeed = signal(0);
  estimatedTimeRemaining = signal(0);
  uploadResult = signal<MultiFileUploadResponse | null>(null);
  singleUploadResult = signal<FileUploadResponse | null>(null);
  error = signal<string | null>(null);
  copied = signal(false);
  altchaVerified = signal(false);
  altchaState = signal<AltchaState>("unverified");
  altchaChallenge = signal<string | null>(null);
  pendingFiles = signal<UploadFileEntry[]>([]);
  private altchaPayload = "";

  // Auth popup for unauthenticated users
  showAuthPopup = signal(false);
  popupEmail = signal("");
  popupCode = signal("");
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
  /** Transfer title. */
  title = signal("");
  /** Transfer description. */
  description = signal("");

  altchaHintText = computed(() => {
    switch (this.altchaState()) {
      case "verifying":
        return "Verifying…";
      case "expired":
        return "CAPTCHA expired — fetching a new challenge…";
      case "error":
        return "Verification failed. Please try again.";
      case "code":
        return "Please complete the code challenge.";
      default:
        return "Please complete the CAPTCHA to upload.";
    }
  });

  private uploadStartTime = 0;
  private lastProgressTime = 0;
  private lastProgressBytes = 0;

  private readonly limitsData = this.authService.isAuthenticated()
    ? getQuotaApiAuthQuotaGetResource()
    : getLimitsApiAuthLimitsGetResource();

  constructor() {
    this.loadAltchaChallenge();
  }

  maxFileSizeMb = computed<number>(() => {
    const l = this.limitsData.value();
    if (l) {
      return l.max_file_size_mb;
    }
    return 100;
  });

  isAuthenticated(): boolean {
    return this.authService.isAuthenticated();
  }

  maxFilesPerUpload = computed<number>(() => {
    const l = this.limitsData.value();
    if (l) {
      return l.max_files_per_upload;
    }
    return 10;
  });

  userTier = computed(() => {
    const l = this.limitsData.value();
    if (!l) {
      return "temporary";
    }
    // QuotaResponse has min_expiry_hours, LimitsResponse doesn't
    if ("min_expiry_hours" in l && l.min_expiry_hours !== undefined) {
      // Authenticated user, determine tier from limits
      if ((l as { max_expiry_hours?: number | null }).max_expiry_hours === 720) {
        return "premium";
      }
      return "free";
    }
    return "temporary";
  });

  maxPasswordsPerUpload = computed(() => {
    const l = this.limitsData.value();
    if (l && "max_passwords_per_upload" in l) {
      return (l as { max_passwords_per_upload?: number }).max_passwords_per_upload ?? 0;
    }
    return 1;
  });

  maxEmailsPerUpload = computed(() => {
    const l = this.limitsData.value();
    if (l && "max_emails_per_upload" in l) {
      return (l as { max_emails_per_upload?: number }).max_emails_per_upload ?? 0;
    }
    return 0;
  });

  onAltchaStateChange(event: Event): void {
    const detail = this.getAltchaStateDetail(event);
    const state = (detail?.state ?? "unverified") as AltchaState;
    this.altchaState.set(state);
    switch (state) {
      case "verified":
        if (detail?.payload) {
          this.altchaPayload = detail.payload;
          this.altchaVerified.set(true);
        }
        break;
      case "expired":
        this.altchaVerified.set(false);
        this.altchaPayload = "";
        this.altchaChallenge.set(null);
        this.loadAltchaChallenge();
        break;
      case "error":
        this.altchaVerified.set(false);
        this.altchaPayload = "";
        this.altchaChallenge.set(null);
        this.loadAltchaChallenge();
        break;
      case "unverified":
        this.altchaVerified.set(false);
        this.altchaPayload = "";
        break;
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
    this.uploadFiles(this.pendingFiles().map((entry) => entry.file));
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
    void this.router.navigate(["/auth"], { queryParams: email ? { email } : {} });
  }

  goToRegister(): void {
    const email = this.popupEmail().trim();
    void this.router.navigate(["/auth"], {
      queryParams: { mode: "register", ...(email ? { email } : {}) },
    });
  }

  requestPopupCode(): void {
    const email = this.popupEmail().trim();
    if (!email) {
      this.popupAuthError.set("Please enter your email address.");
      return;
    }
    this.popupCodeRequesting.set(true);
    this.popupAuthError.set(null);
    this.authService.requestCode(email).subscribe({
      error: (err) => {
        this.popupAuthError.set(this.getErrorDetail(err, "Failed to send verification code."));
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
      this.popupAuthError.set("Please enter the verification code.");
      return;
    }
    this.popupCodeVerifying.set(true);
    this.popupAuthError.set(null);
    this.authService.verifyCode(email, code).subscribe({
      error: (err) => {
        this.popupAuthError.set(this.getErrorDetail(err, "Verification failed. Please try again."));
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

  private uploadFiles(files: File[]): void {
    if (!this.altchaPayload) {
      this.error.set("Please complete the CAPTCHA verification first.");
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

    const totalSize = files.reduce((sum, file) => sum + file.size, 0);

    if (files.length === 1) {
      this.fileService
        .upload(files[0], this.altchaPayload, {
          expiryHours: this.expiryHours(),
          maxDownloads: this.maxDownloads(),
          isPublic: this.isPublic(),
          passwords: this.passwords().filter((p) => p.password),
          emails: this.emails().filter((e) => e.trim()),
          showEmailStats: this.showEmailStats(),
          title: this.title(),
          description: this.description(),
        })
        .subscribe({
          error: (err) => {
            this.error.set(this.getErrorDetail(err, "Upload failed. Please try again."));
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
              this.resetAltcha();
            }
          },
        });
      return;
    }

    this.fileService
      .uploadMultiple(files, this.altchaPayload, {
        expiryHours: this.expiryHours(),
        maxDownloads: this.maxDownloads(),
        isPublic: this.isPublic(),
        passwords: this.passwords().filter((p) => p.password),
        emails: this.emails().filter((e) => e.trim()),
        showEmailStats: this.showEmailStats(),
        title: this.title(),
        description: this.description(),
      })
      .subscribe({
        error: (err) => {
          this.error.set(this.getErrorDetail(err, "Upload failed. Please try again."));
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

    return "";
  }

  copyLink(): void {
    void (async () => {
      try {
        await navigator.clipboard.writeText(this.getShareableLink());
        this.copied.set(true);
        setTimeout(() => {
          this.copied.set(false);
        }, 2000);
      } catch {
        this.error.set("Failed to copy link to clipboard.");
      }
    })();
  }

  formatSize(bytes: number): string {
    return formatFileSize(bytes);
  }

  /** Get emoji for a result file (by filename). */
  getResultFileEmoji(filename: string): string {
    return filenameToEmoji(filename);
  }

  formatSpeed(bytesPerSec: number): string {
    return formatFileSize(bytesPerSec) + "/s";
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
      return multi.total_size_bytes;
    }
    const single = this.singleUploadResult();
    if (single) {
      return single.file_size_bytes;
    }
    return 0;
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
    this.altchaState.set("unverified");
    this.altchaPayload = "";
    this.altchaChallenge.set(null);
    this.loadAltchaChallenge();
  }

  private loadAltchaChallenge(): void {
    this.altchaService.getChallengeApiAltchaChallengeGet().subscribe({
      error: () => {
        this.altchaChallenge.set(null);
        this.error.set("Unable to load CAPTCHA challenge. Please try again later.");
      },
      next: (challenge) => {
        this.altchaChallenge.set(JSON.stringify(challenge));
      },
    });
  }

  private getAltchaStateDetail(event: Event): AltchaStateChangeDetail | null {
    if (
      !(event instanceof CustomEvent) ||
      typeof event.detail !== "object" ||
      event.detail === null
    ) {
      return null;
    }

    const state: unknown = Reflect.get(event.detail, "state");
    const payload: unknown = Reflect.get(event.detail, "payload");

    return {
      payload: typeof payload === "string" ? payload : undefined,
      state: typeof state === "string" ? state : undefined,
    };
  }

  private getErrorDetail(error: unknown, fallback: string): string {
    if (
      !(error instanceof HttpErrorResponse) ||
      typeof error.error !== "object" ||
      error.error === null
    ) {
      return fallback;
    }

    const detail: unknown = Reflect.get(error.error, "detail");
    if (typeof detail === "string") {
      return detail;
    }

    return fallback;
  }
}
