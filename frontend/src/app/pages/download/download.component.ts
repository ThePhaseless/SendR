import { DatePipe } from "@angular/common";
import { Component, computed, inject, signal } from "@angular/core";
import { ActivatedRoute } from "@angular/router";
import {
  getFileInfoApiFilesDownloadTokenInfoGetResource,
  getGroupInfoApiFilesGroupUploadGroupGetResource,
} from "../../api/endpoints/filename.resource";
import { FileService } from "../../services/file.service";
import { filenameToEmoji, formatFileSize, isExpired } from "../../utils/file.utils";

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

  private readonly fileInfoResource = this.token
    ? getFileInfoApiFilesDownloadTokenInfoGetResource(signal(this.token))
    : undefined;

  private readonly groupInfoResource = this.group
    ? getGroupInfoApiFilesGroupUploadGroupGetResource(signal(this.group))
    : undefined;

  fileInfo = computed(() => this.fileInfoResource?.value() ?? null);
  groupInfo = computed(() => this.groupInfoResource?.value() ?? null);
  error = computed(() => {
    if (this.token && this.fileInfoResource?.error()) {
      return "File not found or has expired.";
    }
    if (this.group && this.groupInfoResource?.error()) {
      return "Files not found or have expired.";
    }
    if (!this.token && !this.group) {
      return "Invalid download link.";
    }
    return null;
  });
  loading = computed(() => {
    if (this.token) {
      return this.fileInfoResource?.isLoading() ?? false;
    }
    if (this.group) {
      return this.groupInfoResource?.isLoading() ?? false;
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

  getFileEmoji(name: string): string {
    return filenameToEmoji(name);
  }
}
