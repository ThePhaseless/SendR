import { NgTemplateOutlet } from "@angular/common";
import { Component, computed, input, model, output, signal } from "@angular/core";
import { filenameToEmoji, formatFileSize, mimeToEmoji } from "../../utils/file.utils";

export interface UploadFileEntry {
  file: File;
  name: string;
  size: number;
  mimeType: string;
  relativePath?: string;
}

export interface FileTreeNode {
  name: string;
  fullPath: string;
  isFolder: boolean;
  size: number;
  fileCount: number;
  children?: FileTreeNode[];
  /** Index in the flat pendingFiles array (only for leaf files) */
  fileIndex?: number;
  mimeType?: string;
}

@Component({
  imports: [NgTemplateOutlet],
  selector: "app-file-picker",
  styleUrl: "./file-picker.component.scss",
  templateUrl: "./file-picker.component.html",
})
export class FilePickerComponent {
  /** Max total size in MB. */
  maxFileSizeMb = input(100);

  /** Max number of files (0 = unlimited). */
  maxFilesPerUpload = input(10);

  /** Whether interactions are disabled (e.g. during upload). */
  disabled = input(false);

  /** Whether to show a compact version (for dashboard). */
  compact = input(false);

  /** Staged files ready for upload. */
  pendingFiles = model<UploadFileEntry[]>([]);

  /** Emitted when files list changes. */
  filesChanged = output<UploadFileEntry[]>();

  isDragging = signal(false);
  collapsedFolders = signal(new Set());

  totalPendingSize = computed(() => this.pendingFiles().reduce((sum, f) => sum + f.size, 0));

  limitWarning = computed<string | null>(() => {
    const files = this.pendingFiles();
    if (files.length === 0) {
      return null;
    }
    const maxBytes = this.maxFileSizeMb() * 1024 * 1024;
    const maxPerUpload = this.maxFilesPerUpload();
    const totalSize = files.reduce((sum, f) => sum + f.size, 0);
    const warnings: string[] = [];
    if (maxPerUpload > 0 && files.length > maxPerUpload) {
      warnings.push(`Too many files: ${files.length}/${maxPerUpload}`);
    }
    if (totalSize > maxBytes) {
      warnings.push(
        `Total size exceeds limit: ${this.formatSize(totalSize)}/${this.maxFileSizeMb()} MB`,
      );
    }
    return warnings.length > 0 ? warnings.join(". ") : null;
  });

