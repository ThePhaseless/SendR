import { Component, inject, signal } from "@angular/core";
import type { OnInit } from "@angular/core";
import { FileService } from "../../services/file.service";
import type { FileUploadResponse } from "../../services/file.service";
import { extractDownloadToken, formatFileSize, isExpired } from "../../utils/file.utils";
import { DatePipe } from "@angular/common";
import { resolveAppUrl } from "../../utils/url.utils";

@Component({
  imports: [DatePipe],
  selector: "app-dashboard",
  styleUrl: "./dashboard.component.scss",
  templateUrl: "./dashboard.component.html",
})
export class DashboardComponent implements OnInit {
  private readonly fileService = inject(FileService);

  files = signal<FileUploadResponse[]>([]);
  loading = signal(true);
  error = signal<string | null>(null);
  copiedId = signal<number | null>(null);

  ngOnInit(): void {
    this.loadFiles();
  }

  private loadFiles(): void {
    this.loading.set(true);
    this.fileService.listFiles().subscribe({
      error: () => {
        this.error.set("Failed to load files.");
        this.loading.set(false);
      },
      next: (res) => {
        this.files.set(res.files);
        this.loading.set(false);
      },
    });
  }

  copyLink(file: FileUploadResponse): void {
    const token = extractDownloadToken(file.download_url);
    const link = resolveAppUrl(`download/${token}`);
    void navigator.clipboard.writeText(link);
    this.copiedId.set(file.id);
    setTimeout(() => {
      this.copiedId.set(null);
    }, 2000);
  }

  refreshFile(file: FileUploadResponse): void {
    this.fileService.refreshFile(file.id).subscribe({
      error: () => {
        this.error.set("Failed to refresh file link.");
      },
      next: (updated) => {
        this.files.update((files) => files.map((f) => (f.id === updated.id ? updated : f)));
      },
    });
  }

  deleteFile(file: FileUploadResponse): void {
    this.fileService.deleteFile(file.id).subscribe({
      error: () => {
        this.error.set("Failed to delete file.");
      },
      next: () => {
        this.files.update((files) => files.filter((f) => f.id !== file.id));
      },
    });
  }

  formatSize(bytes: number): string {
    return formatFileSize(bytes);
  }

  isExpired(expiresAt: string): boolean {
    return isExpired(expiresAt);
  }
}
