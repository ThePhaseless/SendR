import { Component, CUSTOM_ELEMENTS_SCHEMA, inject, signal } from "@angular/core";
import { HttpEventType } from "@angular/common/http";
import { AuthService } from "../../services/auth.service";
import { FileService, FileUploadResponse } from "../../services/file.service";
import { extractDownloadToken, formatFileSize } from "../../utils/file.utils";

@Component({
  selector: "app-home",
  imports: [],
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
  uploadResult = signal<FileUploadResponse | null>(null);
  error = signal<string | null>(null);
  copied = signal(false);
  altchaVerified = signal(false);
  private altchaPayload = "";
  private pendingFile: File | null = null;
  quota = signal<{
    files_used: number;
    files_limit: number;
    max_file_size_mb: number;
  } | null>(null);
  maxFileSizeMb = signal(100);

  constructor() {
    if (this.authService.isAuthenticated()) {
      this.authService.getQuota().subscribe({
        next: (q) => {
          this.quota.set(q);
          this.maxFileSizeMb.set(q.max_file_size_mb);
        },
      });
    } else {
      this.authService.getLimits().subscribe({
        next: (l) => this.maxFileSizeMb.set(l.max_file_size_mb),
        error: () => {
          // Keep the default 100 MB limit if the request fails
        },
      });
    }
  }

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
      this.stageFile(files[0]);
    }
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.stageFile(input.files[0]);
    }
  }

  onAltchaStateChange(event: Event): void {
    const detail = (event as CustomEvent).detail;
    if (detail && detail.state === "verified" && detail.payload) {
      this.altchaPayload = detail.payload;
      this.altchaVerified.set(true);
      if (this.pendingFile) {
        this.uploadFile(this.pendingFile);
      }
    } else if (detail && detail.state === "error") {
      this.error.set("CAPTCHA verification failed. Please try again.");
      this.altchaVerified.set(false);
      this.altchaPayload = "";
    }
  }

  private stageFile(file: File): void {
    const maxBytes = this.maxFileSizeMb() * 1024 * 1024;
    if (file.size > maxBytes) {
      this.error.set(`File is too large. Maximum allowed size is ${this.maxFileSizeMb()} MB.`);
      return;
    }

    this.pendingFile = file;
    this.error.set(null);
    this.uploadResult.set(null);

    if (this.altchaVerified()) {
      this.uploadFile(file);
    }
  }

  private uploadFile(file: File): void {
    if (!this.altchaPayload) {
      this.error.set("Please complete the CAPTCHA verification first.");
      return;
    }

    this.isUploading.set(true);
    this.uploadProgress.set(0);
    this.error.set(null);
    this.uploadResult.set(null);

    this.fileService.upload(file, this.altchaPayload).subscribe({
      next: (event) => {
        if (event.type === HttpEventType.UploadProgress && event.total) {
          this.uploadProgress.set(Math.round((100 * event.loaded) / event.total));
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

  getShareableLink(): string {
    const result = this.uploadResult();
    if (!result) return "";
    return `${window.location.origin}/download/${extractDownloadToken(result.download_url)}`;
  }

  copyLink(): void {
    navigator.clipboard.writeText(this.getShareableLink());
    this.copied.set(true);
    setTimeout(() => this.copied.set(false), 2000);
  }

  formatSize(bytes: number): string {
    return formatFileSize(bytes);
  }

  resetUpload(): void {
    this.uploadResult.set(null);
    this.error.set(null);
    this.pendingFile = null;
    this.resetAltcha();
  }

  hasPendingFile(): boolean {
    return this.pendingFile !== null;
  }

  getPendingFileName(): string {
    return this.pendingFile?.name ?? "";
  }

  private resetAltcha(): void {
    this.altchaVerified.set(false);
    this.altchaPayload = "";
  }
}
