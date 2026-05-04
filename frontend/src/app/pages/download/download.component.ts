import { DatePipe } from '@angular/common';
import { httpResource } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import type { FileUploadResponse, UploadGroupInfoResponse } from '../../api/model';
import { FileService, type RecipientStatsResponse } from '../../services';
import {
  filenameToEmoji,
  formatFileSize,
  isExpired,
  resolveAppUrl,
  toUserFacingErrorMessage,
} from '../../utils/index';

interface DownloadRequestOptions {
  accessToken: string | null;
  fallbackFilename: string;
  reload: () => void;
  url: string;
}

type ResponseChunk = Uint8Array<ArrayBuffer>;

interface FileSystemWritableFileStreamLike extends WritableStream<ResponseChunk> {
  close: () => Promise<void>;
  write: (data: BufferSource | Blob | string) => Promise<void>;
}

interface FileSystemFileHandleLike {
  createWritable: () => Promise<FileSystemWritableFileStreamLike>;
}

interface SaveFilePickerWindow extends Window {
  showSaveFilePicker?: (options?: { suggestedName?: string }) => Promise<FileSystemFileHandleLike>;
}

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, FormsModule],
  selector: 'app-download',
  standalone: true,
  styleUrl: './download.component.scss',
  templateUrl: './download.component.html',
})
export class DownloadComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly fileService = inject(FileService);

  private readonly token = this.route.snapshot.paramMap.get('token') ?? '';
  private readonly group = this.route.snapshot.paramMap.get('group') ?? '';

  isGroup = Boolean(this.group);

  /** Password input by user. */
  enteredPassword = signal('');

  /** Password token from query param (for email invite links). */
  passwordToken = signal(
    this.route.snapshot.queryParamMap.get('password') ??
      this.getPasswordFromFragment(this.route.snapshot.fragment),
  );

  /** Password verification error. */
  passwordError = signal('');

  private readonly fileInfoResource = this.token
    ? httpResource<FileUploadResponse>(() => {
        const pw = this.passwordToken();
        const base = `/api/files/${this.token}/info`;
        return pw ? { headers: { 'X-Access-Token': pw }, url: base } : { url: base };
      })
    : undefined;

  private readonly groupInfoResource = this.group
    ? httpResource<UploadGroupInfoResponse>(() => {
        const pw = this.passwordToken();
        const base = `/api/files/group/${this.group}`;
        return pw ? { headers: { 'X-Access-Token': pw }, url: base } : { url: base };
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

  otherRecipientDownloads = computed(() => {
    const stats = this.recipientStats();
    if (!stats) {
      return 0;
    }

    const recipientDownloads = stats.downloads.reduce(
      (sum, entry) => sum + entry.download_count,
      0,
    );
    return Math.max(0, stats.total_downloads - recipientDownloads);
  });

  showOtherRecipientDownloads = computed(() => {
    const group = this.groupInfo();
    const stats = this.recipientStats();
    return Boolean(group?.has_passwords && stats && stats.downloads.length > 0);
  });

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

  private async getDownloadErrorDetail(response: Response): Promise<string> {
    const body = (await response.json().catch(() => null)) as unknown;
    if (typeof body === 'object' && body !== null) {
      const detail: unknown = Reflect.get(body, 'detail');
      if (typeof detail === 'object' && detail !== null) {
        const message: unknown = Reflect.get(detail, 'message');
        if (typeof message === 'string') {
          return toUserFacingErrorMessage(message);
        }
      }
      if (typeof detail === 'string') {
        return toUserFacingErrorMessage(detail);
      }
    }
    return 'Download failed.';
  }

  async download(): Promise<void> {
    const url = this.fileService.getDownloadUrlWithPassword(
      this.token,
      this.passwordToken() || undefined,
    );
    await this.downloadFromUrl({
      accessToken: this.passwordToken() || null,
      fallbackFilename: this.fileInfo()?.original_filename ?? 'download',
      reload: () => {
        this.fileInfoResource?.reload();
      },
      url,
    });
  }

  async downloadGroup(): Promise<void> {
    const url = this.fileService.getGroupDownloadUrlWithPassword(
      this.group,
      this.passwordToken() || undefined,
    );
    await this.downloadFromUrl({
      accessToken: this.passwordToken() || null,
      fallbackFilename: this.groupDownloadFallbackFilename(),
      reload: () => {
        this.groupInfoResource?.reload();
      },
      url,
    });
  }

  private async downloadFromUrl(options: DownloadRequestOptions): Promise<void> {
    this.downloadError.set('');
    this.downloading.set(true);
    let writableStream: FileSystemWritableFileStreamLike | null = null;
    let completed = false;
    try {
      if (!options.accessToken) {
        this.startBrowserDownload(options.url);
        return;
      }

      writableStream = await this.openWritableDownloadStream(options.fallbackFilename);
      const response = await fetch(options.url, {
        credentials: 'include',
        headers: options.accessToken ? { 'X-Access-Token': options.accessToken } : undefined,
      });
      if (!response.ok) {
        await this.abortWritableStream(writableStream);
        const detail = await this.getDownloadErrorDetail(response);
        this.downloadError.set(detail);
        options.reload();
        return;
      }

      const filename = this.getFilenameFromContentDisposition(response) ?? options.fallbackFilename;

      if (writableStream && response.body) {
        await this.writeResponseToStream(response, writableStream);
      } else {
        const blob = await response.blob();
        this.triggerDownload(blob, filename);
      }

      completed = true;
      options.reload();
    } catch (error: unknown) {
      if (!completed) {
        await this.abortWritableStream(writableStream);
      }
      if (this.isUserCancelledDownload(error)) {
        return;
      }
      this.downloadError.set('Download failed. Please try again.');
    } finally {
      this.downloading.set(false);
    }
  }

  private startBrowserDownload(url: string): void {
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.rel = 'noopener';
    anchor.style.display = 'none';
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
  }

  private async openWritableDownloadStream(
    suggestedName: string,
  ): Promise<FileSystemWritableFileStreamLike | null> {
    const pickerWindow = window as SaveFilePickerWindow;
    if (!window.isSecureContext || typeof pickerWindow.showSaveFilePicker !== 'function') {
      return null;
    }

    const handle = await pickerWindow.showSaveFilePicker({ suggestedName });
    return handle.createWritable();
  }

  private async writeResponseToStream(
    response: Response,
    writableStream: FileSystemWritableFileStreamLike,
  ): Promise<void> {
    if (!response.body) {
      const blob = await response.blob();
      await writableStream.write(blob);
      await writableStream.close();
      return;
    }

    try {
      await response.body.pipeTo(writableStream);
    } catch (error: unknown) {
      await writableStream.abort?.(error).catch(() => {});
      throw error;
    }
  }

  private async abortWritableStream(
    writableStream: FileSystemWritableFileStreamLike | null,
  ): Promise<void> {
    if (!writableStream) {
      return;
    }

    if (typeof writableStream.abort === 'function') {
      await writableStream.abort().catch(() => {});
      return;
    }

    await writableStream.close().catch(() => {});
  }

  private isUserCancelledDownload(error: unknown): boolean {
    return error instanceof DOMException && error.name === 'AbortError';
  }

  private getFilenameFromContentDisposition(response: Response): string | null {
    const disposition = response.headers.get('Content-Disposition');
    if (!disposition) {
      return null;
    }

    const encodedMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    if (encodedMatch) {
      return decodeURIComponent(encodedMatch[1]);
    }

    return disposition.match(/filename="?([^";]+)"?/i)?.[1] ?? null;
  }

  private groupDownloadFallbackFilename(): string {
    const group = this.groupInfo();
    const trimmedTitle = group?.title?.trim();
    const baseName =
      trimmedTitle === undefined || trimmedTitle === ''
        ? `sendr-${this.group.slice(0, 8)}`
        : trimmedTitle;
    return group?.will_zip ? `${baseName.replace(/\.zip$/i, '')}.zip` : baseName;
  }

  private triggerDownload(blob: Blob, filename: string): void {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  private getPasswordFromFragment(fragment: string | null): string {
    if (!fragment) {
      return '';
    }
    return new URLSearchParams(fragment).get('password') ?? '';
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
    return `${base}#password=${encodeURIComponent(password)}`;
  }
}
