import type { HttpEvent } from "@angular/common/http";
import { HttpClient } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import type { Observable } from "rxjs";
import { environment } from "../../environments/environment";
import { FilesService as ApiFilesService } from "../api/endpoints/files/files.service";
import type {
  FileEditRequest,
  FileListResponse,
  FileUploadResponse,
  GroupEditRequest,
  GroupRefreshRequest,
  MultiFileUploadResponse,
  UploadGroupInfoResponse,
} from "../api/model";

export type {
  FileEditRequest,
  FileUploadResponse,
  GroupEditRequest,
  GroupRefreshRequest,
  MultiFileUploadResponse,
  UploadGroupInfoResponse,
};

@Injectable({
  providedIn: "root",
})
export class FileService {
  private readonly api = inject(ApiFilesService);
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  upload(
    file: File,
    altchaPayload: string,
    options?: { expiryHours?: number; maxDownloads?: number; password?: string },
  ): Observable<HttpEvent<FileUploadResponse>> {
    return this.api.uploadFileApiFilesUploadPost(
      {
        altcha: altchaPayload,
        expiry_hours: options?.expiryHours,
        file,
        max_downloads:
          options?.maxDownloads && options.maxDownloads > 0 ? options.maxDownloads : undefined,
        password: options?.password ?? undefined,
      },
      { observe: "events", reportProgress: true },
    );
  }

  getFileInfo(downloadToken: string): Observable<FileUploadResponse> {
    return this.api.getFileInfoApiFilesDownloadTokenInfoGet(downloadToken);
  }

  listFiles(): Observable<FileListResponse> {
    return this.api.listFilesApiFilesGet();
  }

  refreshFile(fileId: number, expiryHours?: number): Observable<FileUploadResponse> {
    return this.api.refreshDownloadLinkApiFilesFileIdRefreshPost(fileId, {
      expiry_hours: expiryHours,
    });
  }

  deleteFile(fileId: number): Observable<Record<string, string>> {
    return this.api.deactivateFileApiFilesFileIdDelete(fileId);
  }

  editFile(fileId: number, body: FileEditRequest): Observable<FileUploadResponse> {
    return this.api.editFileApiFilesFileIdPatch(fileId, body);
  }

  getDownloadUrl(downloadToken: string): string {
    return `${this.apiUrl}/api/files/${downloadToken}`;
  }

  uploadMultiple(
    files: File[],
    altchaPayload: string,
    options?: { expiryHours?: number; maxDownloads?: number; password?: string },
  ): Observable<HttpEvent<MultiFileUploadResponse>> {
    return this.api.uploadMultipleFilesApiFilesUploadMultiplePost(
      {
        altcha: altchaPayload,
        expiry_hours: options?.expiryHours,
        files,
        max_downloads:
          options?.maxDownloads && options.maxDownloads > 0 ? options.maxDownloads : undefined,
        password: options?.password ?? undefined,
      },
      { observe: "events", reportProgress: true },
    );
  }

  getGroupInfo(uploadGroup: string): Observable<UploadGroupInfoResponse> {
    return this.api.getGroupInfoApiFilesGroupUploadGroupGet(uploadGroup);
  }

  addFilesToGroup(uploadGroup: string, files: File[]): Observable<MultiFileUploadResponse> {
    const formData = new FormData();
    for (const file of files) {
      formData.append("files", file);
    }
    return this.http.post<MultiFileUploadResponse>(
      `${this.apiUrl}/api/files/group/${encodeURIComponent(uploadGroup)}/add`,
      formData,
    );
  }

  getGroupDownloadUrl(uploadGroup: string): string {
    return `${this.apiUrl}/api/files/group/${uploadGroup}/download`;
  }

  refreshGroup(
    uploadGroup: string,
    body: GroupRefreshRequest,
  ): Observable<MultiFileUploadResponse> {
    return this.api.refreshGroupApiFilesGroupUploadGroupRefreshPost(uploadGroup, body);
  }

  editGroup(uploadGroup: string, body: GroupEditRequest): Observable<MultiFileUploadResponse> {
    return this.api.editGroupApiFilesGroupUploadGroupPatch(uploadGroup, body);
  }
}
