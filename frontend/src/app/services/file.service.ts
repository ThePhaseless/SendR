import type { HttpEvent } from "@angular/common/http";
import { HttpClient } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import type { Observable } from "rxjs";
import { environment } from "../../environments/environment";
import { FilesService as ApiFilesService } from "../api/endpoints/files/files.service";
import type {
  AccessEditRequest,
  AccessInfoResponse,
  DownloadStatsResponse,
  FileEditRequest,
  FileListResponse,
  FileUploadResponse,
  GroupEditRequest,
  GroupRefreshRequest,
  MultiFileUploadResponse,
  RecipientStatsResponse,
  UploadGroupInfoResponse,
} from "../api/model";

export type {
  AccessEditRequest,
  AccessInfoResponse,
  DownloadStatsResponse,
  FileEditRequest,
  FileUploadResponse,
  GroupEditRequest,
  GroupRefreshRequest,
  MultiFileUploadResponse,
  RecipientStatsResponse,
  UploadGroupInfoResponse,
};

export interface UploadAccessOptions {
  expiryHours?: number;
  maxDownloads?: number;
  isPublic?: boolean;
  passwords?: { label: string; password: string }[];
  emails?: string[];
  showEmailStats?: boolean;
  title?: string;
  description?: string;
}

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
    options?: UploadAccessOptions,
  ): Observable<HttpEvent<FileUploadResponse>> {
    return this.api.uploadFileApiFilesUploadPost(
      {
        altcha: altchaPayload,
        expiry_hours: options?.expiryHours,
        file,
        max_downloads:
          options?.maxDownloads && options.maxDownloads > 0 ? options.maxDownloads : undefined,
        is_public: options?.isPublic ?? true,
        passwords:
          options?.passwords && options.passwords.length > 0
            ? JSON.stringify(options.passwords)
            : undefined,
        emails:
          options?.emails && options.emails.length > 0 ? JSON.stringify(options.emails) : undefined,
        show_email_stats: options?.showEmailStats ?? false,
        title: options?.title || undefined,
        description: options?.description || undefined,
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
    options?: UploadAccessOptions,
  ): Observable<HttpEvent<MultiFileUploadResponse>> {
    return this.api.uploadMultipleFilesApiFilesUploadMultiplePost(
      {
        altcha: altchaPayload,
        expiry_hours: options?.expiryHours,
        files,
        max_downloads:
          options?.maxDownloads && options.maxDownloads > 0 ? options.maxDownloads : undefined,
        is_public: options?.isPublic ?? true,
        passwords:
          options?.passwords && options.passwords.length > 0
            ? JSON.stringify(options.passwords)
            : undefined,
        emails:
          options?.emails && options.emails.length > 0 ? JSON.stringify(options.emails) : undefined,
        show_email_stats: options?.showEmailStats ?? false,
        title: options?.title || undefined,
        description: options?.description || undefined,
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

  getAccessInfo(uploadGroup: string): Observable<AccessInfoResponse> {
    return this.api.getAccessInfoApiFilesGroupUploadGroupAccessInfoGet(uploadGroup);
  }

  editAccess(uploadGroup: string, body: AccessEditRequest): Observable<AccessInfoResponse> {
    return this.api.editAccessApiFilesGroupUploadGroupAccessPatch(uploadGroup, body);
  }

  getGroupStats(uploadGroup: string): Observable<DownloadStatsResponse> {
    return this.api.getGroupStatsApiFilesGroupUploadGroupStatsGet(uploadGroup);
  }

  getRecipientStats(uploadGroup: string, token: string): Observable<RecipientStatsResponse> {
    return this.api.getRecipientStatsApiFilesGroupUploadGroupRecipientStatsGet(uploadGroup, {
      password: token,
    });
  }

  getDownloadUrlWithPassword(downloadToken: string, password?: string): string {
    const base = `${this.apiUrl}/api/files/${downloadToken}`;
    if (password) {
      return `${base}?password=${encodeURIComponent(password)}`;
    }
    return base;
  }

  getGroupDownloadUrlWithPassword(uploadGroup: string, password?: string): string {
    const base = `${this.apiUrl}/api/files/group/${uploadGroup}/download`;
    if (password) {
      return `${base}?password=${encodeURIComponent(password)}`;
    }
    return base;
  }
}
