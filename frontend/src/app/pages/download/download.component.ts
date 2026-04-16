import { DatePipe } from "@angular/common";
import { Component, computed, inject, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { ActivatedRoute } from "@angular/router";
import {
  getFileInfoApiFilesDownloadTokenInfoGetResource,
  getGroupInfoApiFilesGroupUploadGroupGetResource,
} from "../../api/endpoints/filename.resource";
import type { RecipientStatsResponse } from "../../services/file.service";
import { FileService } from "../../services/file.service";
import { filenameToEmoji, formatFileSize, isExpired } from "../../utils/file.utils";

@Component({
  imports: [DatePipe, FormsModule],
  selector: "app-download",
  styleUrl: "./download.component.scss",
  templateUrl: "./download.component.html",
})
export class DownloadComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly fileService = inject(FileService);

  private readonly token = this.route.snapshot.paramMap.get("token") ?? "";
  private readonly group = this.route.snapshot.paramMap.get("group") ?? "";

  isGroup = Boolean(this.group);

  private readonly fileInfoResource = this.token
    ? getFileInfoApiFilesDownloadTokenInfoGetResource(signal(this.token))
    : undefined;

  private readonly groupInfoResource = this.group
    ? getGroupInfoApiFilesGroupUploadGroupGetResource(signal(this.group))
    : undefined;

  fileInfo = computed(() => this.fileInfoResource?.value() ?? null);
  groupInfo = computed(() => this.groupInfoResource?.value() ?? null);
  error = computed(() => {
    if (this.token && this.fileInfoResource?.error()) {
      return "File not found or has expired.";
    }
    if (this.group && this.groupInfoResource?.error()) {
      return "Files not found or have expired.";
    }
    if (!this.token && !this.group) {
      return "Invalid download link.";
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

  /** Whether a password is required to download. */
  needsPassword = computed(() => {
    const file = this.fileInfo();
    const group = this.groupInfo();
    if (file) {
      return file.has_passwords && !this.passwordToken();
    }
    if (group) {
      return group.has_passwords && !this.passwordToken();
    }
    return false;
  });

  /** Password input by user. */
  enteredPassword = signal("");

  /** Password token from query param (for email invite links). */
  passwordToken = signal(this.route.snapshot.queryParamMap.get("password") ?? "");

  /** Password verification error. */
  passwordError = signal("");

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
    this.passwordError.set("");
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

  download(): void {
    window.location.href = this.fileService.getDownloadUrlWithPassword(
      this.token,
      this.passwordToken() || undefined,
    );
  }

  downloadGroup(): void {
    window.location.href = this.fileService.getGroupDownloadUrlWithPassword(
      this.group,
      this.passwordToken() || undefined,
    );
  }

  downloadSingleFile(downloadUrl: string): void {
    const pw = this.passwordToken();
    if (pw) {
      const separator = downloadUrl.includes("?") ? "&" : "?";
      window.location.href = `${downloadUrl}${separator}password=${encodeURIComponent(pw)}`;
    } else {
      window.location.href = downloadUrl;
    }
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
}
