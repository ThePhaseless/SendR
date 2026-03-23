import { HttpClient } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import type { Observable } from "rxjs";
import { environment } from "../../environments/environment";

export interface AdminUser {
  id: number;
  email: string;
  tier: string;
  is_admin: boolean;
}

export interface AdminUserListResponse {
  users: AdminUser[];
  total: number;
}

export interface AdminUserUpdate {
  tier?: string;
  is_admin?: boolean;
}

@Injectable({
  providedIn: "root",
})
export class AdminService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  listUsers(page = 1, perPage = 20, search = ""): Observable<AdminUserListResponse> {
    const params: Record<string, string> = {
      page: page.toString(),
      per_page: perPage.toString(),
    };
    if (search) {
      params["search"] = search;
    }
    return this.http.get<AdminUserListResponse>(`${this.apiUrl}/api/admin/users`, { params });
  }

  updateUser(userId: number, update: AdminUserUpdate): Observable<AdminUser> {
    return this.http.patch<AdminUser>(`${this.apiUrl}/api/admin/users/${userId}`, update);
  }

  deleteUser(userId: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiUrl}/api/admin/users/${userId}`);
  }
}
