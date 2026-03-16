import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface FileUploadResponse {
  id: number;
  original_filename: string;
  file_size_bytes: number;
  download_url: string;
  expires_at: string;
  download_count: number;
  is_active: boolean;
}

interface FileListResponse {
  files: FileUploadResponse[];
  quota_used: number;
  quota_limit: number;
}

@Injectable({
  providedIn: 'root',
})
export class FileService {
  private readonly http = inject(HttpClient);

  upload(file: File): Observable<FileUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<FileUploadResponse>('/api/files/upload', formData, {
      reportProgress: false,
    });
  }

  getFileInfo(downloadToken: string): Observable<FileUploadResponse> {
    return this.http.get<FileUploadResponse>(
      `/api/files/${downloadToken}/info`,
    );
  }

  listFiles(): Observable<FileListResponse> {
    return this.http.get<FileListResponse>('/api/files/');
  }

  refreshFile(fileId: number): Observable<FileUploadResponse> {
    return this.http.post<FileUploadResponse>(
      `/api/files/${fileId}/refresh`,
      {},
    );
  }

  deleteFile(fileId: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`/api/files/${fileId}`);
  }

  getDownloadUrl(downloadToken: string): string {
    return `/api/files/${downloadToken}`;
  }
}
