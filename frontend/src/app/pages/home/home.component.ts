import { Component, inject, signal } from '@angular/core';
import { AuthService } from '../../services/auth.service';
import { FileService, FileUploadResponse } from '../../services/file.service';

@Component({
  selector: 'app-home',
  imports: [],
  templateUrl: './home.component.html',
  styleUrl: './home.component.scss',
})
export class HomeComponent {
  private readonly fileService = inject(FileService);
  private readonly authService = inject(AuthService);

  isDragging = signal(false);
  isUploading = signal(false);
  uploadResult = signal<FileUploadResponse | null>(null);
  error = signal<string | null>(null);
  copied = signal(false);
  quota = signal<{
    files_used: number;
    files_limit: number;
    max_file_size_mb: number;
  } | null>(null);

  constructor() {
    if (this.authService.isAuthenticated()) {
      this.authService.getQuota().subscribe({
        next: (q) => this.quota.set(q),
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
      this.uploadFile(files[0]);
    }
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.uploadFile(input.files[0]);
    }
  }

  private uploadFile(file: File): void {
    this.isUploading.set(true);
    this.error.set(null);
    this.uploadResult.set(null);

    this.fileService.upload(file).subscribe({
      next: (result) => {
        this.uploadResult.set(result);
        this.isUploading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail ?? 'Upload failed. Please try again.');
        this.isUploading.set(false);
      },
    });
  }

  getShareableLink(): string {
    const result = this.uploadResult();
    if (!result) return '';
    return `${window.location.origin}/download/${this.extractToken(result.download_url)}`;
  }

  copyLink(): void {
    navigator.clipboard.writeText(this.getShareableLink());
    this.copied.set(true);
    setTimeout(() => this.copied.set(false), 2000);
  }

  formatSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  resetUpload(): void {
    this.uploadResult.set(null);
    this.error.set(null);
  }

  private extractToken(downloadUrl: string): string {
    const parts = downloadUrl.split('/');
    return parts[parts.length - 1] || parts[parts.length - 2];
  }
}
