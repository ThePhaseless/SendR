import { Component, computed, inject, isDevMode, signal } from "@angular/core";
import { Router, RouterLink } from "@angular/router";
import { AuthService } from "../../services/auth.service";
import type { MeResponse } from "../../services/auth.service";
import { toSignal } from "@angular/core/rxjs-interop";

@Component({
  imports: [RouterLink],
  selector: "app-header",
  styleUrl: "./header.component.scss",
  templateUrl: "./header.component.html",
})
export class HeaderComponent {
  private readonly router = inject(Router);
  readonly auth = inject(AuthService);

  readonly isDevMode = isDevMode();

  private readonly me = this.auth.isAuthenticated()
    ? toSignal(this.auth.getMe(), { initialValue: null })
    : signal<MeResponse | null>(null);

  isAdmin = computed(() => this.me()?.is_admin ?? false);

  logout(): void {
    this.auth.logout();
    void this.router.navigate(["/"]);
  }

  devLogin(role: "admin" | "user" | "premium"): void {
    this.auth.devLogin(role).subscribe({
      next: () => {
        window.location.reload();
      },
    });
  }
}
