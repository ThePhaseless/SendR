import { DatePipe } from '@angular/common';
import { httpResource } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import type { FileUploadResponse, UploadGroupInfoResponse } from '../../api/model';
import { AuthService } from '../../services/auth.service';
import type { RecipientStatsResponse } from '../../services/file.service';
import { FileService } from '../../services/file.service';
import { filenameToEmoji, formatFileSize, isExpired } from '../../utils/file.utils';
import { resolveAppUrl } from '../../utils/url.utils';

@Component({
  imports: [DatePipe, FormsModule],
  selector: 'app-download',
  styleUrl: './download.component.scss',
  templateUrl: './download.component.html',
})
export class DownloadComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly authService = inject(AuthService);
  private readonly fileService = inject(FileService);

  private readonly token = this.route.snapshot.paramMap.get('token') ?? '';
  private readonly group = this.route.snapshot.paramMap.get('group') ?? '';

  isGroup = Boolean(this.group);

  /** Password input by user. */
  enteredPassword = signal('');

  /** Password token from query param (for email invite links). */
  passwordToken = signal(this.route.snapshot.queryParamMap.get('password') ?? '');

  /** Password verification error. */
  passwordError = signal('');

  private readonly fileInfoResource = this.token
    ? httpResource<FileUploadResponse>(() => {
        const pw = this.passwordToken();
        const base = `/api/files/${this.token}/info`;
        return pw ? `${base}?password=${encodeURIComponent(pw)}` : base;
      })
    : undefined;

  private readonly groupInfoResource = this.group
    ? httpResource<UploadGroupInfoResponse>(() => {
        const pw = this.passwordToken();
        const base = `/api/files/group/${this.group}`;
        return pw ? `${base}?password=${encodeURIComponent(pw)}` : base;
      })
    : undefined;

  fileInfo = computed(() => this.fileInfoResource?.value() ?? null);
  groupInfo = computed(() => this.groupInfoResource?.value() ?? null);
  error = computed(() => {
    if (this.token && this.fileInfoResource?.error()) {
      return 'File not found or has expired.';
    }
    if (this.group && this.groupInfoResource?.error()) {
      return 'Files not found or have expired.';
    }
    if (!this.token && !this.group) {
      return 'Invalid download link.';
    }
    return null;
  });
  loading = computed(() => {
    if (this.token) {
      return this.fileInfoResource?.isLoading() ?? false;
    }
    if (this.group) {
      return this.groupInfoResource?.isLoading() ?? false;
    }
    return false;
  });

  /** Whether a password is required to see file details (is_public=false means details are hidden). */
  needsPasswordForDetails = computed(() => {
    const file = this.fileInfo();
    const group = this.groupInfo();
    if (file) {
      if (file.viewer_is_owner) {
        return false;
      }
      return !file.is_public && file.has_passwords && !this.passwordToken();
    }
    if (group) {
      if (group.viewer_is_owner) {
        return false;
      }
      return !group.is_public && group.has_passwords && !this.passwordToken();
    }
    return false;
  });

  /** Whether a password is required to download (details visible, but download needs password). */
  needsPasswordToDownload = computed(() => {
    const file = this.fileInfo();
    const group = this.groupInfo();
    if (file) {
      if (file.viewer_is_owner) {
        return false;
      }
      return file.is_public && file.has_passwords && !this.passwordToken();
    }
    if (group) {
      if (group.viewer_is_owner) {
        return false;
      }
      return group.is_public && group.has_passwords && !this.passwordToken();
    }
    return false;
  });

  /** Whether the download limit has been reached for a single file. */
  isFileLimitReached = computed(() => {
    const file = this.fileInfo();
    if (!file || file.viewer_is_owner || !file.max_downloads) {
      return false;
    }
    return file.download_count >= file.max_downloads;
  });

  singleFileGroupDownloadOnly = computed(() => {
    const file = this.fileInfo();
    return Boolean(file && file.group_download_only && !file.viewer_is_owner);
  });

  /** Whether the download limit has been reached for the group. */
  isGroupLimitReached = computed(() => {
    const group = this.groupInfo();
    if (!group || group.viewer_is_owner) {
      return false;
    }
    return group.files.some(
      (f) =>
        f.max_downloads !== null &&
        f.max_downloads !== undefined &&
        f.max_downloads > 0 &&
        f.download_count >= f.max_downloads,
    );
  });

  /** Whether the download limit has been reached for a specific file in a group. */
  isGroupFileLimitReached(file: {
    download_count: number;
    group_download_only?: boolean;
    max_downloads?: number | null;
  }): boolean {
    if (this.groupInfo()?.viewer_is_owner || file.group_download_only || !file.max_downloads) {
      return false;
    }
    return file.download_count >= file.max_downloads;
  }

  groupRestrictsSingleFileDownloads = computed(() => {
    const group = this.groupInfo();
    return Boolean(group && group.files.some((file) => file.group_download_only));
  });

  /** Download error message. */
  downloadError = signal('');

  /** Whether a download is in progress. */
  downloading = signal(false);

  /** Recipient download stats (for email recipients). */
  recipientStats = signal<RecipientStatsResponse | null>(null);
  recipientStatsLoading = signal(false);

  constructor() {
    // If a password token is present (email invite link), try to load recipient stats
    const pwToken = this.passwordToken();
    if (pwToken && this.group) {
      this.loadRecipientStats(pwToken);
    }
  }

  submitPassword(): void {
    const pw = this.enteredPassword().trim();
    if (!pw) {
      return;
    }
    // Set the password token (it will be used in download URLs)
    this.passwordToken.set(pw);
    this.passwordError.set('');
  }

  private loadRecipientStats(token: string): void {
    if (!this.group) {
      return;
    }
    this.recipientStatsLoading.set(true);
    this.fileService.getRecipientStats(this.group, token).subscribe({
      error: () => {
        this.recipientStatsLoading.set(false);
      },
      next: (stats) => {
        this.recipientStats.set(stats);
        this.recipientStatsLoading.set(false);
      },
    });
  }

  private getDownloadHeaders(): HeadersInit | undefined {
    const token = this.authService.getToken();
    if (!token) {
      return undefined;
    }
    return { Authorization: `Bearer ${token}` };
  }

  private async getDownloadErrorDetail(response: Response): Promise<string> {
    const body = (await response.json().catch(() => null)) as unknown;
    if (typeof body === 'object' && body !== null) {
      const detail = Reflect.get(body, 'detail');
      if (typeof detail === 'string') {
        return detail;
      }
    }
    return 'Download failed.';
  }

  async download(): Promise<void> {
    this.downloadError.set('');
    this.downloading.set(true);
    const url = this.fileService.getDownloadUrlWithPassword(
      this.token,
      this.passwordToken() || undefined,
    );
    try {
      const response = await fetch(url, { headers: this.getDownloadHeaders() });
      if (!response.ok) {
        const detail = await this.getDownloadErrorDetail(response);
        this.downloadError.set(detail);
        this.fileInfoResource?.reload();
        return;
      }
      const blob = await response.blob();
      const disposition = response.headers.get('Content-Disposition');
      const match = disposition?.match(/filename="?([^"]+)"?/);
      const filename = match?.[1] ?? this.fileInfo()?.original_filename ?? 'download';
      this.triggerDownload(blob, filename);
      this.fileInfoResource?.reload();
    } catch {
      this.downloadError.set('Download failed. Please try again.');
    } finally {
      this.downloading.set(false);
    }
  }

  async downloadGroup(): Promise<void> {
    this.downloadError.set('');
    this.downloading.set(true);
    const url = this.fileService.getGroupDownloadUrlWithPassword(
      this.group,
      this.passwordToken() || undefined,
    );
    try {
      const response = await fetch(url, { headers: this.getDownloadHeaders() });
      if (!response.ok) {
        const detail = await this.getDownloadErrorDetail(response);
        this.downloadError.set(detail);
        this.groupInfoResource?.reload();
        return;
      }
      const blob = await response.blob();
      const disposition = response.headers.get('Content-Disposition');
      const match = disposition?.match(/filename="?([^"]+)"?/);
      const filename = match?.[1] ?? `sendr-${this.group.slice(0, 8)}.zip`;
      this.triggerDownload(blob, filename);
      this.groupInfoResource?.reload();
    } catch {
      this.downloadError.set('Download failed. Please try again.');
    } finally {
      this.downloading.set(false);
    }
  }

  async downloadSingleFile(downloadUrl: string, originalFilename?: string): Promise<void> {
    this.downloadError.set('');
    this.downloading.set(true);
    const pw = this.passwordToken();
    let url = downloadUrl;
    if (pw) {
      const separator = downloadUrl.includes('?') ? '&' : '?';
      url = `${downloadUrl}${separator}password=${encodeURIComponent(pw)}`;
    }
    try {
      const response = await fetch(url, { headers: this.getDownloadHeaders() });
      if (!response.ok) {
        const detail = await this.getDownloadErrorDetail(response);
        this.downloadError.set(detail);
        this.groupInfoResource?.reload();
        return;
      }
      const blob = await response.blob();
      const disposition = response.headers.get('Content-Disposition');
      const match = disposition?.match(/filename="?([^"]+)"?/);
      const filename = match?.[1] ?? originalFilename ?? 'download';
      this.triggerDownload(blob, filename);
      this.groupInfoResource?.reload();
    } catch {
      this.downloadError.set('Download failed. Please try again.');
    } finally {
      this.downloading.set(false);
    }
  }

  private triggerDownload(blob: Blob, filename: string): void {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  formatSize(bytes: number): string {
    return formatFileSize(bytes);
  }

  isExpired(expiresAt: string): boolean {
    return isExpired(expiresAt);
  }

  getFileEmoji(name: string): string {
    return filenameToEmoji(name);
  }

  formatDownloadCount(file: {
    download_count: number;
    public_download_count?: number;
    restricted_download_count?: number;
    max_downloads?: number | null;
    separate_download_counts?: boolean;
  }): string {
    if (file.separate_download_counts && file.max_downloads) {
      const pub = file.public_download_count ?? 0;
      const res = file.restricted_download_count ?? 0;
      return `Public: ${pub} / ${file.max_downloads} · Restricted: ${res} / ${file.max_downloads}`;
    }
    if (file.max_downloads) {
      return `${file.download_count} / ${file.max_downloads}`;
    }
    return `${file.download_count}`;
  }

  getGroupPageUrl(uploadGroup: string): string {
    const password = this.passwordToken();
    const base = resolveAppUrl(`download/group/${uploadGroup}`);
    if (!password) {
      return base;
    }
    return `${base}?password=${encodeURIComponent(password)}`;
  }
}
