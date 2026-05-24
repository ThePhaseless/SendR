import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuthService } from '../../services/auth.service';
import { UiNotificationService } from '../../services/ui-notification.service';
import { getErrorDetail } from '../../utils/error.utils';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink],
  selector: 'app-header',
  standalone: true,
  styleUrl: './header.component.scss',
  templateUrl: './header.component.html',
})
export class HeaderComponent {
  private readonly router = inject(Router);
  readonly auth = inject(AuthService);
  private readonly notifications = inject(UiNotificationService);

  readonly showDevTools = environment.enableDevTools;
  readonly menuOpen = signal(false);
  readonly currentUser = this.auth.currentUser;

  isAdmin = computed(() => this.currentUser()?.is_admin ?? false);

  constructor() {
    this.auth.syncSession();

    effect(() => {
      if (!this.auth.authenticated()) {
        this.closeMenu();
      }
    });
  }

  toggleMenu(): void {
    this.menuOpen.update((v) => !v);
  }

  closeMenu(): void {
    this.menuOpen.set(false);
  }

  logout(): void {
    void this.auth.logout();
    this.menuOpen.set(false);
    void this.router.navigate(['/']);
  }

  async devLogin(role: 'admin' | 'user' | 'premium'): Promise<void> {
    try {
      await this.auth.devLogin(role);
      this.closeMenu();
      await this.router.navigate(['/']);
    } catch (error) {
      const detail = getErrorDetail(
        error,
        'Dev login is only available when the backend runs locally with dev login enabled.',
      );
      this.notifications.error(
        'Dev login failed',
        detail === 'Not found'
          ? 'Dev login is only available when the backend runs locally with dev login enabled.'
          : detail,
        {
          dedupeKey: 'dev-login-failed',
        },
      );
    }
  }
}
