import { DatePipe } from '@angular/common';
import { httpResource } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type {
  AdminUserListResponse,
  AdminUserLoginEntry,
  AdminUserStatsResponse,
  FileListResponse,
  UserResponse,
} from '../../api/model';
import { AdminService } from '../../services/admin.service';
import { ConfirmDialogService } from '../../services/confirm-dialog.service';
import type { FileUploadResponse } from '../../services/file.service';
import { formatFileSize, getApiDateTime, getErrorDetail } from '../../utils/index';

interface AdminTransferGroup {
  uploadGroup: string;
  files: FileUploadResponse[];
  totalSize: number;
  latestExpiry: string;
}

type AdminUser = UserResponse;

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, FormsModule],
  selector: 'app-admin',
  standalone: true,
  styleUrl: './admin.component.scss',
  templateUrl: './admin.component.html',
})
export class AdminComponent {
  private readonly adminService = inject(AdminService);
  private readonly confirmDialog = inject(ConfirmDialogService);

  page = signal(1);
  perPage = 20;
  search = '';
  private readonly appliedSearch = signal('');
  private readonly userListResource = httpResource<AdminUserListResponse>(() => {
    const search = this.appliedSearch();
    const params: Record<string, number | string> = {
      page: this.page(),
      per_page: this.perPage,
    };
    if (search) {
      params['search'] = search;
    }
    return {
      params,
      url: '/api/admin/users',
    };
  });
  private readonly selectedUploadsResource = httpResource<FileListResponse>(() => {
    const user = this.selectedDetailsUser();
    if (!user) {
      return;
    }

    return `/api/admin/users/${user.id}/uploads`;
  });
  private readonly selectedLoginsResource = httpResource<{ logins: AdminUserLoginEntry[] }>(() => {
    const user = this.selectedDetailsUser();
    if (!user) {
      return;
    }

    return `/api/admin/users/${user.id}/logins`;
  });
  private readonly selectedStatsResource = httpResource<AdminUserStatsResponse>(() => {
    const user = this.selectedDetailsUser();
    if (!user) {
      return;
    }

    return `/api/admin/users/${user.id}/stats`;
  });
  private readonly mutationError = signal<string | null>(null);

  users = computed(() =>
    this.userListResource.hasValue() ? this.userListResource.value().users : [],
  );
  total = computed(() =>
    this.userListResource.hasValue() ? this.userListResource.value().total : 0,
  );
  loading = computed(() => this.userListResource.isLoading());
  error = computed(
    () =>
      this.mutationError() ??
      (this.userListResource.error() ? 'Failed to load users.' : null) ??
      (this.selectedUploadsResource.error() ? 'Failed to load user uploads.' : null) ??
      (this.selectedLoginsResource.error() ? 'Failed to load user logins.' : null) ??
      (this.selectedStatsResource.error() ? 'Failed to load user stats.' : null),
  );
  editingUser = signal<AdminUser | null>(null);
  editTier = '';
  editIsAdmin = false;
  editIsBanned = false;
  selectedDetailsUser = signal<AdminUser | null>(null);
  selectedUploads = computed(() =>
    this.selectedUploadsResource.hasValue() ? this.selectedUploadsResource.value().files : [],
  );
  uploadsLoading = computed(
    () => Boolean(this.selectedDetailsUser()) && this.selectedUploadsResource.isLoading(),
  );
  selectedLogins = computed(() =>
    this.selectedLoginsResource.hasValue() ? this.selectedLoginsResource.value().logins : [],
  );
  loginsLoading = computed(
    () => Boolean(this.selectedDetailsUser()) && this.selectedLoginsResource.isLoading(),
  );
  selectedStats = computed(() =>
    this.selectedStatsResource.hasValue() ? this.selectedStatsResource.value() : null,
  );
  statsLoading = computed(
    () => Boolean(this.selectedDetailsUser()) && this.selectedStatsResource.isLoading(),
  );

  onSearch(): void {
    this.page.set(1);
    this.appliedSearch.set(this.search.trim());
    this.mutationError.set(null);
  }

  nextPage(): void {
    if (this.page() * this.perPage < this.total()) {
      this.page.update((p) => p + 1);
    }
  }

  prevPage(): void {
    if (this.page() > 1) {
      this.page.update((p) => p - 1);
    }
  }

  startEdit(user: AdminUser): void {
    this.editingUser.set(user);
    this.editTier = user.tier;
    this.editIsAdmin = user.is_admin ?? false;
    this.editIsBanned = user.is_banned ?? false;
  }

  cancelEdit(): void {
    this.editingUser.set(null);
  }

