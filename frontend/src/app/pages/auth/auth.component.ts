import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';

@Component({
  imports: [FormsModule],
  selector: 'app-auth',
  styleUrl: './auth.component.scss',
  templateUrl: './auth.component.html',
})
export class AuthComponent {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  readonly isRegister = this.route.snapshot.queryParamMap.get('mode') === 'register';

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

  signInMethod = signal<'code' | 'password'>('code');
  step = signal<'email' | 'code' | 'password'>('email');
  email = this.route.snapshot.queryParamMap.get('email') ?? '';
  code = '';
  password = '';
  loading = signal(false);
  error = signal<string | null>(null);
  message = signal<string | null>(null);

  private static readonly EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

  requestCode(): void {
    if (!this.email) {
      return;
    }
    if (!AuthComponent.EMAIL_PATTERN.test(this.email)) {
      this.error.set('Please enter a valid email address.');
      return;
    }
    this.loading.set(true);
    this.error.set(null);

    this.authService.requestCode(this.email).subscribe({
      error: (err) => {
        this.error.set(this.getErrorDetail(err, 'Failed to send code.'));
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
        this.error.set(this.getErrorDetail(err, 'Invalid email or password.'));
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
    this.loading.set(true);
    this.error.set(null);

    this.authService.verifyCode(this.email, this.code, this.isRegister).subscribe({
      error: (err) => {
        this.message.set(null);
        this.error.set(this.getErrorDetail(err, 'Invalid code.'));
        this.loading.set(false);
      },
      next: () => {
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
}
