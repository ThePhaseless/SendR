import { DatePipe } from '@angular/common';
import { httpResource } from '@angular/common/http';
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
export class PremiumComponent {
  private readonly authService = inject(AuthService);

  private readonly userResource = httpResource<UserResponse>(() => '/api/auth/me');
  private readonly subscriptionResource = httpResource<SubscriptionResponse>(() =>
    this.userResource.hasValue() ? '/api/subscription' : undefined,
  );
  private readonly mutationError = signal<string | null>(null);

  user = computed(() => (this.userResource.hasValue() ? this.userResource.value() : null));
  subscription = computed(() =>
    this.subscriptionResource.hasValue() ? this.subscriptionResource.value() : null,
  );
  loading = computed(() => this.userResource.isLoading() || this.subscriptionResource.isLoading());
  error = computed(
    () =>
      this.mutationError() ??
      (this.subscriptionResource.error() ? 'Failed to load subscription info.' : null),
  );
  processing = signal(false);
  readonly isAuthenticated = computed(() => this.userResource.hasValue());

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
    this.mutationError.set(null);
    this.authService.upgradeToPremium().subscribe({
      error: () => {
        this.mutationError.set('Failed to upgrade. Please try again.');
        this.processing.set(false);
      },
      next: (sub) => {
        this.subscriptionResource.set(sub);
        this.userResource.update((user) => (user ? { ...user, tier: 'premium' } : user));
        this.authService.currentUser.update((user) => (user ? { ...user, tier: 'premium' } : user));
        this.processing.set(false);
      },
    });
  }

  cancel(): void {
    this.processing.set(true);
    this.mutationError.set(null);
    this.authService.cancelSubscription().subscribe({
      error: () => {
        this.mutationError.set('Failed to cancel. Please try again.');
        this.processing.set(false);
      },
      next: (sub) => {
        this.subscriptionResource.set(sub);
        this.userResource.update((user) => (user ? { ...user, tier: 'free' } : user));
        this.authService.currentUser.update((user) => (user ? { ...user, tier: 'free' } : user));
        this.processing.set(false);
      },
    });
  }
}
