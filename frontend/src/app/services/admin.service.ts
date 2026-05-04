import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';
import { AdminService as ApiAdminService } from '../api/endpoints/admin/admin.service';
import type { AdminUserUpdateRequest, UserResponse } from '../api/model';

export type AdminUser = UserResponse;

@Injectable({
  providedIn: 'root',
})
export class AdminService {
  private readonly api = inject(ApiAdminService);

  updateUser(userId: number, update: AdminUserUpdateRequest): Observable<UserResponse> {
    return this.api.updateUserApiAdminUsersUserIdPatch(userId, update);
  }

  deleteUser(userId: number): Observable<Record<string, string>> {
    return this.api.deleteUserApiAdminUsersUserIdDelete(userId);
  }

  deleteUserTransfer(userId: number, uploadGroup: string): Observable<Record<string, string>> {
    return this.api.deleteUserTransferApiAdminUsersUserIdTransfersUploadGroupDelete(
      userId,
      uploadGroup,
    );
  }
}
