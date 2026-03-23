import { HttpClient } from "@angular/common/http";
import { Injectable, inject, signal } from "@angular/core";
import type { Observable } from "rxjs";
import { map, tap } from "rxjs/operators";
import { environment } from "../../environments/environment";
import { AuthService as GeneratedAuthService } from "../api/api/auth.service";
import type {
  EmailVerificationRequest,
  QuotaResponse,
  TokenResponse,
  UserResponse,
} from "../api/model/models";

export interface RequestCodeResponse {
  message: string;
}

export type VerifyCodeResponse = TokenResponse;
export type MeResponse = UserResponse;

export interface LimitsResponse {
  max_file_size_mb: number;
  max_files_per_upload: number;
}

const TOKEN_KEY = "sendr_token";
const EXPIRES_KEY = "sendr_token_expires";

@Injectable({
  providedIn: "root",
})
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly api = inject(GeneratedAuthService);
  private readonly apiUrl = environment.apiUrl;
  authenticated = signal(this.isAuthenticated());

  getLimits(): Observable<LimitsResponse> {
    return this.http.get<LimitsResponse>(`${this.apiUrl}/api/auth/limits`);
  }

  requestCode(email: string): Observable<RequestCodeResponse> {
    const payload: EmailVerificationRequest = { email };
    return this.api
      .requestCodeApiAuthRequestCodePost(payload)
      .pipe(map((response) => ({ message: response["message"] ?? "Verification code sent" })));
  }

  verifyCode(email: string, code: string): Observable<VerifyCodeResponse> {
    return this.api.verifyCodeApiAuthVerifyCodePost({ code, email }).pipe(
      tap((res) => {
        localStorage.setItem(TOKEN_KEY, res.token);
        localStorage.setItem(EXPIRES_KEY, res.expires_at);
        this.authenticated.set(true);
      }),
    );
  }

  getMe(): Observable<MeResponse> {
    return this.api.getMeApiAuthMeGet();
  }

  getQuota(): Observable<QuotaResponse> {
    return this.api.getQuotaApiAuthQuotaGet();
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

  devLogin(role: "admin" | "user"): Observable<VerifyCodeResponse> {
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
