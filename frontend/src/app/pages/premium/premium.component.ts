import { DatePipe } from '@angular/common';
import type { OnInit } from '@angular/core';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { SubscriptionResponse, UserResponse } from '../../api/model';
import { AuthService } from '../../services/auth.service';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, DatePipe],
  selector: 'app-premium',
  standalone: true,
  styleUrl: './premium.component.scss',
  templateUrl: './premium.component.html',
})
export class PremiumComponent implements OnInit {
  private readonly authService = inject(AuthService);

  user = signal<UserResponse | null>(null);
  subscription = signal<SubscriptionResponse | null>(null);
  loading = signal(true);
  error = signal<string | null>(null);
  processing = signal(false);
  readonly isAuthenticated = computed(() => this.authService.authenticated());

  ngOnInit(): void {
    this.authService.getMe().subscribe({
      error: () => {
        this.user.set(null);
        this.loading.set(false);
      },
      next: (me) => {
        this.user.set(me);
        this.loadSubscription();
      },
    });
  }

  private loadSubscription(): void {
    this.authService.getSubscription().subscribe({
      error: () => {
        this.loading.set(false);
      },
      next: (sub) => {
        this.subscription.set(sub);
        this.loading.set(false);
      },
    });
  }

  isPremium(): boolean {
    return this.user()?.tier === 'premium';
  }

  tierDisplayName(): string {
    const tier = this.user()?.tier;
    if (tier === 'temporary') {
      return 'Temporary';
    }
    if (tier === 'free') {
      return 'Free';
    }
    if (tier === 'premium') {
      return 'Premium';
    }
    return tier ?? 'Unknown';
  }

  upgrade(): void {
    this.processing.set(true);
    this.error.set(null);
    this.authService.upgradeToPremium().subscribe({
      error: () => {
        this.error.set('Failed to upgrade. Please try again.');
        this.processing.set(false);
      },
      next: (sub) => {
        this.subscription.set(sub);
        this.user.update((u) => (u ? { ...u, tier: 'premium' } : u));
        this.processing.set(false);
      },
    });
  }

  cancel(): void {
    this.processing.set(true);
    this.error.set(null);
    this.authService.cancelSubscription().subscribe({
      error: () => {
        this.error.set('Failed to cancel. Please try again.');
        this.processing.set(false);
      },
      next: (sub) => {
        this.subscription.set(sub);
        this.user.update((u) => (u ? { ...u, tier: 'free' } : u));
        this.processing.set(false);
      },
    });
  }
}
