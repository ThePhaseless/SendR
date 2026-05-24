import { ChangeDetectionStrategy, Component, effect, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { AuthService } from '../../services/auth.service';
import { getErrorDetail } from '../../utils/error.utils';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule],
  selector: 'app-auth',
  standalone: true,
  styleUrl: './auth.component.scss',
  templateUrl: './auth.component.html',
})
export class AuthComponent {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly queryParamMap = toSignal(this.route.queryParamMap, {
    initialValue: this.route.snapshot.queryParamMap,
  });

  readonly isRegister = signal(this.route.snapshot.queryParamMap.get('mode') === 'register');

  signInMethod = signal<'code' | 'password'>('code');
  step = signal<'email' | 'code' | 'password'>('email');
  email = this.route.snapshot.queryParamMap.get('email') ?? '';
  code = '';
  password = '';
  confirmPassword = '';
  loading = signal(false);
  error = signal<string | null>(null);
  message = signal<string | null>(null);

  private static readonly EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

  constructor() {
    effect(() => {
      const queryParams = this.queryParamMap();
      const nextIsRegister = queryParams.get('mode') === 'register';
      const previousIsRegister = this.isRegister();

      this.isRegister.set(nextIsRegister);

      const nextEmail = queryParams.get('email');
      if (nextEmail !== null) {
        this.email = nextEmail;
      }

      if (nextIsRegister !== previousIsRegister) {
        this.resetFlow();
      }
    });
  }

  async requestCode(): Promise<void> {
    if (!this.email) {
      return;
    }
    if (!AuthComponent.EMAIL_PATTERN.test(this.email)) {
      this.error.set('Please enter a valid email address.');
      return;
    }

    const passwordError = this.getRegistrationPasswordError();
    if (passwordError) {
      this.error.set(passwordError);
      return;
    }

    this.loading.set(true);
    this.error.set(null);
    this.message.set(null);

    try {
      const res = await firstValueFrom(this.authService.requestCode(this.email));
      this.message.set(res['message'] ?? 'Verification code sent');
      this.step.set('code');
    } catch (error) {
      this.error.set(getErrorDetail(error, 'Failed to send code.'));
    } finally {
      this.loading.set(false);
    }
  }

  async loginWithPassword(): Promise<void> {
    if (!this.email || !this.password) {
      return;
    }
    if (!AuthComponent.EMAIL_PATTERN.test(this.email)) {
      this.error.set('Please enter a valid email address.');
      return;
    }

    this.loading.set(true);
    this.error.set(null);
    this.message.set(null);

    try {
      await firstValueFrom(this.authService.loginWithPassword(this.email, this.password));
      await this.router.navigate(['/']);
    } catch (error) {
      this.error.set(getErrorDetail(error, 'Invalid email or password.'));
      this.loading.set(false);
    }
  }

  async verifyCode(): Promise<void> {
    if (!this.code) {
      return;
    }

    const passwordError = this.getRegistrationPasswordError();
    if (passwordError) {
      this.error.set(passwordError);
      return;
    }

    this.loading.set(true);
    this.error.set(null);
    this.message.set(null);

    try {
      await firstValueFrom(this.authService.verifyCode(this.email, this.code, this.isRegister()));

      if (this.isRegister() && this.password) {
        this.authService.syncSession();
        await new Promise((resolve) => {
          setTimeout(resolve, 500);
        });
        const me = this.authService.currentUser();
        if (me && !me.has_password) {
          await firstValueFrom(this.authService.setPassword(this.password));
        }
      }

      this.loading.set(false);
      await this.router.navigate(['/']);
    } catch (error) {
      this.error.set(getErrorDetail(error, 'Invalid code.'));
      this.loading.set(false);
    }
  }

  backToEmail(): void {
    this.step.set('email');
    this.code = '';
    this.error.set(null);
    this.message.set(null);
  }

  setMethod(method: 'code' | 'password'): void {
    this.signInMethod.set(method);
    this.step.set(method === 'password' ? 'password' : 'email');
    this.password = '';
    this.code = '';
    this.error.set(null);
    this.message.set(null);
  }

  private getRegistrationPasswordError(): string | null {
    if (!this.isRegister()) {
      return null;
    }
    if (!this.password) {
      return 'Enter a password.';
    }
    if (this.password.length < 8) {
      return 'Password must be at least 8 characters long.';
    }
    if (this.password.length > 128) {
      return 'Password must be 128 characters or fewer.';
    }
    if (!this.confirmPassword) {
      return 'Confirm your password.';
    }
    if (this.password !== this.confirmPassword) {
      return 'Password and confirmation do not match.';
    }
    return null;
  }

  private resetFlow(): void {
    this.signInMethod.set('code');
    this.step.set('email');
    this.code = '';
    this.password = '';
    this.confirmPassword = '';
    this.loading.set(false);
    this.error.set(null);
    this.message.set(null);
  }
}
