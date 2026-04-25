import { DatePipe } from "@angular/common";
import type { OnInit } from "@angular/core";
import { Component, computed, inject, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import type { UploadFileEntry } from "../../components/file-picker/file-picker.component";
import { FilePickerComponent } from "../../components/file-picker/file-picker.component";
import { UploadSettingsComponent } from "../../components/upload-settings/upload-settings.component";
import { AuthService } from "../../services/auth.service";
import type {
  AccessEditRequest,
  AccessInfoResponse,
  DownloadStatsResponse,
  FileUploadResponse,
} from "../../services/file.service";
import { FileService } from "../../services/file.service";
import { extractDownloadToken, formatFileSize, isExpired } from "../../utils/file.utils";
import { getErrorDetail } from "../../utils/error.utils";
import { resolveAppUrl } from "../../utils/url.utils";

export interface UploadGroup {
  key: string;
  files: FileUploadResponse[];
  isGroup: boolean;
  uploadGroup: string | null;
  totalSize: number;
}

@Component({
  imports: [DatePipe, FormsModule, FilePickerComponent, UploadSettingsComponent],
  selector: "app-dashboard",
  styleUrl: "./dashboard.component.scss",
  templateUrl: "./dashboard.component.html",
})
export class DashboardComponent implements OnInit {
  private readonly fileService = inject(FileService);
  private readonly authService = inject(AuthService);

  files = signal<FileUploadResponse[]>([]);
  loading = signal(true);
  error = signal<string | null>(null);
  copiedGroupKey = signal<string | null>(null);
  expandedGroupKey = signal<string | null>(null);
  userTier = signal("temporary");

  // Unified panel settings (bound to upload-settings component)
  panelExpiryHours = signal(72);
  panelMaxDownloads = signal(0);
  panelTitle = signal("");
  panelDescription = signal("");
  // Download stats for the expanded group
  groupStats = signal<DownloadStatsResponse | null>(null);
  statsLoading = signal(false);
  statsExpanded = signal(false);

  // Access control for the expanded group
  accessInfo = signal<AccessInfoResponse | null>(null);
  accessLoading = signal(false);
  newPasswordLabel = signal("");
  newPasswordValue = signal("");
  newEmail = signal("");

  // Staged new files for the expanded group
  newFiles = signal<UploadFileEntry[]>([]);
  isSaving = signal(false);

  // Refresh warning dialog
  showRefreshWarning = signal(false);
  pendingRefreshGroup = signal<UploadGroup | null>(null);

  /** Groups files by upload_group. */
  uploadGroups = computed<UploadGroup[]>(() => {
    const allFiles = this.files();
    const groupMap = new Map<string, FileUploadResponse[]>();
    const singles: FileUploadResponse[] = [];

    for (const file of allFiles) {
      if (file.upload_group) {
        const existing = groupMap.get(file.upload_group) ?? [];
        existing.push(file);
        groupMap.set(file.upload_group, existing);
      } else {
        singles.push(file);
      }
    }

    const groups: UploadGroup[] = [];
    for (const [groupKey, groupFiles] of groupMap) {
      groups.push({
        files: groupFiles,
        isGroup: true,
        key: groupKey,
        totalSize: groupFiles.reduce((sum, f) => sum + f.file_size_bytes, 0),
        uploadGroup: groupKey,
      });
    }
    for (const file of singles) {
      groups.push({
        files: [file],
        isGroup: false,
        key: `single-${file.id}`,
        totalSize: file.file_size_bytes,
        uploadGroup: null,
      });
    }

    // Sort: active first, then by latest expiry desc
    groups.sort((a, b) => {
      const aExpired = this.isGroupExpired(a) ? 1 : 0;
      const bExpired = this.isGroupExpired(b) ? 1 : 0;
      if (aExpired !== bExpired) {
        return aExpired - bExpired;
      }
      const aExpiry = Math.max(...a.files.map((f) => new Date(f.expires_at).getTime()));
      const bExpiry = Math.max(...b.files.map((f) => new Date(f.expires_at).getTime()));
      return bExpiry - aExpiry;
    });

    return groups;
  });

  ngOnInit(): void {
    this.loadFiles();
    this.authService.getMe().subscribe({
      next: (me) => {
        this.userTier.set(me.tier);
      },
    });
  }

  private loadFiles(): void {
    this.loading.set(true);
    this.fileService.listFiles().subscribe({
      error: (err: unknown) => {
        this.error.set(getErrorDetail(err, "Failed to load uploads."));
        this.loading.set(false);
      },
      next: (res) => {
        this.files.set(res.files);
        this.loading.set(false);
      },
    });
  }

  isGroupExpired(group: UploadGroup): boolean {
    return group.files.every((f) => isExpired(f.expires_at) || !f.is_active);
  }

  isAnyActive(group: UploadGroup): boolean {
    return group.files.some((f) => f.is_active && !isExpired(f.expires_at));
  }

  /** Check if an expired group is within the 14-day premium refresh grace period. */
  isWithinGrace(group: UploadGroup): boolean {
    const latestExpiry = Math.max(...group.files.map((f) => new Date(f.expires_at).getTime()));
    const graceCutoff = Date.now() - 14 * 24 * 60 * 60 * 1000;
    return latestExpiry > graceCutoff;
  }

  canRefresh(group: UploadGroup): boolean {
    if (this.userTier() === "temporary") {
      return false;
    }
    if (this.isGroupExpired(group)) {
      return this.userTier() === "premium" && this.isWithinGrace(group);
    }
    return true;
  }

  canSave(): boolean {
    return this.userTier() !== "temporary";
  }

  hasUnsavedFiles(): boolean {
    return this.newFiles().length > 0;
  }

  getGroupExpiry(group: UploadGroup): string {
    const latest = group.files.reduce((max, f) => {
      const d = new Date(f.expires_at);
      return d > max ? d : max;
    }, new Date(0));
    return latest.toISOString();
  }

  getGroupDownloads(group: UploadGroup): string {
    const total = group.files.reduce((sum, f) => sum + f.download_count, 0);
    const maxDl = group.files[0]?.max_downloads;
    if (maxDl) {
      return `${total}/${maxDl * group.files.length}`;
    }
    return `${total}`;
  }

  copyLink(group: UploadGroup): void {
    let link: string;
    if (group.isGroup && group.uploadGroup) {
      link = resolveAppUrl(`download/group/${group.uploadGroup}`);
    } else {
      const token = extractDownloadToken(group.files[0].download_url);
      link = resolveAppUrl(`download/${token}`);
    }
    void navigator.clipboard.writeText(link);
    this.copiedGroupKey.set(group.key);
    setTimeout(() => {
      this.copiedGroupKey.set(null);
    }, 2000);
  }

  getDownloadPageUrl(group: UploadGroup): string {
    if (group.isGroup && group.uploadGroup) {
      return resolveAppUrl(`download/group/${group.uploadGroup}`);
    }
    const token = extractDownloadToken(group.files[0].download_url);
    return resolveAppUrl(`download/${token}`);
  }

  toggleExpanded(groupKey: string): void {
    if (this.expandedGroupKey() === groupKey) {
      this.expandedGroupKey.set(null);
      this.newFiles.set([]);
      this.groupStats.set(null);
      this.accessInfo.set(null);
      this.statsExpanded.set(false);
    } else {
      this.expandedGroupKey.set(groupKey);
      this.newFiles.set([]);
      this.groupStats.set(null);
      this.accessInfo.set(null);
      this.statsExpanded.set(false);
      this.newPasswordLabel.set("");
      this.newPasswordValue.set("");
      this.newEmail.set("");
      // Pre-populate panel settings from the group
      const group = this.uploadGroups().find((g) => g.key === groupKey);
      if (group) {
        const ref = group.files[0];
        const hoursLeft = Math.max(
          1,
          Math.ceil((new Date(ref.expires_at).getTime() - Date.now()) / (1000 * 60 * 60)),
        );
        // Snap to nearest valid expiry option so the select shows a valid value
        this.panelExpiryHours.set(this.snapToNearestExpiry(hoursLeft));
        this.panelMaxDownloads.set(ref.max_downloads ?? 0);
        // Load download stats and group info (for title/description)
        if (group.uploadGroup) {
          this.loadGroupStats(group.uploadGroup);
          this.loadGroupInfo(group.uploadGroup);
          this.loadAccessInfo(group.uploadGroup);
        }
      }
    }
  }

  /** Save group settings in-place (premium only, keeps download tokens). */
  saveGroup(group: UploadGroup): void {
    this.isSaving.set(true);

    // First: if there are staged new files, add them to the group
    const addFilesObs =
      group.uploadGroup && this.newFiles().length > 0
        ? this.fileService.addFilesToGroup(
            group.uploadGroup,
            this.newFiles().map((e) => e.file),
          )
        : null;

    const finishSave = () => {
      // Then: edit group settings
      if (group.isGroup && group.uploadGroup) {
        this.fileService
          .editGroup(group.uploadGroup, {
            description: this.panelDescription() || null,
            expiry_hours: this.panelExpiryHours(),
            max_downloads: this.panelMaxDownloads() || undefined,
            title: this.panelTitle() || null,
          })
          .subscribe({
            error: (err: unknown) => {
              this.error.set(getErrorDetail(err, "Failed to save changes."));
              this.isSaving.set(false);
            },
            next: (res) => {
              this.files.update((files) => {
                const updatedIds = new Set(res.files.map((f) => f.id));
                return [...files.filter((f) => !updatedIds.has(f.id)), ...res.files];
              });
              this.newFiles.set([]);
              this.isSaving.set(false);
            },
          });
      } else {
        // Single file: use per-file edit
        const file = group.files[0];
        this.fileService
          .editFile(file.id, {
            expires_in_hours: this.panelExpiryHours(),
            max_downloads: this.panelMaxDownloads() || undefined,
          })
          .subscribe({
            error: (err: unknown) => {
              this.error.set(getErrorDetail(err, "Failed to save changes."));
              this.isSaving.set(false);
            },
            next: (updated) => {
              this.files.update((files) => files.map((f) => (f.id === updated.id ? updated : f)));
              this.isSaving.set(false);
            },
          });
      }
    };

    if (addFilesObs) {
      addFilesObs.subscribe({
        error: (err: unknown) => {
          this.error.set(getErrorDetail(err, "Failed to add new files."));
          this.isSaving.set(false);
        },
        next: (res) => {
          this.files.update((existing) => [...existing, ...res.files]);
          finishSave();
        },
      });
    } else {
      finishSave();
    }
  }

  /** Show refresh confirmation warning. */
  confirmRefresh(group: UploadGroup): void {
    this.pendingRefreshGroup.set(group);
    this.showRefreshWarning.set(true);
  }

  /** Cancel refresh warning. */
  cancelRefresh(): void {
    this.showRefreshWarning.set(false);
    this.pendingRefreshGroup.set(null);
  }

  /** Execute refresh after confirmation. */
  executeRefresh(): void {
    const group = this.pendingRefreshGroup();
    if (!group) {
      return;
    }
    this.showRefreshWarning.set(false);
    this.pendingRefreshGroup.set(null);
    this.isSaving.set(true);

    // First: if there are staged new files, add them to the group
    const addFilesObs =
      group.uploadGroup && this.newFiles().length > 0
        ? this.fileService.addFilesToGroup(
            group.uploadGroup,
            this.newFiles().map((e) => e.file),
          )
        : null;

    const doRefresh = () => {
      if (group.isGroup && group.uploadGroup) {
        this.fileService
          .refreshGroup(group.uploadGroup, {
            description: this.panelDescription() || null,
            expiry_hours: this.panelExpiryHours(),
            max_downloads: this.panelMaxDownloads() || undefined,
            title: this.panelTitle() || null,
          })
          .subscribe({
            error: (err: unknown) => {
              this.error.set(getErrorDetail(err, "Failed to refresh upload."));
              this.isSaving.set(false);
            },
            next: (res) => {
              this.files.update((files) => {
                const updatedIds = new Set(res.files.map((f) => f.id));
                return [...files.filter((f) => !updatedIds.has(f.id)), ...res.files];
              });
              this.newFiles.set([]);
              this.isSaving.set(false);
            },
          });
      } else {
        // Single file refresh
        const file = group.files[0];
        this.fileService.refreshFile(file.id, this.panelExpiryHours()).subscribe({
          error: (err: unknown) => {
            this.error.set(getErrorDetail(err, "Failed to refresh upload."));
            this.isSaving.set(false);
          },
          next: (updated) => {
            this.files.update((files) => files.map((f) => (f.id === updated.id ? updated : f)));
            this.newFiles.set([]);
            this.isSaving.set(false);
          },
        });
      }
    };

    if (addFilesObs) {
      addFilesObs.subscribe({
        error: (err: unknown) => {
          this.error.set(getErrorDetail(err, "Failed to add new files."));
          this.isSaving.set(false);
        },
        next: (res) => {
          this.files.update((existing) => [...existing, ...res.files]);
          doRefresh();
        },
      });
    } else {
      doRefresh();
    }
  }

  /** Remove a single file (delete from server). */
  removeFile(file: FileUploadResponse, group: UploadGroup): void {
    this.fileService.deleteFile(file.id).subscribe({
      error: (err: unknown) => {
        this.error.set(getErrorDetail(err, "Failed to delete file."));
      },
      next: () => {
        this.files.update((files) => files.filter((f) => f.id !== file.id));
        if (group.files.length <= 1) {
          this.expandedGroupKey.set(null);
        }
      },
    });
  }

  /** Delete all files in a group. */
  deleteGroup(group: UploadGroup): void {
    this.expandedGroupKey.set(null);
    for (const file of group.files) {
      this.fileService.deleteFile(file.id).subscribe({
        error: (err: unknown) => {
          this.error.set(getErrorDetail(err, "Failed to delete upload."));
        },
        next: () => {
          this.files.update((files) => files.filter((f) => f.id !== file.id));
        },
      });
    }
  }

  private loadGroupStats(uploadGroup: string): void {
    this.statsLoading.set(true);
    this.fileService.getGroupStats(uploadGroup).subscribe({
      error: () => {
        this.statsLoading.set(false);
      },
      next: (stats) => {
        this.groupStats.set(stats);
        this.statsLoading.set(false);
      },
    });
  }

  private loadGroupInfo(uploadGroup: string): void {
    this.fileService.getGroupInfo(uploadGroup).subscribe({
      next: (info) => {
        this.panelTitle.set(info.title ?? "");
        this.panelDescription.set(info.description ?? "");
      },
    });
  }

  private loadAccessInfo(uploadGroup: string): void {
    this.accessLoading.set(true);
    this.fileService.getAccessInfo(uploadGroup).subscribe({
      error: () => {
        this.accessLoading.set(false);
      },
      next: (info) => {
        this.accessInfo.set(info);
        this.accessLoading.set(false);
      },
    });
  }

  toggleStatsExpanded(): void {
    this.statsExpanded.update((v) => !v);
  }

  editAccess(uploadGroup: string, body: AccessEditRequest): void {
    this.accessLoading.set(true);
    this.fileService.editAccess(uploadGroup, body).subscribe({
      error: (err: unknown) => {
        this.error.set(getErrorDetail(err, "Failed to update access control."));
        this.accessLoading.set(false);
      },
      next: (info) => {
        this.accessInfo.set(info);
        this.accessLoading.set(false);
        // Update file list badges
        this.files.update((files) =>
          files.map((f) => {
            if (f.upload_group === uploadGroup) {
              return {
                ...f,
                has_email_recipients: info.emails.length > 0,
                has_passwords: info.passwords.length > 0,
                is_public: info.is_public,
              };
            }
            return f;
          }),
        );
      },
    });
  }

  addPassword(uploadGroup: string): void {
    const label = this.newPasswordLabel().trim();
    const password = this.newPasswordValue().trim();
    if (!password) {
      return;
    }
    this.editAccess(uploadGroup, {
      passwords_to_add: [{ label: label || "Password", password }],
    });
    this.newPasswordLabel.set("");
    this.newPasswordValue.set("");
  }

  removePassword(uploadGroup: string, passwordId: number): void {
    this.editAccess(uploadGroup, { password_ids_to_remove: [passwordId] });
  }

  addEmail(uploadGroup: string): void {
    const email = this.newEmail().trim().toLowerCase();
    if (!email) {
      return;
    }
    this.editAccess(uploadGroup, { emails_to_add: [email] });
    this.newEmail.set("");
  }

  removeEmail(uploadGroup: string, emailId: number): void {
    this.editAccess(uploadGroup, { email_ids_to_remove: [emailId] });
  }

  togglePublic(uploadGroup: string, isPublic: boolean): void {
    this.editAccess(uploadGroup, { is_public: isPublic });
  }

  toggleShowEmailStats(uploadGroup: string, show: boolean): void {
    this.editAccess(uploadGroup, { show_email_stats: show });
  }

  formatSize(bytes: number): string {
    return formatFileSize(bytes);
  }

  isExpired(expiresAt: string): boolean {
    return isExpired(expiresAt);
  }

  /** Snap a raw hours value to the nearest valid expiry option for the user's tier. */
  private snapToNearestExpiry(hours: number): number {
    const tier = this.userTier();
    let options: number[];
    if (tier === "premium") {
      options = [1, 24, 72, 168, 336, 720];
    } else if (tier === "free") {
      options = [1, 24, 72, 168];
    } else {
      options = [24, 72];
    }
    return options.reduce((best, opt) =>
      Math.abs(opt - hours) < Math.abs(best - hours) ? opt : best,
    );
  }
}
