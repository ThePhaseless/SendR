import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { FileService, FileUploadResponse } from '../../services/file.service';
import { DatePipe } from '@angular/common';

@Component({
  selector: 'app-download',
  imports: [DatePipe],
  templateUrl: './download.component.html',
  styleUrl: './download.component.scss',
})
export class DownloadComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly fileService = inject(FileService);

  fileInfo = signal<FileUploadResponse | null>(null);
  error = signal<string | null>(null);
  loading = signal(true);
  private token = '';

  ngOnInit(): void {
    this.token = this.route.snapshot.paramMap.get('token') ?? '';
    if (!this.token) {
      this.error.set('Invalid download link.');
      this.loading.set(false);
      return;
    }

    this.fileService.getFileInfo(this.token).subscribe({
      next: (info) => {
        this.fileInfo.set(info);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('File not found or has expired.');
        this.loading.set(false);
      },
    });
  }

  download(): void {
    window.location.href = this.fileService.getDownloadUrl(this.token);
  }

  formatSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  isExpired(expiresAt: string): boolean {
    return new Date(expiresAt) < new Date();
  }
}
