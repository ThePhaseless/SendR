import { HttpClient } from "@angular/common/http";
import { inject, Injectable, signal } from "@angular/core";
import { Observable } from "rxjs";
import { tap } from "rxjs/operators";

interface RequestCodeResponse {
  message: string;
}

interface VerifyCodeResponse {
  token: string;
  expires_at: string;
}

interface MeResponse {
  id: number;
  email: string;
  tier: string;
  is_admin: boolean;
}

interface QuotaResponse {
  files_used: number;
  files_limit: number;
  max_file_size_mb: number;
}

interface LimitsResponse {
  max_file_size_mb: number;
  max_files_per_week: number;
  max_files_per_upload: number;
}

const TOKEN_KEY = "sendr_token";
const EXPIRES_KEY = "sendr_token_expires";

@Injectable({
  providedIn: "root",
})
export class AuthService {
  private readonly http = inject(HttpClient);
  authenticated = signal(this.isAuthenticated());

  getLimits(): Observable<LimitsResponse> {
    return this.http.get<LimitsResponse>("/api/auth/limits");
  }

  requestCode(email: string): Observable<RequestCodeResponse> {
    return this.http.post<RequestCodeResponse>("/api/auth/request-code", {
      email,
    });
  }

  verifyCode(email: string, code: string): Observable<VerifyCodeResponse> {
    return this.http.post<VerifyCodeResponse>("/api/auth/verify-code", { email, code }).pipe(
      tap((res) => {
        localStorage.setItem(TOKEN_KEY, res.token);
        localStorage.setItem(EXPIRES_KEY, res.expires_at);
        this.authenticated.set(true);
      }),
    );
  }

  getMe(): Observable<MeResponse> {
    return this.http.get<MeResponse>("/api/auth/me");
  }

  getQuota(): Observable<QuotaResponse> {
    return this.http.get<QuotaResponse>("/api/auth/quota");
  }

  isAuthenticated(): boolean {
    const token = this.getToken();
    if (!token) return false;
    const expires = localStorage.getItem(EXPIRES_KEY);
    if (!expires) return false;
    return new Date(expires) > new Date();
  }

  getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  }

  devLogin(role: "admin" | "user"): Observable<VerifyCodeResponse> {
    return this.http.post<VerifyCodeResponse>(`/api/dev/login/${role}`, {}).pipe(
      tap((res) => {
        localStorage.setItem(TOKEN_KEY, res.token);
        localStorage.setItem(EXPIRES_KEY, res.expires_at);
        this.authenticated.set(true);
      }),
    );
  }

  logout(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EXPIRES_KEY);
    this.authenticated.set(false);
  }
}
