import { Component, inject, signal } from "@angular/core";
import type { OnInit } from "@angular/core";
import { RouterLink } from "@angular/router";
import { DatePipe } from "@angular/common";
import { AuthService } from "../../services/auth.service";
import type { UserResponse } from "../../api/model/models";
import type { SubscriptionResponse } from "../../api/model/subscription-response";

@Component({
  imports: [RouterLink, DatePipe],
  selector: "app-premium",
  styleUrl: "./premium.component.scss",
  templateUrl: "./premium.component.html",
})
export class PremiumComponent implements OnInit {
  private readonly authService = inject(AuthService);

  user = signal<UserResponse | null>(null);
  subscription = signal<SubscriptionResponse | null>(null);
  loading = signal(true);
  error = signal<string | null>(null);
  processing = signal(false);

  ngOnInit(): void {
    this.authService.getMe().subscribe({
      error: () => {
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
    return this.user()?.tier === "premium";
  }

  upgrade(): void {
    this.processing.set(true);
    this.error.set(null);
    this.authService.upgradeToPremium().subscribe({
      error: () => {
        this.error.set("Failed to upgrade. Please try again.");
        this.processing.set(false);
      },
      next: (sub) => {
        this.subscription.set(sub);
        this.user.update((u) => (u ? { ...u, tier: "premium" } : u));
        this.processing.set(false);
      },
    });
  }

  cancel(): void {
    this.processing.set(true);
    this.error.set(null);
    this.authService.cancelSubscription().subscribe({
      error: () => {
        this.error.set("Failed to cancel. Please try again.");
        this.processing.set(false);
      },
      next: (sub) => {
        this.subscription.set(sub);
        this.user.update((u) => (u ? { ...u, tier: "free" } : u));
        this.processing.set(false);
      },
    });
  }
}
