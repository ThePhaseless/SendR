import { Component, computed, inject, signal } from "@angular/core";
import { Router, RouterLink } from "@angular/router";
import { environment } from "../../../environments/environment";
import { getMeApiAuthMeGetResource } from "../../api/endpoints/filename.resource";
import { AuthService } from "../../services/auth.service";

@Component({
  imports: [RouterLink],
  selector: "app-header",
  styleUrl: "./header.component.scss",
  templateUrl: "./header.component.html",
})
export class HeaderComponent {
  private readonly router = inject(Router);
  readonly auth = inject(AuthService);

  readonly showDevTools = environment.enableDevTools;
  readonly menuOpen = signal(false);

  private readonly me = this.auth.isAuthenticated() ? getMeApiAuthMeGetResource() : undefined;

  isAdmin = computed(() => this.me?.value()?.is_admin ?? false);

  toggleMenu(): void {
    this.menuOpen.update((v) => !v);
  }

  closeMenu(): void {
    this.menuOpen.set(false);
  }

  logout(): void {
    this.auth.logout();
    this.menuOpen.set(false);
    void this.router.navigate(["/"]);
  }

  devLogin(role: "admin" | "user" | "premium"): void {
    this.auth.devLogin(role).subscribe({
      error: () => {
        alert(`Dev login failed. Is SENDR_DEV_MODE=true on the backend?`);
      },
      next: () => {
        window.location.reload();
      },
    });
  }
}
