import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { OnInit } from '@angular/core';
import type { AdminUserLoginEntry, AdminUserStatsResponse } from '../../api/model';
import { AdminService } from '../../services/admin.service';
import type { AdminUser } from '../../services/admin.service';
import type { FileUploadResponse } from '../../services/file.service';
import { formatFileSize } from '../../utils/file.utils';

interface AdminTransferGroup {
  uploadGroup: string;
  files: FileUploadResponse[];
  totalSize: number;
  latestExpiry: string;
}

@Component({
  imports: [DatePipe, FormsModule],
  selector: 'app-admin',
  styleUrl: './admin.component.scss',
  templateUrl: './admin.component.html',
})
export class AdminComponent implements OnInit {
  private readonly adminService = inject(AdminService);

  users = signal<AdminUser[]>([]);
  total = signal(0);
  page = signal(1);
  perPage = 20;
  search = '';
  loading = signal(true);
  error = signal<string | null>(null);
  editingUser = signal<AdminUser | null>(null);
  editTier = '';
  editIsAdmin = false;
  editIsBanned = false;
  selectedDetailsUser = signal<AdminUser | null>(null);
  selectedUploads = signal<FileUploadResponse[]>([]);
  uploadsLoading = signal(false);
  selectedLogins = signal<AdminUserLoginEntry[]>([]);
  loginsLoading = signal(false);
  selectedStats = signal<AdminUserStatsResponse | null>(null);
  statsLoading = signal(false);

  ngOnInit(): void {
    this.loadUsers();
  }

  loadUsers(): void {
    this.loading.set(true);
    this.error.set(null);
    this.adminService.listUsers(this.page(), this.perPage, this.search).subscribe({
      error: () => {
        this.error.set('Failed to load users.');
        this.loading.set(false);
      },
      next: (res) => {
        this.users.set(res.users);
        this.total.set(res.total);
        this.loading.set(false);
      },
    });
  }

  onSearch(): void {
    this.page.set(1);
    this.loadUsers();
  }

  nextPage(): void {
    if (this.page() * this.perPage < this.total()) {
      this.page.update((p) => p + 1);
      this.loadUsers();
    }
  }

  prevPage(): void {
    if (this.page() > 1) {
      this.page.update((p) => p - 1);
      this.loadUsers();
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

  private getErrorDetail(error: unknown, fallback: string): string {
    if (
      !(error instanceof HttpErrorResponse) ||
      typeof error.error !== 'object' ||
      error.error === null
    ) {
      return fallback;
    }

    const detail: unknown = Reflect.get(error.error, 'detail');
    if (typeof detail === 'string') {
      return detail;
    }

    return fallback;
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
          this.error.set(this.getErrorDetail(err, 'Failed to update user.'));
        },
        next: (updated) => {
          this.users.update((users) => users.map((u) => (u.id === updated.id ? updated : u)));
          this.selectedDetailsUser.update((current) =>
            current && current.id === updated.id ? updated : current,
          );
          this.editingUser.set(null);
        },
      });
  }

  deleteUser(user: AdminUser): void {
    if (!confirm(`Delete user ${user.email}? This cannot be undone.`)) {
      return;
    }

    this.adminService.deleteUser(user.id).subscribe({
      error: (err) => {
        this.error.set(this.getErrorDetail(err, 'Failed to delete user.'));
      },
      next: () => {
        if (this.selectedDetailsUser()?.id === user.id) {
          this.clearDetails();
        }
        this.users.update((users) => users.filter((u) => u.id !== user.id));
        this.total.update((t) => t - 1);
      },
    });
  }

  totalPages(): number {
    return Math.ceil(this.total() / this.perPage);
  }

  private clearDetails(): void {
    this.selectedDetailsUser.set(null);
    this.selectedUploads.set([]);
    this.selectedLogins.set([]);
    this.selectedStats.set(null);
    this.uploadsLoading.set(false);
    this.loginsLoading.set(false);
    this.statsLoading.set(false);
  }

  toggleDetails(user: AdminUser): void {
    if (this.selectedDetailsUser()?.id === user.id) {
      this.clearDetails();
      return;
    }

    this.selectedDetailsUser.set(user);
    this.selectedUploads.set([]);
    this.selectedLogins.set([]);
    this.selectedStats.set(null);
    this.uploadsLoading.set(true);
    this.loginsLoading.set(true);
    this.statsLoading.set(true);
    this.adminService.listUserUploads(user.id).subscribe({
      error: (err) => {
        this.error.set(this.getErrorDetail(err, 'Failed to load user uploads.'));
        this.uploadsLoading.set(false);
      },
      next: (res) => {
        this.selectedUploads.set(res.files);
        this.uploadsLoading.set(false);
      },
    });
    this.adminService.listUserLogins(user.id).subscribe({
      error: (err) => {
        this.error.set(this.getErrorDetail(err, 'Failed to load user logins.'));
        this.loginsLoading.set(false);
      },
      next: (res) => {
        this.selectedLogins.set(res.logins);
        this.loginsLoading.set(false);
      },
    });
    this.adminService.getUserStats(user.id).subscribe({
      error: (err) => {
        this.error.set(this.getErrorDetail(err, 'Failed to load user stats.'));
        this.statsLoading.set(false);
      },
      next: (stats) => {
        this.selectedStats.set(stats);
        this.statsLoading.set(false);
      },
    });
  }

  transferGroups(): AdminTransferGroup[] {
    const groups = new Map<string, FileUploadResponse[]>();
    for (const file of this.selectedUploads()) {
      const groupKey = file.upload_group ?? `single-${file.id}`;
      const existing = groups.get(groupKey) ?? [];
      existing.push(file);
      groups.set(groupKey, existing);
    }

    return [...groups.entries()]
      .map(([uploadGroup, files]) => ({
        files,
        latestExpiry: files.reduce(
          (latest, file) =>
            new Date(file.expires_at) > new Date(latest) ? file.expires_at : latest,
          files[0].expires_at,
        ),
        totalSize: files.reduce((sum, file) => sum + file.file_size_bytes, 0),
        uploadGroup,
      }))
      .sort((a, b) => new Date(b.latestExpiry).getTime() - new Date(a.latestExpiry).getTime());
  }

  deleteTransfer(group: AdminTransferGroup): void {
    const user = this.selectedDetailsUser();
    if (!user) {
      return;
    }
    if (
      !confirm(
        `Delete transfer ${group.uploadGroup}? This will deactivate ${group.files.length} file(s).`,
      )
    ) {
      return;
    }

    this.adminService.deleteUserTransfer(user.id, group.uploadGroup).subscribe({
      error: (err) => {
        this.error.set(this.getErrorDetail(err, 'Failed to delete transfer.'));
      },
      next: () => {
        this.selectedUploads.update((files) =>
          files.filter((file) => file.upload_group !== group.uploadGroup),
        );
        this.adminService.getUserStats(user.id).subscribe({
          error: (err) => {
            this.error.set(this.getErrorDetail(err, 'Failed to refresh user stats.'));
          },
          next: (stats) => {
            this.selectedStats.set(stats);
          },
        });
      },
    });
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
