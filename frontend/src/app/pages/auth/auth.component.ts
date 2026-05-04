import { ChangeDetectionStrategy, Component, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { of, switchMap } from 'rxjs';
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

  requestCode(): void {
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

    this.authService.requestCode(this.email).subscribe({
      error: (err) => {
        this.error.set(getErrorDetail(err, 'Failed to send code.'));
        this.loading.set(false);
      },
      next: (res) => {
        this.message.set(res['message'] ?? 'Verification code sent');
        this.step.set('code');
        this.loading.set(false);
      },
    });
  }

  loginWithPassword(): void {
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

    this.authService.loginWithPassword(this.email, this.password).subscribe({
      error: (err) => {
        this.error.set(getErrorDetail(err, 'Invalid email or password.'));
        this.loading.set(false);
      },
      next: () => {
        void this.router.navigate(['/']);
      },
    });
  }

  verifyCode(): void {
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

    this.authService
      .verifyCode(this.email, this.code, this.isRegister())
      .pipe(switchMap(() => this.completeRegistrationWithPassword()))
      .subscribe({
        error: (err) => {
          this.error.set(getErrorDetail(err, 'Invalid code.'));
          this.loading.set(false);
        },
        next: () => {
          this.loading.set(false);
          void this.router.navigate(['/']);
        },
      });
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

  private completeRegistrationWithPassword() {
    if (!this.isRegister() || !this.password) {
      return of(null);
    }

    return this.authService
      .getMe()
      .pipe(
        switchMap((me) => (me.has_password ? of(me) : this.authService.setPassword(this.password))),
      );
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
