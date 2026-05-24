import { DatePipe } from '@angular/common';
import { HttpClient, httpResource } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import type {
  FileUploadResponse,
  RecipientStatsResponse,
  ScanStatus,
  UploadGroupInfoResponse,
} from '../../api/model';
import { FileService } from '../../services';
import {
  filenameToEmoji,
  formatFileSize,
  getScanStatusDescription,
  getScanStatusLabel,
  getScanStatusTone,
  isBlockedScanStatus,
  isExpired,
  isPendingScanStatus,
  resolveAppUrl,
} from '../../utils/index';

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
  private readonly destroyRef = inject(DestroyRef);
  private readonly fileService = inject(FileService);
  private scanStatusPollTimer?: ReturnType<typeof setInterval>;

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
  scanStatus = computed<ScanStatus | null>(
    () => this.fileInfo()?.scan_status ?? this.groupInfo()?.scan_status ?? null,
  );
  scanStatusLabel = computed(() => getScanStatusLabel(this.scanStatus()));
  scanStatusMessage = computed(() =>
    getScanStatusDescription(this.scanStatus(), this.group ? 'transfer' : 'file'),
  );
  scanStatusTone = computed(() => getScanStatusTone(this.scanStatus()));
  showScanStatusNotice = computed(() => {
    const status = this.scanStatus();
    return isPendingScanStatus(status) || isBlockedScanStatus(status);
  });
  scanPending = computed(() => isPendingScanStatus(this.scanStatus()));
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
    return Boolean(file && file.group_download_only);
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

  constructor() {
    effect(() => {
      if (isPendingScanStatus(this.scanStatus())) {
        this.startScanStatusPolling();
        return;
      }

      this.stopScanStatusPolling();
    });

    effect(() => {
      const fileErr = this.fileInfoResource?.error();
      const groupErr = this.groupInfoResource?.error();
      const err = fileErr ?? groupErr;
      if (err && this.passwordToken()) {
        const status =
          typeof err === 'object' && err !== null && 'status' in err
            ? (err as { status: number }).status
            : undefined;
        if (status === 403) {
          this.passwordError.set('Invalid password. Please try again.');
          this.enteredPassword.set('');
          this.passwordToken.set('');
        }
      }
    });

    this.destroyRef.onDestroy(() => {
      this.stopScanStatusPolling();
    });
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

  download(): void {
    if (this.downloading()) {
      return;
    }
    this.downloading.set(true);
    this.downloadError.set('');

    const url = this.fileService.getDownloadUrlWithPassword(
      this.token,
      this.passwordToken() || undefined,
    );

    window.open(url, '_self');
  }

  downloadGroup(): void {
    if (this.downloading()) {
      return;
    }
    this.downloading.set(true);
    this.downloadError.set('');

    const url = this.fileService.getGroupDownloadUrlWithPassword(
      this.group,
      this.passwordToken() || undefined,
    );

    window.open(url, '_self');
  }

  private startScanStatusPolling(): void {
    if (this.scanStatusPollTimer) {
      return;
    }

    this.scanStatusPollTimer = setInterval(() => {
      this.fileInfoResource?.reload();
      this.groupInfoResource?.reload();
    }, 3000);
  }

  private stopScanStatusPolling(): void {
    if (!this.scanStatusPollTimer) {
      return;
    }

    clearInterval(this.scanStatusPollTimer);
    this.scanStatusPollTimer = undefined;
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
