import type { HttpEvent } from '@angular/common/http';
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { FilesService as ApiFilesService } from '../api/endpoints/files/files.service';
import type {
  AccessEditRequest,
  AccessInfoResponse,
  DownloadStatsResponse,
  FileEditRequest,
  FileUploadResponse,
  GroupEditRequest,
  GroupRefreshRequest,
  MultiFileUploadResponse,
  UploadGroupInfoResponse,
} from '../api/model';
import type { UploadFileEntry } from '../components/file-picker/file-picker.component';

export type {
  AccessEditRequest,
  AccessInfoResponse,
  DownloadStatsResponse,
  FileEditRequest,
  FileUploadResponse,
  GroupEditRequest,
  GroupRefreshRequest,
  MultiFileUploadResponse,
  UploadGroupInfoResponse,
};

export interface UploadAccessOptions {
  expiryHours?: number;
  maxDownloads?: number;
  isPublic?: boolean;
  passwords?: { label: string; password: string }[];
  emails?: string[];
  showEmailStats?: boolean;
  separateDownloadCounts?: boolean;
  title?: string;
  description?: string;
}

@Injectable({
  providedIn: 'root',
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
        description: options?.description ?? undefined,
        emails:
          options?.emails && options.emails.length > 0 ? JSON.stringify(options.emails) : undefined,
        expiry_hours: options?.expiryHours,
        file,
        is_public: options?.isPublic ?? true,
        max_downloads:
          options?.maxDownloads && options.maxDownloads > 0 ? options.maxDownloads : undefined,
        passwords:
          options?.passwords && options.passwords.length > 0
            ? JSON.stringify(options.passwords)
            : undefined,
        separate_download_counts: options?.separateDownloadCounts ?? false,
        show_email_stats: options?.showEmailStats ?? false,
        title: options?.title ?? undefined,
      },
      { observe: 'events', reportProgress: true },
    );
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
    files: UploadFileEntry[],
    altchaPayload: string,
    options?: UploadAccessOptions,
  ): Observable<HttpEvent<MultiFileUploadResponse>> {
    const formData = this.buildUploadAccessFormData(altchaPayload, options);
    for (const entry of files) {
      formData.append('files', entry.file, entry.relativePath ?? entry.file.name);
    }

    return this.http.post<MultiFileUploadResponse>(
      `${this.apiUrl}/api/files/upload-multiple`,
      formData,
      {
        observe: 'events',
        reportProgress: true,
      },
    );
  }

  addFilesToGroup(
    uploadGroup: string,
    files: UploadFileEntry[],
  ): Observable<MultiFileUploadResponse> {
    const formData = new FormData();
    for (const entry of files) {
      formData.append('files', entry.file, entry.relativePath ?? entry.file.name);
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

  editAccess(uploadGroup: string, body: AccessEditRequest): Observable<AccessInfoResponse> {
    return this.api.editAccessApiFilesGroupUploadGroupAccessPatch(uploadGroup, body);
  }

  getDownloadUrlWithPassword(downloadToken: string, _password?: string): string {
    return `${this.apiUrl}/api/files/${downloadToken}`;
  }

  getGroupDownloadUrlWithPassword(uploadGroup: string, _password?: string): string {
    return `${this.apiUrl}/api/files/group/${uploadGroup}/download`;
  }

  private buildUploadAccessFormData(
    altchaPayload: string,
    options?: UploadAccessOptions,
  ): FormData {
    const formData = new FormData();
    formData.append('altcha', altchaPayload);
    if (options?.expiryHours !== undefined) {
      formData.append('expiry_hours', options.expiryHours.toString());
    }
    if (options?.maxDownloads && options.maxDownloads > 0) {
      formData.append('max_downloads', options.maxDownloads.toString());
    }
    formData.append('is_public', (options?.isPublic ?? true).toString());
    if (options?.passwords && options.passwords.length > 0) {
      formData.append('passwords', JSON.stringify(options.passwords));
    }
    if (options?.emails && options.emails.length > 0) {
      formData.append('emails', JSON.stringify(options.emails));
    }
    formData.append('show_email_stats', (options?.showEmailStats ?? false).toString());
    formData.append(
      'separate_download_counts',
      (options?.separateDownloadCounts ?? false).toString(),
    );
    if (options?.title) {
      formData.append('title', options.title);
    }
    if (options?.description) {
      formData.append('description', options.description);
    }
    return formData;
  }
}
