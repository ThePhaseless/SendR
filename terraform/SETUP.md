# Przewodnik Konfiguracji i Migracji (Setup & Migration Guide)

Ten dokument opisuje krok po kroku, jak przygotować środowisko chmurowe DigitalOcean, zmigrować stare dane i uruchomić aplikację SendR w trybie Cloud-Native.

---

## KROK 1: Przygotowanie platformy DigitalOcean

Wykonaj te czynności manualnie w panelu DO, aby Terraform mógł przejąć kontrolę.

1. **DO Spaces (State Bucket):** Utwórz bucket (np. `sendr-tfstate-12345`) w regionie `fra1`. Nazwę wpisz w `terraform/environments/*/backend.conf`.
2. **Spaces Keys:** W menu API -> Spaces Keys wygeneruj parę kluczy (Access & Secret).
3. **API Token:** W menu API -> Personal access tokens wygeneruj token z uprawnieniami **Write**.

---

## KROK 2: Konfiguracja GitHub Secrets

Dodaj poniższe klucze w ustawieniach repozytorium GitHub (Settings -> Secrets and variables -> Actions):

| Nazwa Sekretu | Opis |
| :--- | :--- |
| `DO_PAT` | Główny token API DigitalOcean |
| `SPACES_ACCESS_KEY` | Access Key do Spaces (S3) |
| `SPACES_SECRET_KEY` | Secret Key do Spaces (S3) |

---

## KROK 3: Wdrożenie Infrastruktury (IaC)

Wypchnij kod na gałąź `main` (lub `DO-implementation`), aby GitHub Actions zbudował:
* Prywatną sieć VPC.
* Klaster PostgreSQL.
* Bucket na pliki użytkowników.
* Klaster Kubernetes (DOKS).

---

## KROK 4: Migracja Danych (Local -> Cloud)

Gdy chmura już działa, przenieś dane ze starej bazy SQLite i dysku lokalnego.

### 4.1 Przygotowanie zmiennych
W terminalu PowerShell (lokalnie):
```powershell
$env:DATABASE_URL="postgresql+asyncpg://user:password@host:port/sendr"
$env:SPACES_ACCESS_KEY="TWOJE_KLUCZE"
$env:SPACES_SECRET_KEY="TWOJE_KLUCZE"
$env:SPACES_BUCKET_NAME="sendr-app-data-dev-fra1"
$env:PYTHONPATH="backend/src"
```

### 4.2 Uruchomienie skryptów ETL
Upewnij się, że jesteś w głównym folderze projektu:
```bash
# Migracja bazy danych
uv run --project backend python scripts/migrate_sqlite_to_postgres.py

# Migracja fizycznych plików do chmury S3
uv run --project backend python scripts/sync_files_to_spaces.py
```

---

## KROK 5: Uruchomienie lokalne w trybie Chmury

Aby przetestować, czy backend poprawnie rozmawia z nową bazą i S3:
```powershell
cd backend
$env:PYTHONPATH="src"
uv run uvicorn app:app --reload --app-dir src
```

*Aplikacja będzie teraz automatycznie wysyłać nowe pliki do DigitalOcean Spaces i używać Pre-signed URLs do pobierania.*
