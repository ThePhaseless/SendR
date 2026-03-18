import { Component, computed, inject, isDevMode, signal } from "@angular/core";
import { toSignal } from "@angular/core/rxjs-interop";
import { Router, RouterLink } from "@angular/router";
import { AuthService } from "../../services/auth.service";

@Component({
  selector: "app-header",
  imports: [RouterLink],
  templateUrl: "./header.component.html",
  styleUrl: "./header.component.scss",
})
export class HeaderComponent {
  private readonly router = inject(Router);
  readonly auth = inject(AuthService);

  readonly isDevMode = isDevMode();

  private readonly me = this.auth.isAuthenticated()
    ? toSignal(this.auth.getMe())
    : signal(undefined);

  isAdmin = computed(() => this.me()?.is_admin ?? false);

  logout(): void {
    this.auth.logout();
    void this.router.navigate(["/"]);
  }

  devLogin(role: "admin" | "user"): void {
    this.auth.devLogin(role).subscribe({
      next: () => {
        window.location.reload();
      },
    });
  }
}
