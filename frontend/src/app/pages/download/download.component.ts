import { Component, computed, inject, signal } from "@angular/core";
import { toSignal } from "@angular/core/rxjs-interop";
import { ActivatedRoute } from "@angular/router";
import { FileService } from "../../services/file.service";
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

  private readonly fileInfoResult = this.token
    ? toSignal(
        this.fileService.getFileInfo(this.token).pipe(
          map((info) => ({ info, error: null })),
          catchError(() => of({ info: null, error: "File not found or has expired." })),
        ),
      )
    : signal({ info: null, error: "Invalid download link." });

  fileInfo = computed(() => this.fileInfoResult()?.info ?? null);
  error = computed(() => this.fileInfoResult()?.error ?? null);
  loading = computed(() => (this.token ? this.fileInfoResult() === undefined : false));

  download(): void {
    window.location.href = this.fileService.getDownloadUrl(this.token);
  }

  formatSize(bytes: number): string {
    return formatFileSize(bytes);
  }

  isExpired(expiresAt: string): boolean {
    return isExpired(expiresAt);
  }
}