  saveEdit(): void {
    const user = this.editingUser();
    if (!user) {
      return;
    }

    this.adminService
      .updateUser(user.id, {
        is_admin: this.editIsAdmin,
        is_banned: this.editIsBanned,
        tier: this.editTier,
      })
      .subscribe({
        error: (err) => {
          this.mutationError.set(getErrorDetail(err, 'Failed to update user.'));
        },
        next: (updated) => {
          this.userListResource.update((response) =>
            response
              ? {
                  ...response,
                  users: response.users.map((listedUser) =>
                    listedUser.id === updated.id ? updated : listedUser,
                  ),
                }
              : response,
          );
          this.selectedDetailsUser.update((current) =>
            current && current.id === updated.id ? updated : current,
          );
          this.editingUser.set(null);
        },
      });
  }

  deleteUser(user: AdminUser): void {
    this.confirmDialog.confirm(
      {
        confirmLabel: 'Delete user',
        message: `${user.email} will be deleted permanently. This action cannot be undone.`,
        title: 'Delete this user?',
        tone: 'danger',
      },
      () => {
        this.adminService.deleteUser(user.id).subscribe({
          error: (err) => {
            this.mutationError.set(getErrorDetail(err, 'Failed to delete user.'));
          },
          next: () => {
            if (this.selectedDetailsUser()?.id === user.id) {
              this.clearDetails();
            }
            this.userListResource.update((response) =>
              response
                ? {
                    ...response,
                    total: Math.max(0, response.total - 1),
                    users: response.users.filter((existingUser) => existingUser.id !== user.id),
                  }
                : response,
            );
          },
        });
      },
    );
  }

  totalPages(): number {
    return Math.ceil(this.total() / this.perPage);
  }

  private clearDetails(): void {
    this.selectedDetailsUser.set(null);
  }

  toggleDetails(user: AdminUser): void {
    if (this.selectedDetailsUser()?.id === user.id) {
      this.clearDetails();
      return;
    }

    this.selectedDetailsUser.set(user);
    this.mutationError.set(null);
  }

  transferGroups(): AdminTransferGroup[] {
    const groups = new Map<string, FileUploadResponse[]>();
    for (const file of this.selectedUploads()) {
      const groupKey = file.upload_group ?? `single-${file.id}`;
      const existing = groups.get(groupKey) ?? [];
      existing.push(file);
      groups.set(groupKey, existing);
    }

    const transferGroups: AdminTransferGroup[] = [...groups.entries()].map(
      ([uploadGroup, files]) => ({
        files,
        latestExpiry: files.reduce(
          (latest, file) =>
            getApiDateTime(file.expires_at) > getApiDateTime(latest) ? file.expires_at : latest,
          files[0].expires_at,
        ),
        totalSize: files.reduce((sum, file) => sum + file.file_size_bytes, 0),
        uploadGroup,
      }),
    );

    return this.sortTransferGroupsByLatestExpiry(transferGroups);
  }

  private sortTransferGroupsByLatestExpiry(
    transferGroups: AdminTransferGroup[],
  ): AdminTransferGroup[] {
    const sortedTransferGroups: AdminTransferGroup[] = [];
    for (const transferGroup of transferGroups) {
      const insertIndex = sortedTransferGroups.findIndex(
        (existingTransferGroup) =>
          getApiDateTime(transferGroup.latestExpiry) >
          getApiDateTime(existingTransferGroup.latestExpiry),
      );
      if (insertIndex === -1) {
        sortedTransferGroups.push(transferGroup);
      } else {
        sortedTransferGroups.splice(insertIndex, 0, transferGroup);
      }
    }
    return sortedTransferGroups;
  }

  deleteTransfer(group: AdminTransferGroup): void {
    const user = this.selectedDetailsUser();
    if (!user) {
      return;
    }

    this.confirmDialog.confirm(
      {
        confirmLabel: 'Delete transfer',
        message: `This will deactivate ${group.files.length} ${group.files.length === 1 ? 'file' : 'files'} for ${user.email}.`,
        title: 'Delete this transfer?',
        tone: 'danger',
      },
      () => {
        this.adminService.deleteUserTransfer(user.id, group.uploadGroup).subscribe({
          error: (err) => {
            this.mutationError.set(getErrorDetail(err, 'Failed to delete transfer.'));
          },
          next: () => {
            this.selectedUploadsResource.update((response) =>
              response
                ? {
                    ...response,
                    files: response.files.filter((file) => file.upload_group !== group.uploadGroup),
                  }
                : response,
            );
            this.selectedStatsResource.reload();
          },
        });
      },
    );
  }

  formatSize(bytes: number): string {
    return formatFileSize(bytes);
  }

  loginMethodLabel(authMethod: string): string {
    switch (authMethod) {
      case 'dev_login': {
        return 'Dev login';
      }
      case 'verification_code': {
        return 'Verification code';
      }
      default: {
        return authMethod;
      }
    }
  }
}
