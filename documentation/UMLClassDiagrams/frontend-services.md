# Frontend Angular Services

Services are shown by responsibility. Generated OpenAPI endpoint services are represented as API adapters to avoid long generated method names.

## Session And Auth Services

```mermaid
classDiagram
    direction LR

    class AuthService {
      -http: HttpClient
      -api: ApiAuthService
      -devApi: ApiDevService
      -subscriptionApi: ApiSubscriptionService
      +authenticatedSignal
      +currentUserResource
      +requestCode(email)
      +verifyCode(email, code)
      +loginPassword(email, password)
      +devLogin(role)
      +syncSession()
      +logout()
    }

    class ApiAuthService {
      +requestCodeEndpoint
      +verifyCodeEndpoint
      +sessionEndpoints
      +passwordEndpoints
    }

    class ApiSubscriptionService {
      +subscriptionEndpoint
    }

    class ApiDevService {
      +localDevLoginEndpoint
    }

    AuthService --> ApiAuthService : wraps
    AuthService --> ApiSubscriptionService : wraps
    AuthService --> ApiDevService : local only
    AuthService --> HttpClient : direct calls

    note for AuthService "Session state is derived from backend cookies, not browser storage"
```

## File Services

```mermaid
classDiagram
    direction LR

    class FileService {
      -api: ApiFilesService
      -http: HttpClient
      +uploadFiles
      +listOwnedFiles
      +editDeleteFiles
      +downloadBlobs
      +groupAccess
      +downloadStats
    }

    class ApiFilesService {
      +generatedFileEndpoints
      +generatedGroupEndpoints
      +generatedStatsEndpoints
    }

    class UploadAccessOptions {
      +expiryDownloadLimits
      +publicPasswordEmailAccess
      +titleDescription
    }

    FileService --> ApiFilesService : wraps
    FileService --> HttpClient : upload and blob requests
    FileService --> UploadAccessOptions : accepts

    note for FileService "Hand-written facade for upload progress, blobs, and generated endpoints"
```

## Admin And UI Services

```mermaid
classDiagram
    direction LR

    class AdminService {
      -api: ApiAdminService
      +listUsers(page, perPage, search)
      +updateUser(userId, update)
      +deleteUser(userId)
      +listUserUploads(userId)
      +listUserLogins(userId)
      +getUserStats(userId)
    }

    class ApiAdminService {
      +generatedAdminEndpoints
    }

    class UiNotificationService {
      +notificationsSignal
      +success/info/warning/error()
      +dismiss(id)
    }

    class ConfirmDialogService {
      +stateSignal
      +confirm(options, action)
      +close()
    }

    AdminService --> ApiAdminService : wraps
    ConfirmDialogService --> UiNotificationService : complements

    note for AdminService "Typed facade for admin users, uploads, login history, and stats"
    note for UiNotificationService "Global user-facing status messages"
```

---

Angular services and generated API adapters used by the frontend.