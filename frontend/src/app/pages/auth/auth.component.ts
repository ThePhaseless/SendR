import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-auth',
  imports: [FormsModule],
  templateUrl: './auth.component.html',
  styleUrl: './auth.component.scss',
})
export class AuthComponent {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  step = signal<'email' | 'code'>('email');
  email = '';
  code = '';
  loading = signal(false);
  error = signal<string | null>(null);
  message = signal<string | null>(null);

  requestCode(): void {
    if (!this.email) return;
    this.loading.set(true);
    this.error.set(null);

    this.authService.requestCode(this.email).subscribe({
      next: (res) => {
        this.message.set(res.message);
        this.step.set('code');
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail ?? 'Failed to send code.');
        this.loading.set(false);
      },
    });
  }

  verifyCode(): void {
    if (!this.code) return;
    this.loading.set(true);
    this.error.set(null);

    this.authService.verifyCode(this.email, this.code).subscribe({
      next: () => {
        this.router.navigate(['/']);
      },
      error: (err) => {
        this.error.set(err.error?.detail ?? 'Invalid code.');
        this.loading.set(false);
      },
    });
  }

  backToEmail(): void {
    this.step.set('email');
    this.code = '';
    this.error.set(null);
    this.message.set(null);
  }
}
