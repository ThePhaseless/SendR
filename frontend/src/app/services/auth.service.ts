import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import type { Observable } from 'rxjs';
import { tap } from 'rxjs/operators';
import { environment } from '../../environments/environment';
import { AuthService as ApiAuthService } from '../api/endpoints/auth/auth.service';
import { SubscriptionService as ApiSubscriptionService } from '../api/endpoints/subscription/subscription.service';
import type {
  LimitsResponse,
  QuotaResponse,
  SubscriptionResponse,
  TokenResponse,
  UserResponse,
} from '../api/model';

export type VerifyCodeResponse = TokenResponse;
export type MeResponse = UserResponse;

const TOKEN_KEY = 'sendr_token';
const EXPIRES_KEY = 'sendr_token_expires';

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly api = inject(ApiAuthService);
  private readonly subscriptionApi = inject(ApiSubscriptionService);
  private readonly apiUrl = environment.apiUrl;
  authenticated = signal(this.isAuthenticated());

  requestCode(email: string): Observable<Record<string, string>> {
    return this.api.requestCodeApiAuthRequestCodePost({ email });
  }

  verifyCode(email: string, code: string, createAccount = false): Observable<VerifyCodeResponse> {
    return this.api
      .verifyCodeApiAuthVerifyCodePost({ code, create_account: createAccount, email })
      .pipe(
        tap((res) => {
          this.storeToken(res);
        }),
      );
  }

  getMe(): Observable<MeResponse> {
    return this.api.getMeApiAuthMeGet();
  }

  getQuota(): Observable<QuotaResponse> {
    return this.api.getQuotaApiAuthQuotaGet();
  }

  getLimits(): Observable<LimitsResponse> {
    return this.api.getLimitsApiAuthLimitsGet();
  }

  getSubscription(): Observable<SubscriptionResponse> {
    return this.subscriptionApi.getSubscriptionApiSubscriptionGet();
  }

  upgradeToPremium(): Observable<SubscriptionResponse> {
    return this.subscriptionApi.upgradeToPremiumApiSubscriptionUpgradePost();
  }

  cancelSubscription(): Observable<SubscriptionResponse> {
    return this.subscriptionApi.cancelSubscriptionApiSubscriptionCancelPost();
  }

  isAuthenticated(): boolean {
    const token = this.getToken();
    if (!token) {
      return false;
    }
    const expires = localStorage.getItem(EXPIRES_KEY);
    if (!expires) {
      return false;
    }
    return new Date(expires) > new Date();
  }

  getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  }

  devLogin(role: 'admin' | 'user' | 'premium'): Observable<VerifyCodeResponse> {
    return this.http.post<VerifyCodeResponse>(`${this.apiUrl}/api/dev/login/${role}`, {}).pipe(
      tap((res) => {
        this.storeToken(res);
      }),
    );
  }

  storeToken(res: VerifyCodeResponse): void {
    localStorage.setItem(TOKEN_KEY, res.token);
    localStorage.setItem(EXPIRES_KEY, res.expires_at);
    this.authenticated.set(true);
  }

  logout(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EXPIRES_KEY);
    this.authenticated.set(false);
  }
}
