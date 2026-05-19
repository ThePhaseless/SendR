# Reference Schemas & Request Bodies

Generated request-body and parameter names are abbreviated in the diagram. Notes keep the API operation mapping without forcing Mermaid to render very long class names.

```mermaid
classDiagram
    direction LR

    class UploadFileBody {
      +file: Blob
      +accessOptions
      +metadataFields
      +altcha: string optional
    }

    class UploadManyBody {
      +files: Blob array
      +accessOptions
      +metadataFields
      +altcha: string optional
    }

    class AddToGroupBody {
      +files: Blob array
      +altcha: string optional
    }

    class FileDownloadParams {
      +token: string
    }

    class GroupDownloadParams {
      +upload_group: string
    }

    class ListUsersParams {
      +page: number optional
      +per_page: number optional
      +search: string optional
    }

    class RefreshLinkParams {
      +expiry_hours: number optional
      +max_downloads: number optional
    }

    class RecipientStatsParams {
      +upload_group: string
    }

    class MessageResponse {
      +message: string
    }

    class HTTPValidationError {
      +detail: ValidationError array optional
    }

    class ValidationError {
      +loc: string array
      +msg: string
      +type: string
    }

    class ValidationErrorCtx {
      +ctx: Record optional
    }

    class AltchaChallengeResponse {
      +challenge: string
      +salt: string
      +algorithm: string
      +signature: string
    }

    HTTPValidationError --> ValidationError : contains
    ValidationErrorCtx --> ValidationError : extends

    note for UploadFileBody "Generated name: BodyUploadFileApiFilesUploadPost"
    note for UploadManyBody "Generated name: BodyUploadMultipleFilesApiFilesUploadMultiplePost"
    note for AddToGroupBody "Generated name: BodyAddFilesToGroupApiFilesGroupUploadGroupAddPost"
    note for MessageResponse "Shared shape for simple success responses"
    note for AltchaChallengeResponse "Generated ALTCHA challenge response"
```

---

Reference request bodies, query/path parameter shapes, validation errors, and simple generated response types.