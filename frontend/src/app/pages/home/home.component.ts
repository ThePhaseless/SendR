import { HttpErrorResponse, HttpEventType } from "@angular/common/http";
import { CUSTOM_ELEMENTS_SCHEMA, Component, computed, inject, signal } from "@angular/core";
import { AuthService } from "../../services/auth.service";
import type { LimitsResponse, QuotaResponse } from "../../services/auth.service";
import { FileService } from "../../services/file.service";
import type { FileUploadResponse, MultiFileUploadResponse } from "../../services/file.service";
import { JumpingTextComponent } from "../../components/jumping-text/jumping-text.component";
import { extractDownloadToken, formatFileSize } from "../../utils/file.utils";
import { resolveAppUrl } from "../../utils/url.utils";
import { toSignal } from "@angular/core/rxjs-interop";

interface UploadFileEntry {
  file: File;
  name: string;
  size: number;
}

interface AltchaStateChangeDetail {
  payload?: string;
  state?: string;
}

@Component({
  imports: [JumpingTextComponent],
  schemas: [CUSTOM_ELEMENTS_SCHEMA],
  selector: "app-home",
  styleUrl: "./home.component.scss",
  templateUrl: "./home.component.html",
})
export class HomeComponent {
  private readonly fileService = inject(FileService);
  private readonly authService = inject(AuthService);

  isDragging = signal(false);
  isUploading = signal(false);
  uploadProgress = signal(0);
  uploadSpeed = signal(0);
  estimatedTimeRemaining = signal(0);
  uploadResult = signal<MultiFileUploadResponse | null>(null);
  singleUploadResult = signal<FileUploadResponse | null>(null);
  error = signal<string | null>(null);
  copied = signal(false);
  altchaVerified = signal(false);
  pendingFiles = signal<UploadFileEntry[]>([]);
  private altchaPayload = "";

  private uploadStartTime = 0;
  private lastProgressTime = 0;
  private lastProgressBytes = 0;

  private readonly quotaData = this.authService.isAuthenticated()
    ? toSignal(this.authService.getQuota(), { initialValue: null })
    : signal<QuotaResponse | null>(null);

  private readonly limitsData = this.authService.isAuthenticated()
    ? signal<LimitsResponse | null>(null)
    : toSignal(this.authService.getLimits(), { initialValue: null });

  quota = computed<QuotaResponse | null>(() => this.quotaData());

  maxFileSizeMb = computed<number>(() => {
    const q = this.quotaData();
    if (q) {
      return q.max_file_size_mb;
    }
    const l = this.limitsData();
    if (l) {
      return l.max_file_size_mb;
    }
    return 100;
  });

  maxFilesPerUpload = computed<number>(() => {
    const l = this.limitsData();
    if (l) {
      return l.max_files_per_upload;
    }
    return 10;
  });

  totalPendingSize = computed(() => this.pendingFiles().reduce((sum, file) => sum + file.size, 0));

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging.set(true);
  }

  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging.set(false);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging.set(false);
    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      this.stageFiles([...files]);
    }
  }

  onFileSelected(event: Event): void {
    const { target } = event;
    if (!(target instanceof HTMLInputElement) || !target.files || target.files.length === 0) {
      return;
    }

    this.stageFiles([...target.files]);
  }

  onAltchaStateChange(event: Event): void {
    const detail = this.getAltchaStateDetail(event);
    if (detail?.state === "verified" && detail.payload) {
      this.altchaPayload = detail.payload;
      this.altchaVerified.set(true);
      const files = this.pendingFiles();
      if (files.length > 0) {
        this.uploadFiles(files.map((file) => file.file));
      }
    } else if (detail?.state === "error") {
      this.error.set("CAPTCHA verification failed. Please try again.");
      this.altchaVerified.set(false);
      this.altchaPayload = "";
    }
  }

  removeFile(index: number): void {
    this.pendingFiles.update((files) => files.filter((_, i) => i !== index));
  }

  private stageFiles(newFiles: File[]): void {
    const maxBytes = this.maxFileSizeMb() * 1024 * 1024;
    const maxPerUpload = this.maxFilesPerUpload();
    const combined = [...this.pendingFiles()];

    for (const file of newFiles) {
      combined.push({ file, name: file.name, size: file.size });
    }

    if (maxPerUpload > 0 && combined.length > maxPerUpload) {
      this.error.set(`Too many files. Maximum ${maxPerUpload} files per upload.`);
      return;
    }

    const totalSize = combined.reduce((sum, file) => sum + file.size, 0);
    if (totalSize > maxBytes) {
      this.error.set(`Total file size exceeds the limit of ${this.maxFileSizeMb()} MB.`);
      return;
    }

    this.pendingFiles.set(combined);
    this.error.set(null);
    this.uploadResult.set(null);
    this.singleUploadResult.set(null);

    if (this.altchaVerified()) {
      this.uploadFiles(combined.map((file) => file.file));
    }
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
      this.fileService.upload(files[0], this.altchaPayload).subscribe({
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

    this.fileService.uploadMultiple(files, this.altchaPayload).subscribe({
      error: (err) => {
        this.error.set(this.getErrorDetail(err, "Upload failed. Please try again."));
        this.isUploading.set(false);
        this.uploadProgress.set(0);
        this.resetAltcha();
      },
      next: (event) => {
        if (event.type === HttpEventType.UploadProgress && event.total !== undefined) {
          const progress = event.total === 0 ? 100 : Math.round((100 * event.loaded) / event.total);
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
    this.altchaPayload = "";
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
