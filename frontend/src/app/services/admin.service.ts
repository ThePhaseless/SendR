import { Injectable, inject } from "@angular/core";
import type { Observable } from "rxjs";
import { AdminService as ApiAdminService } from "../api/endpoints/admin/admin.service";
import type { AdminUserListResponse, AdminUserUpdateRequest, UserResponse } from "../api/model";

export type AdminUser = UserResponse;

@Injectable({
  providedIn: "root",
})
export class AdminService {
  private readonly api = inject(ApiAdminService);

  listUsers(page = 1, perPage = 20, search = ""): Observable<AdminUserListResponse> {
    return this.api.listUsersApiAdminUsersGet({
      page,
      per_page: perPage,
      search: search || undefined,
    });
  }

  updateUser(userId: number, update: AdminUserUpdateRequest): Observable<UserResponse> {
    return this.api.updateUserApiAdminUsersUserIdPatch(userId, update);
  }

  deleteUser(userId: number): Observable<Record<string, string>> {
    return this.api.deleteUserApiAdminUsersUserIdDelete(userId);
  }
}
