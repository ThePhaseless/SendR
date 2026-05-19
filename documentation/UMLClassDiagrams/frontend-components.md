# Frontend Angular Components

Components are grouped by UI responsibility and use compact signal notation.

## Upload Components

```mermaid
classDiagram
    direction LR

    class UploadFileEntry {
      +file: File
      +name: string
      +size: number
      +mimeType: string
      +relativePath: string optional
    }

    class FileTreeNode {
      +name: string
      +fullPath: string
      +isFolder: boolean
      +size: number
      +fileCount: number
    }

    class PasswordEntry {
      +label: string
      +password: string
    }

    class FilePickerComponent {
      +fileLimitInputs
      +pendingFilesModel
      +filesChangedOutput
      +openFilePicker()
      +removeFile(index)
      +clearFiles()
    }

    class UploadSettingsComponent {
      +tierInput
      +expiryDownloadModels
      +passwordEmailModels
      +titleDescriptionModels
      +computedOptionLists
      +addPassword()
      +addEmail()
      +reset()
    }

    FilePickerComponent --> UploadFileEntry : manages
    FilePickerComponent --> FileTreeNode : builds
    UploadSettingsComponent --> PasswordEntry : manages
```

## Shell And Feedback Components

```mermaid
classDiagram
    direction LR

    class HeaderComponent {
      +currentUserSignal
      +isAdminComputed
      +menuOpenSignal
      +logout()
      +devLogin(role)
    }

    class JumpingTextComponent {
      +textInput
      +speedInput
      +displayTextComputed
    }

    class AppNotificationsComponent {
      +notificationsSignal
      +dismiss(id)
    }

    class ConfirmDialogComponent {
      +dialogState
      +confirm()
      +cancel()
    }

    HeaderComponent --> UserResponse : displays
    AppNotificationsComponent --> UiNotificationService : reads
    ConfirmDialogComponent --> ConfirmDialogService : controls

    note for HeaderComponent "Navigation, session status, and local dev login actions"
    note for AppNotificationsComponent "Global toast-style status messages"
    note for ConfirmDialogComponent "Shared confirmation modal"
```

---

Angular components and the data structures they manage.