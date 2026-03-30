import { HttpErrorResponse } from "@angular/common/http";
import { Component, inject, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import type { OnInit } from "@angular/core";
import { AdminService } from "../../services/admin.service";
import type { AdminUser } from "../../services/admin.service";

@Component({
  imports: [FormsModule],
  selector: "app-admin",
  styleUrl: "./admin.component.scss",
  templateUrl: "./admin.component.html",
})
export class AdminComponent implements OnInit {
  private readonly adminService = inject(AdminService);

  users = signal<AdminUser[]>([]);
  total = signal(0);
  page = signal(1);
  perPage = 20;
  search = "";
  loading = signal(true);
  error = signal<string | null>(null);
  editingUser = signal<AdminUser | null>(null);
  editTier = "";
  editIsAdmin = false;

  ngOnInit(): void {
    this.loadUsers();
  }

  loadUsers(): void {
    this.loading.set(true);
    this.error.set(null);
    this.adminService.listUsers(this.page(), this.perPage, this.search).subscribe({
      error: () => {
        this.error.set("Failed to load users.");
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
  }

  cancelEdit(): void {
    this.editingUser.set(null);
  }

  private getErrorDetail(error: unknown, fallback: string): string {
    if (
      !(error instanceof HttpErrorResponse) ||
      typeof error.error !== "object" ||
      error.error === null
    ) {
      return fallback;
    }

    const detail: unknown = Reflect.get(error.error, "detail");
    if (typeof detail === "string") {
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
        tier: this.editTier,
      })
      .subscribe({
        error: (err) => {
          this.error.set(this.getErrorDetail(err, "Failed to update user."));
        },
        next: (updated) => {
          this.users.update((users) => users.map((u) => (u.id === updated.id ? updated : u)));
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
        this.error.set(this.getErrorDetail(err, "Failed to delete user."));
      },
      next: () => {
        this.users.update((users) => users.filter((u) => u.id !== user.id));
        this.total.update((t) => t - 1);
      },
    });
  }

  totalPages(): number {
    return Math.ceil(this.total() / this.perPage);
  }
}
