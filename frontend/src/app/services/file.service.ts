import type { HttpEvent } from "@angular/common/http";
import { HttpClient } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import type { Observable } from "rxjs";

export interface FileUploadResponse {
  id: number;
  original_filename: string;
  file_size_bytes: number;
  download_url: string;
  expires_at: string;
  download_count: number;
  is_active: boolean;
}

export interface MultiFileUploadResponse {
  files: FileUploadResponse[];
  upload_group: string;
  total_size_bytes: number;
}

export interface UploadGroupInfoResponse {
  files: FileUploadResponse[];
  upload_group: string;
  total_size_bytes: number;
  file_count: number;
  will_zip: boolean;
}

interface FileListResponse {
  files: FileUploadResponse[];
}

@Injectable({
  providedIn: "root",
})
export class FileService {
  private readonly http = inject(HttpClient);

  upload(file: File, altchaPayload: string): Observable<HttpEvent<FileUploadResponse>> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("altcha", altchaPayload);
    return this.http.post<FileUploadResponse>("/api/files/upload", formData, {
      observe: "events",
      reportProgress: true,
    });
  }

  getFileInfo(downloadToken: string): Observable<FileUploadResponse> {
    return this.http.get<FileUploadResponse>(`/api/files/${downloadToken}/info`);
  }

  listFiles(): Observable<FileListResponse> {
    return this.http.get<FileListResponse>("/api/files/");
  }

  refreshFile(fileId: number): Observable<FileUploadResponse> {
    return this.http.post<FileUploadResponse>(`/api/files/${fileId}/refresh`, {});
  }

  deleteFile(fileId: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`/api/files/${fileId}`);
  }

  getDownloadUrl(downloadToken: string): string {
    return `/api/files/${downloadToken}`;
  }

  uploadMultiple(
    files: File[],
    altchaPayload: string,
  ): Observable<HttpEvent<MultiFileUploadResponse>> {
    const formData = new FormData();
    for (const file of files) {
      formData.append("files", file);
    }
    formData.append("altcha", altchaPayload);
    return this.http.post<MultiFileUploadResponse>("/api/files/upload-multiple", formData, {
      observe: "events",
      reportProgress: true,
    });
  }

  getGroupInfo(uploadGroup: string): Observable<UploadGroupInfoResponse> {
    return this.http.get<UploadGroupInfoResponse>(`/api/files/group/${uploadGroup}`);
  }

  getGroupDownloadUrl(uploadGroup: string): string {
    return `/api/files/group/${uploadGroup}/download`;
  }
}
