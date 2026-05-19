# Frontend Pages & Routes

Page diagrams focus on responsibilities and service dependencies rather than every signal and method on each component.

## Main User Pages

```mermaid
classDiagram
    direction LR

    class UploadGroup {
      +key: string
      +files: FileUploadResponse array
      +isGroup: boolean
      +uploadGroup: string optional
      +totalSize: number
    }

    class DashboardComponent {
      -fileService: FileService
      -authService: AuthService
      +filesGroupedState
      +quotaLimitsState
      +uploadPanelState
      +accessEditingState
      +uploadFiles()
      +editDeleteActions
      +groupActions
    }

    class AuthComponent {
      -authService: AuthService
      +emailCodeState
      +passwordFormState
      +loadingErrorState
      +requestCode()
      +verifyCode()
      +loginWithPassword()
      +reset()
    }

    class HomeComponent {
      +currentUserState
      +heroActions
    }

    class DownloadComponent {
      -fileService: FileService
      +fileGroupRouteState
      +accessChallengeState
      +downloadProgressState
      +downloadFile()
      +downloadGroup()
    }

    DashboardComponent --> FileService : files
    DashboardComponent --> AuthService : session
    DashboardComponent --> UploadGroup : groups
    DashboardComponent --> FilePickerComponent : uploads
    DashboardComponent --> UploadSettingsComponent : settings
    AuthComponent --> AuthService : auth
    HomeComponent --> AuthService : session
    DownloadComponent --> FileService : downloads
```

## Admin And Subscription Pages

```mermaid
classDiagram
    direction LR

    class AdminComponent {
      -adminService: AdminService
      +userSearchState
      +selectedUploadsState
      +loginAuditState
      +statsState
      +loadUsers()
      +saveUserEdit()
      +deleteActions
    }

    class PremiumComponent {
      -authService: AuthService
      +subscriptionState
      +loadingState
    }

    AdminComponent --> AdminService : users/transfers
    AdminComponent --> ConfirmDialogService : destructive actions
    PremiumComponent --> AuthService : session

    note for AdminComponent "Admin search, user mutation, upload review, login audit"
    note for PremiumComponent "Subscription status and upgrade copy"
```

---

Angular routed pages and their main service dependencies.