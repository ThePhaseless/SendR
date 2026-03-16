import { Component, inject, OnInit, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import {
  FileService,
  FileUploadResponse,
} from '../../services/file.service';

@Component({
  selector: 'app-dashboard',
  imports: [DatePipe],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent implements OnInit {
  private readonly fileService = inject(FileService);

  files = signal<FileUploadResponse[]>([]);
  quotaUsed = signal(0);
  quotaLimit = signal(0);
  loading = signal(true);
  error = signal<string | null>(null);
  copiedId = signal<number | null>(null);

  ngOnInit(): void {
    this.loadFiles();
  }

  private loadFiles(): void {
    this.loading.set(true);
    this.fileService.listFiles().subscribe({
      next: (res) => {
        this.files.set(res.files);
        this.quotaUsed.set(res.quota_used);
        this.quotaLimit.set(res.quota_limit);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Failed to load files.');
        this.loading.set(false);
      },
    });
  }

  copyLink(file: FileUploadResponse): void {
    const token = this.extractToken(file.download_url);
    const link = `${window.location.origin}/download/${token}`;
    navigator.clipboard.writeText(link);
    this.copiedId.set(file.id);
    setTimeout(() => this.copiedId.set(null), 2000);
  }

  refreshFile(file: FileUploadResponse): void {
    this.fileService.refreshFile(file.id).subscribe({
      next: (updated) => {
        this.files.update((files) =>
          files.map((f) => (f.id === updated.id ? updated : f)),
        );
      },
      error: () => {
        this.error.set('Failed to refresh file link.');
      },
    });
  }

  deleteFile(file: FileUploadResponse): void {
    this.fileService.deleteFile(file.id).subscribe({
      next: () => {
        this.files.update((files) => files.filter((f) => f.id !== file.id));
        this.quotaUsed.update((q) => q - 1);
      },
      error: () => {
        this.error.set('Failed to delete file.');
      },
    });
  }

  formatSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  isExpired(expiresAt: string): boolean {
    return new Date(expiresAt) < new Date();
  }

  private extractToken(downloadUrl: string): string {
    const parts = downloadUrl.split('/');
    return parts[parts.length - 1] || parts[parts.length - 2];
  }
}