  fileTree = computed<FileTreeNode[]>(() => this.buildFileTree(this.pendingFiles()));

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging.set(true);
  }

  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging.set(false);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging.set(false);
    const items = event.dataTransfer?.items;
    if (items && items.length > 0) {
      void this.processDataTransferItems(items);
    }
  }

  onFileSelected(event: Event): void {
    const { target } = event;
    if (!(target instanceof HTMLInputElement) || !target.files || target.files.length === 0) {
      return;
    }
    const files = [...target.files];
    const entries: UploadFileEntry[] = files.map((file) => ({
      file,
      mimeType: file.type,
      name: file.name,
      relativePath: file.webkitRelativePath || undefined,
      size: file.size,
    }));
    this.stageFileEntries(entries);
    target.value = "";
  }

  removeFile(index: number): void {
    this.pendingFiles.update((files) => files.filter((_, i) => i !== index));
    this.filesChanged.emit(this.pendingFiles());
  }

  removeFolder(folderPath: string): void {
    this.pendingFiles.update((files) =>
      files.filter(
        (f) => !f.relativePath?.startsWith(folderPath + "/") && f.relativePath !== folderPath,
      ),
    );
    this.collapsedFolders.update((set) => {
      const next = new Set(set);
      for (const key of set) {
        if (key === folderPath || key.startsWith(folderPath + "/")) {
          next.delete(key);
        }
      }
      return next;
    });
    this.filesChanged.emit(this.pendingFiles());
  }

  toggleFolder(folderPath: string): void {
    this.collapsedFolders.update((set) => {
      const next = new Set(set);
      if (next.has(folderPath)) {
        next.delete(folderPath);
      } else {
        next.add(folderPath);
      }
      return next;
    });
  }

  isFolderCollapsed(folderPath: string): boolean {
    return this.collapsedFolders().has(folderPath);
  }

  getNodeEmoji(node: FileTreeNode): string {
    if (node.mimeType) {
      return mimeToEmoji(node.mimeType);
    }
    return filenameToEmoji(node.name);
  }

  formatSize(bytes: number): string {
    return formatFileSize(bytes);
  }

  /** Clear all staged files. */
  clear(): void {
    this.pendingFiles.set([]);
    this.collapsedFolders.set(new Set());
    this.filesChanged.emit([]);
  }

  /** Get the File objects ready for upload. */
  getFiles(): File[] {
    return this.pendingFiles().map((e) => e.file);
  }

  private stageFileEntries(newEntries: UploadFileEntry[]): void {
    const combined = [...this.pendingFiles(), ...newEntries];
    this.pendingFiles.set(combined);
    this.filesChanged.emit(combined);
  }

  private async processDataTransferItems(items: DataTransferItemList): Promise<void> {
    const entries: FileSystemEntry[] = [];
    for (let i = 0; i < items.length; i++) {
      const entry = items[i].webkitGetAsEntry();
      if (entry) {
        entries.push(entry);
      }
    }
    const files = await this.readEntries(entries, "");
    if (files.length > 0) {
      this.stageFileEntries(files);
    }
  }

  private async readEntries(
    entries: FileSystemEntry[],
    basePath: string,
  ): Promise<UploadFileEntry[]> {
    const result: UploadFileEntry[] = [];
    for (const entry of entries) {
      if (entry.isFile) {
        const file = await this.getFile(entry as FileSystemFileEntry);
        const relativePath = basePath ? `${basePath}/${file.name}` : "";
        result.push({
          file,
          mimeType: file.type,
          name: file.name,
          relativePath: relativePath || undefined,
          size: file.size,
        });
      } else if (entry.isDirectory) {
        const dirEntry = entry as FileSystemDirectoryEntry;
        const dirReader = dirEntry.createReader();
        const childEntries = await this.readAllDirectoryEntries(dirReader);
        const prefix = basePath ? `${basePath}/${entry.name}` : entry.name;
        const childFiles = await this.readEntries(childEntries, prefix);
        result.push(...childFiles);
      }
    }
    return result;
  }

  private readAllDirectoryEntries(reader: FileSystemDirectoryReader): Promise<FileSystemEntry[]> {
    return new Promise((resolve, reject) => {
      const allEntries: FileSystemEntry[] = [];
      const readBatch = (): void => {
        reader.readEntries((entries) => {
          if (entries.length === 0) {
            resolve(allEntries);
          } else {
            allEntries.push(...entries);
            readBatch();
          }
        }, reject);
      };
      readBatch();
    });
  }

  private getFile(entry: FileSystemFileEntry): Promise<File> {
    return new Promise((resolve, reject) => {
      entry.file(resolve, reject);
    });
  }

  private buildFileTree(files: UploadFileEntry[]): FileTreeNode[] {
    interface TreeBuildNode {
      name: string;
      fullPath: string;
      children: Map<string, TreeBuildNode>;
      files: { entry: UploadFileEntry; index: number }[];
      totalSize: number;
      totalFileCount: number;
    }

    const rootChildren = new Map<string, TreeBuildNode>();
    const rootFiles: FileTreeNode[] = [];

    for (let i = 0; i < files.length; i++) {
      const entry = files[i];
      if (!entry.relativePath) {
        rootFiles.push({
          fileCount: 1,
          fileIndex: i,
          fullPath: entry.name,
          isFolder: false,
          mimeType: entry.mimeType,
          name: entry.name,
          size: entry.size,
        });
        continue;
      }

      const parts = entry.relativePath.split("/");
      let currentChildren = rootChildren;
      let currentPath = "";

      for (let p = 0; p < parts.length - 1; p++) {
        currentPath = currentPath ? `${currentPath}/${parts[p]}` : parts[p];
        if (!currentChildren.has(parts[p])) {
          currentChildren.set(parts[p], {
            children: new Map(),
            files: [],
            fullPath: currentPath,
            name: parts[p],
            totalFileCount: 0,
            totalSize: 0,
          });
        }
        const node = currentChildren.get(parts[p])!;
        node.totalSize += entry.size;
        node.totalFileCount += 1;
        if (p === parts.length - 2) {
          node.files.push({ entry, index: i });
        }
        currentChildren = node.children;
      }
    }

    const convertNode = (node: TreeBuildNode): FileTreeNode => {
      const children: FileTreeNode[] = [];
      for (const child of node.children.values()) {
        children.push(convertNode(child));
      }
      for (const f of node.files) {
        children.push({
          fileCount: 1,
          fileIndex: f.index,
          fullPath: `${node.fullPath}/${f.entry.name}`,
          isFolder: false,
          mimeType: f.entry.mimeType,
          name: f.entry.name,
          size: f.entry.size,
        });
      }
      return {
        children,
        fileCount: node.totalFileCount,
        fullPath: node.fullPath,
        isFolder: true,
        name: node.name,
        size: node.totalSize,
      };
    };

    const result: FileTreeNode[] = [];
    for (const node of rootChildren.values()) {
      result.push(convertNode(node));
    }
    result.push(...rootFiles);
    return result;
  }
}
