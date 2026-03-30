import type { HttpEvent } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import type { Observable } from "rxjs";
import { environment } from "../../environments/environment";
import { FilesService as ApiFilesService } from "../api/endpoints/files/files.service";
import type {
  FileListResponse,
  FileUploadResponse,
  MultiFileUploadResponse,
  UploadGroupInfoResponse,
} from "../api/model";

export type { FileUploadResponse, MultiFileUploadResponse, UploadGroupInfoResponse };

@Injectable({
  providedIn: "root",
})
export class FileService {
  private readonly api = inject(ApiFilesService);
  private readonly apiUrl = environment.apiUrl;

  upload(
    file: File,
    altchaPayload: string,
    options?: { expiryHours?: number; maxDownloads?: number },
  ): Observable<HttpEvent<FileUploadResponse>> {
    return this.api.uploadFileApiFilesUploadPost(
      {
        altcha: altchaPayload,
        expiry_hours: options?.expiryHours,
        file,
        max_downloads:
          options?.maxDownloads && options.maxDownloads > 0 ? options.maxDownloads : undefined,
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

  refreshFile(fileId: number): Observable<FileUploadResponse> {
    return this.api.refreshDownloadLinkApiFilesFileIdRefreshPost(fileId);
  }

  deleteFile(fileId: number): Observable<Record<string, string>> {
    return this.api.deactivateFileApiFilesFileIdDelete(fileId);
  }

  getDownloadUrl(downloadToken: string): string {
    return `${this.apiUrl}/api/files/${downloadToken}`;
  }

  uploadMultiple(
    files: File[],
    altchaPayload: string,
    options?: { expiryHours?: number; maxDownloads?: number },
  ): Observable<HttpEvent<MultiFileUploadResponse>> {
    return this.api.uploadMultipleFilesApiFilesUploadMultiplePost(
      {
        altcha: altchaPayload,
        expiry_hours: options?.expiryHours,
        files,
        max_downloads:
          options?.maxDownloads && options.maxDownloads > 0 ? options.maxDownloads : undefined,
      },
      { observe: "events", reportProgress: true },
    );
  }

  getGroupInfo(uploadGroup: string): Observable<UploadGroupInfoResponse> {
    return this.api.getGroupInfoApiFilesGroupUploadGroupGet(uploadGroup);
  }

  getGroupDownloadUrl(uploadGroup: string): string {
    return `${this.apiUrl}/api/files/group/${uploadGroup}/download`;
  }
}
