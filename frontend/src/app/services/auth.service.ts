import { HttpClient, httpResource } from '@angular/common/http';
import { Injectable, effect, inject, signal } from '@angular/core';
import type { Observable } from 'rxjs';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';
import { AuthService as ApiAuthService } from '../api/endpoints/auth/auth.service';
import { SubscriptionService as ApiSubscriptionService } from '../api/endpoints/subscription/subscription.service';
import type { SessionResponse, SubscriptionResponse, UserResponse } from '../api/model';

export type VerifyCodeResponse = SessionResponse;
export type MeResponse = UserResponse;

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly api = inject(ApiAuthService);
  private readonly subscriptionApi = inject(ApiSubscriptionService);
  private readonly apiUrl = environment.apiUrl;

  private readonly sessionResource = httpResource<MeResponse>(() => `${this.apiUrl}/api/auth/me`);

  readonly authenticated = signal(false);
  readonly currentUser = signal<MeResponse | null>(null);

  constructor() {
    effect(() => {
      if (this.sessionResource.hasValue()) {
        this.currentUser.set(this.sessionResource.value());
        this.authenticated.set(true);
        return;
      }

      if (this.sessionResource.error()) {
        this.currentUser.set(null);
        this.authenticated.set(false);
      }
    });
  }

  requestCode(email: string): Observable<Record<string, string>> {
    return this.api.requestCodeApiAuthRequestCodePost({ email });
  }

  loginWithPassword(email: string, password: string): Observable<VerifyCodeResponse> {
    return this.api.loginPasswordApiAuthLoginPasswordPost({ email, password });
  }

  verifyCode(email: string, code: string, createAccount = false): Observable<VerifyCodeResponse> {
    return this.api.verifyCodeApiAuthVerifyCodePost({
      code,
      create_account: createAccount,
      email,
    });
  }

  setPassword(password: string): Observable<MeResponse> {
    return this.api.setPasswordApiAuthSetPasswordPost({ password });
  }

  changePassword(currentPassword: string, newPassword: string): Observable<MeResponse> {
    return this.api.changePasswordApiAuthChangePasswordPost({
      current_password: currentPassword,
      new_password: newPassword,
    });
  }

  upgradeToPremium(): Observable<SubscriptionResponse> {
    return this.subscriptionApi.upgradeToPremiumApiSubscriptionUpgradePost();
  }

  cancelSubscription(): Observable<SubscriptionResponse> {
    return this.subscriptionApi.cancelSubscriptionApiSubscriptionCancelPost();
  }

  isAuthenticated(): boolean {
    return this.authenticated();
  }

  async devLogin(role: 'admin' | 'user' | 'premium'): Promise<VerifyCodeResponse> {
    const data = await firstValueFrom(
      this.http.post<VerifyCodeResponse>(`${this.apiUrl}/api/dev/login/${role}`, {}),
    );
    this.authenticated.set(true);
    this.syncSession();
    return data;
  }

  syncSession(): void {
    this.sessionResource.reload();
  }

  async logout(): Promise<void> {
    this.currentUser.set(null);
    this.authenticated.set(false);
    try {
      await firstValueFrom(this.http.post<never>(`${this.apiUrl}/api/auth/logout`, {}));
    } catch {
      // Ignore logout errors
    }
  }
}
