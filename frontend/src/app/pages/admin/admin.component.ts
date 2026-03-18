import { Component, inject, OnInit, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { AdminService, AdminUser } from "../../services/admin.service";

@Component({
  selector: "app-admin",
  imports: [FormsModule],
  templateUrl: "./admin.component.html",
  styleUrl: "./admin.component.scss",
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
      next: (res) => {
        this.users.set(res.users);
        this.total.set(res.total);
        this.loading.set(false);
      },
      error: () => {
        this.error.set("Failed to load users.");
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
    this.editIsAdmin = user.is_admin;
  }

  cancelEdit(): void {
    this.editingUser.set(null);
  }

  saveEdit(): void {
    const user = this.editingUser();
    if (!user) return;

    this.adminService
      .updateUser(user.id, {
        tier: this.editTier,
        is_admin: this.editIsAdmin,
      })
      .subscribe({
        next: (updated) => {
          this.users.update((users) => users.map((u) => (u.id === updated.id ? updated : u)));
          this.editingUser.set(null);
        },
        error: (err) => {
          this.error.set(err.error?.detail ?? "Failed to update user.");
        },
      });
  }

  deleteUser(user: AdminUser): void {
    if (!confirm(`Delete user ${user.email}? This cannot be undone.`)) return;

    this.adminService.deleteUser(user.id).subscribe({
      next: () => {
        this.users.update((users) => users.filter((u) => u.id !== user.id));
        this.total.update((t) => t - 1);
      },
      error: (err) => {
        this.error.set(err.error?.detail ?? "Failed to delete user.");
      },
    });
  }

  totalPages(): number {
    return Math.ceil(this.total() / this.perPage);
  }
}
