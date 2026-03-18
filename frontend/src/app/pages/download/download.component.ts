import { Component, computed, inject, signal } from "@angular/core";
import { toSignal } from "@angular/core/rxjs-interop";
import { ActivatedRoute } from "@angular/router";
import { FileService, UploadGroupInfoResponse } from "../../services/file.service";
import { DatePipe } from "@angular/common";
import { formatFileSize, isExpired } from "../../utils/file.utils";
import { catchError, of, map } from "rxjs";

@Component({
  selector: "app-download",
  imports: [DatePipe],
  templateUrl: "./download.component.html",
  styleUrl: "./download.component.scss",
})
export class DownloadComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly fileService = inject(FileService);

  private readonly token = this.route.snapshot.paramMap.get("token") ?? "";
  private readonly group = this.route.snapshot.paramMap.get("group") ?? "";

  isGroup = !!this.group;

  private readonly fileInfoResult = this.token
    ? toSignal(
        this.fileService.getFileInfo(this.token).pipe(
          map((info) => ({ info, error: null })),
          catchError(() => of({ info: null, error: "File not found or has expired." })),
        ),
      )
    : signal({ info: null, error: this.group ? null : "Invalid download link." });

  private readonly groupInfoResult = this.group
    ? toSignal(
        this.fileService.getGroupInfo(this.group).pipe(
          map((info) => ({ info, error: null })),
          catchError(() => of({ info: null, error: "Files not found or have expired." })),
        ),
      )
    : signal({ info: null, error: null });

  fileInfo = computed(() => this.fileInfoResult()?.info ?? null);
  groupInfo = computed(() => this.groupInfoResult()?.info ?? null);
  error = computed(() => this.fileInfoResult()?.error ?? this.groupInfoResult()?.error ?? null);
  loading = computed(() => {
    if (this.token) return this.fileInfoResult() === undefined;
    if (this.group) return this.groupInfoResult() === undefined;
    return false;
  });

  download(): void {
    window.location.href = this.fileService.getDownloadUrl(this.token);
  }

  downloadGroup(): void {
    window.location.href = this.fileService.getGroupDownloadUrl(this.group);
  }

  downloadSingleFile(downloadUrl: string): void {
    window.location.href = downloadUrl;
  }

  formatSize(bytes: number): string {
    return formatFileSize(bytes);
  }

  isExpired(expiresAt: string): boolean {
    return isExpired(expiresAt);
  }
}
