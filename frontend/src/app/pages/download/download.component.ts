import { Component, computed, inject, signal } from "@angular/core";
import { catchError, map, of } from "rxjs";
import { formatFileSize, isExpired } from "../../utils/file.utils";
import { ActivatedRoute } from "@angular/router";
import { DatePipe } from "@angular/common";
import { FileService } from "../../services/file.service";
import { toSignal } from "@angular/core/rxjs-interop";

@Component({
  imports: [DatePipe],
  selector: "app-download",
  styleUrl: "./download.component.scss",
  templateUrl: "./download.component.html",
})
export class DownloadComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly fileService = inject(FileService);

  private readonly token = this.route.snapshot.paramMap.get("token") ?? "";
  private readonly group = this.route.snapshot.paramMap.get("group") ?? "";

  isGroup = Boolean(this.group);

  private readonly fileInfoResult = this.token
    ? toSignal(
        this.fileService.getFileInfo(this.token).pipe(
          map((info) => ({ error: null, info })),
          catchError(() => of({ error: "File not found or has expired.", info: null })),
        ),
      )
    : signal({ error: this.group ? null : "Invalid download link.", info: null });

  private readonly groupInfoResult = this.group
    ? toSignal(
        this.fileService.getGroupInfo(this.group).pipe(
          map((info) => ({ error: null, info })),
          catchError(() => of({ error: "Files not found or have expired.", info: null })),
        ),
      )
    : signal({ error: null, info: null });

  fileInfo = computed(() => this.fileInfoResult()?.info ?? null);
  groupInfo = computed(() => this.groupInfoResult()?.info ?? null);
  error = computed(() => this.fileInfoResult()?.error ?? this.groupInfoResult()?.error ?? null);
  loading = computed(() => {
    if (this.token) {
      return this.fileInfoResult() === undefined;
    }
    if (this.group) {
      return this.groupInfoResult() === undefined;
    }
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
