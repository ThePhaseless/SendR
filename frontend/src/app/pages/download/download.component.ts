import { DatePipe } from '@angular/common';
import { httpResource } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import type {
  FileUploadResponse,
  RecipientStatsResponse,
  UploadGroupInfoResponse,
} from '../../api/model';
import { FileService } from '../../services';
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

interface SuccessfulDownloadOptions {
  filename: string;
  onComplete: () => void;
  reload: () => void;
  response: Response;
  writableStream: FileSystemWritableFileStreamLike | null;
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

  private readonly recipientStatsResource = this.group
    ? httpResource<RecipientStatsResponse>(() => {
        const token = this.passwordToken();
        if (!token) {
          return;
        }

        return {
          headers: { 'X-Access-Token': token },
          url: `/api/files/group/${encodeURIComponent(this.group)}/recipient-stats`,
        };
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
  recipientStats = computed(() =>
    this.recipientStatsResource?.hasValue() ? this.recipientStatsResource.value() : null,
  );
  recipientStatsLoading = computed(() => this.recipientStatsResource?.isLoading() ?? false);

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

  submitPassword(): void {
    const pw = this.enteredPassword().trim();
    if (!pw) {
      return;
    }
    // Set the password token (it will be used in download URLs)
    this.passwordToken.set(pw);
    this.passwordError.set('');
  }

  private getDownloadErrorDetail(response: Response): Promise<string> {
    return response
      .json()
      .catch(() => null)
      .then((body: unknown) => {
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
      });
  }

  download(): void {
    const url = this.fileService.getDownloadUrlWithPassword(
      this.token,
      this.passwordToken() || undefined,
    );
    this.downloadFromUrl({
      accessToken: this.passwordToken() || null,
      fallbackFilename: this.fileInfo()?.original_filename ?? 'download',
      reload: () => {
        this.fileInfoResource?.reload();
      },
      url,
    });
  }

  downloadGroup(): void {
    const url = this.fileService.getGroupDownloadUrlWithPassword(
      this.group,
      this.passwordToken() || undefined,
    );
    this.downloadFromUrl({
      accessToken: this.passwordToken() || null,
      fallbackFilename: this.groupDownloadFallbackFilename(),
      reload: () => {
        this.groupInfoResource?.reload();
      },
      url,
    });
  }

  private downloadFromUrl(options: DownloadRequestOptions): void {
    this.downloadError.set('');
    this.downloading.set(true);
    let writableStream: FileSystemWritableFileStreamLike | null = null;
    let completed = false;

    if (!options.accessToken) {
      this.startBrowserDownload(options.url);
      this.downloading.set(false);
      return;
    }

    void this.openWritableDownloadStream(options.fallbackFilename)
      .then((stream) => {
        writableStream = stream;
        return fetch(options.url, {
          credentials: 'include',
          headers: { 'X-Access-Token': options.accessToken ?? '' },
        });
      })
      .then((response) => {
        if (!response.ok) {
          return this.handleDownloadErrorResponse(response, writableStream, options);
        }

        const filename =
          this.getFilenameFromContentDisposition(response) ?? options.fallbackFilename;

        return this.writeSuccessfulDownload({
          filename,
          onComplete: () => {
            completed = true;
          },
          reload: options.reload,
          response,
          writableStream,
        });
      })
      .then(undefined, (error: unknown) =>
        this.handleDownloadFailure(error, completed, writableStream),
      )
      .finally(() => {
        this.downloading.set(false);
      });
  }

  private handleDownloadErrorResponse(
    response: Response,
    writableStream: FileSystemWritableFileStreamLike | null,
    options: DownloadRequestOptions,
  ): Promise<void> {
    return this.abortWritableStream(writableStream)
      .then(() => this.getDownloadErrorDetail(response))
      .then((detail) => {
        this.downloadError.set(detail);
        options.reload();
      });
  }

  private writeSuccessfulDownload(options: SuccessfulDownloadOptions): Promise<void> {
    return this.writeResponseToDestination(
      options.response,
      options.writableStream,
      options.filename,
    ).then(() => {
      options.onComplete();
      options.reload();
    });
  }

  private handleDownloadFailure(
    error: unknown,
    completed: boolean,
    writableStream: FileSystemWritableFileStreamLike | null,
  ): Promise<void> {
    if (completed || this.isUserCancelledDownload(error)) {
      return Promise.resolve();
    }

    return this.abortWritableStream(writableStream).then(() => {
      this.downloadError.set('Download failed. Please try again.');
    });
  }

  private writeResponseToDestination(
    response: Response,
    writableStream: FileSystemWritableFileStreamLike | null,
    filename: string,
  ): Promise<void> {
    if (writableStream && response.body) {
      return this.writeResponseToStream(response, writableStream);
    }

    return response.blob().then((blob) => {
      this.triggerDownload(blob, filename);
    });
  }

  private openWritableDownloadStream(
    suggestedName: string,
  ): Promise<FileSystemWritableFileStreamLike | null> {
    const pickerWindow = window as SaveFilePickerWindow;
    if (!window.isSecureContext || typeof pickerWindow.showSaveFilePicker !== 'function') {
      return Promise.resolve(null);
    }

    return pickerWindow
      .showSaveFilePicker({ suggestedName })
      .then((handle) => handle.createWritable());
  }

  private writeResponseToStream(
    response: Response,
    writableStream: FileSystemWritableFileStreamLike,
  ): Promise<void> {
    if (!response.body) {
      return response
        .blob()
        .then((blob) => writableStream.write(blob))
        .then(() => writableStream.close());
    }

    return response.body
      .pipeTo(writableStream)
      .then(undefined, (error: unknown) => this.abortFailedPipe(writableStream, error));
  }

  private abortFailedPipe(
    writableStream: FileSystemWritableFileStreamLike,
    error: unknown,
  ): Promise<never> {
    return writableStream.abort(error).then(
      () => {
        throw error;
      },
      () => {
        throw error;
      },
    );
  }

  private abortWritableStream(
    writableStream: FileSystemWritableFileStreamLike | null,
  ): Promise<void> {
    if (!writableStream) {
      return Promise.resolve();
    }

    if (typeof writableStream.abort === 'function') {
      return writableStream.abort().then(undefined, DownloadComponent.ignoreWritableStreamError);
    }

    return writableStream.close().then(undefined, DownloadComponent.ignoreWritableStreamError);
  }

  private static ignoreWritableStreamError(this: void): void {}

  private isUserCancelledDownload(error: unknown): boolean {
    return error instanceof DOMException && error.name === 'AbortError';
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
