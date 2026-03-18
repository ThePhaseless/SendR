import { Component, computed, CUSTOM_ELEMENTS_SCHEMA, inject, signal } from "@angular/core";
import { toSignal } from "@angular/core/rxjs-interop";
import { HttpEventType } from "@angular/common/http";
import { JumpingTextComponent } from "../../components/jumping-text/jumping-text.component";
import { AuthService } from "../../services/auth.service";
import { FileService, FileUploadResponse, MultiFileUploadResponse } from "../../services/file.service";
import { extractDownloadToken, formatFileSize } from "../../utils/file.utils";

interface UploadFileEntry {
  file: File;
  name: string;
  size: number;
}

@Component({
  selector: "app-home",
  imports: [JumpingTextComponent],
  schemas: [CUSTOM_ELEMENTS_SCHEMA],
  templateUrl: "./home.component.html",
  styleUrl: "./home.component.scss",
})
export class HomeComponent {
  private readonly fileService = inject(FileService);
  private readonly authService = inject(AuthService);

  isDragging = signal(false);
  isUploading = signal(false);
  uploadProgress = signal(0);
  uploadSpeed = signal(0); // bytes per second
  estimatedTimeRemaining = signal(0); // seconds
  uploadResult = signal<MultiFileUploadResponse | null>(null);
  singleUploadResult = signal<FileUploadResponse | null>(null);
  error = signal<string | null>(null);
  copied = signal(false);
  altchaVerified = signal(false);
  private altchaPayload = "";
  pendingFiles = signal<UploadFileEntry[]>([]);

  private uploadStartTime = 0;
  private lastProgressTime = 0;
  private lastProgressBytes = 0;

  private readonly quotaData = this.authService.isAuthenticated()
    ? toSignal(this.authService.getQuota())
    : signal(undefined);

  private readonly limitsData = this.authService.isAuthenticated()
    ? signal(undefined)
    : toSignal(this.authService.getLimits(), { initialValue: undefined });

  quota = computed(() => this.quotaData() ?? null);

  maxFileSizeMb = computed(() => {
    const q = this.quotaData();
    if (q) return q.max_file_size_mb;
    const l = this.limitsData();
    if (l) return l.max_file_size_mb;
    return 100;
  });

  maxFilesPerUpload = computed(() => {
    const l = this.limitsData();
    if (l) return l.max_files_per_upload;
    return 10;
  });

  totalPendingSize = computed(() => {
    return this.pendingFiles().reduce((sum, f) => sum + f.size, 0);
  });

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
      this.stageFiles(Array.from(files));
    }
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.stageFiles(Array.from(input.files));
    }
  }

  onAltchaStateChange(event: Event): void {
    const detail = (event as CustomEvent).detail;
    if (detail && detail.state === "verified" && detail.payload) {
      this.altchaPayload = detail.payload;
      this.altchaVerified.set(true);
      const files = this.pendingFiles();
      if (files.length > 0) {
        this.uploadFiles(files.map((f) => f.file));
      }
    } else if (detail && detail.state === "error") {
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

    const existing = this.pendingFiles();
    const combined = [...existing];

    for (const file of newFiles) {
      combined.push({ file, name: file.name, size: file.size });
    }

    if (maxPerUpload > 0 && combined.length > maxPerUpload) {
      this.error.set(`Too many files. Maximum ${maxPerUpload} files per upload.`);
      return;
    }

    const totalSize = combined.reduce((sum, f) => sum + f.size, 0);
    if (totalSize > maxBytes) {
      this.error.set(`Total file size exceeds the limit of ${this.maxFileSizeMb()} MB.`);
      return;
    }

    this.pendingFiles.set(combined);
    this.error.set(null);
    this.uploadResult.set(null);
    this.singleUploadResult.set(null);

    if (this.altchaVerified()) {
      this.uploadFiles(combined.map((f) => f.file));
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

    const totalSize = files.reduce((sum, f) => sum + f.size, 0);

    if (files.length === 1) {
      this.fileService.upload(files[0], this.altchaPayload).subscribe({
        next: (event) => {
          if (event.type === HttpEventType.UploadProgress && event.total !== undefined) {
            const progress = event.total === 0 ? 100 : Math.round((100 * event.loaded) / event.total);
            this.uploadProgress.set(progress);
            this.updateSpeedAndEta(event.loaded, totalSize);
          } else if (event.type === HttpEventType.Response && event.body) {
            this.singleUploadResult.set(event.body);
            this.isUploading.set(false);
            this.uploadProgress.set(0);
            this.resetAltcha();
          }
        },
        error: (err) => {
          this.error.set(err.error?.detail ?? "Upload failed. Please try again.");
          this.isUploading.set(false);
          this.uploadProgress.set(0);
          this.resetAltcha();
        },
      });
    } else {
      this.fileService.uploadMultiple(files, this.altchaPayload).subscribe({
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
        error: (err) => {
          this.error.set(err.error?.detail ?? "Upload failed. Please try again.");
          this.isUploading.set(false);
          this.uploadProgress.set(0);
          this.resetAltcha();
        },
      });
    }
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
      return `${window.location.origin}/download/${extractDownloadToken(singleResult.download_url)}`;
    }
    const multiResult = this.uploadResult();
    if (multiResult) {
      return `${window.location.origin}/download/group/${multiResult.upload_group}`;
    }
    return "";
  }

  copyLink(): void {
    navigator.clipboard.writeText(this.getShareableLink()).then(
      () => {
        this.copied.set(true);
        setTimeout(() => this.copied.set(false), 2000);
      },
      () => {
        this.error.set("Failed to copy link to clipboard.");
      },
    );
  }

  formatSize(bytes: number): string {
    return formatFileSize(bytes);
  }

  formatSpeed(bytesPerSec: number): string {
    return formatFileSize(bytesPerSec) + "/s";
  }

  formatTime(seconds: number): string {
    if (seconds < 60) return `${seconds}s`;
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}m ${s}s`;
  }

  hasResult(): boolean {
    return this.uploadResult() !== null || this.singleUploadResult() !== null;
  }

  getResultFiles(): FileUploadResponse[] {
    const multi = this.uploadResult();
    if (multi) return multi.files;
    const single = this.singleUploadResult();
    if (single) return [single];
    return [];
  }

  getTotalResultSize(): number {
    const multi = this.uploadResult();
    if (multi) return multi.total_size_bytes;
    const single = this.singleUploadResult();
    if (single) return single.file_size_bytes;
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
}
