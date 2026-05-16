# 🚀 SendR - Kompleksowy Przewodnik Wdrożeniowy

Ten dokument to jedyne źródło prawdy dla osoby, która chce uruchomić projekt SendR w chmurze DigitalOcean od zera. Zawiera kroki od konfiguracji panelu, przez sekrety GitHub, aż po migrację danych.

---

## 🏗️ ETAP 1: Przygotowanie DigitalOcean (Manualnie)

Zanim automatyzacja ruszy, musisz przygotować "wejście" dla Terraform.

### 1.1 Miejsce na stan infrastruktury (Spaces)
1. Zaloguj się do [DigitalOcean](https://cloud.digitalocean.com/).
2. Wejdź w **Spaces Object Storage** -> **Create Spaces Bucket**.
3. Region: **Frankfurt (fra1)**.
4. Nazwa: Dowolna unikalna (np. `sendr-tfstate-twójnick`).
5. Dostęp: **Restrict File Access** (Prywatny).
6. **WAŻNE:** Wpisz tę nazwę w plikach `terraform/environments/*/backend.conf` w polu `bucket`.

### 1.2 Klucze dostępowe
1. Wejdź w zakładkę **API** (lewe menu).
2. **Spaces Keys:** Wygeneruj nowy klucz (np. `GitHub-Terraform`). Zapisz **Access Key** i **Secret Key**.
3. **Personal Access Tokens:** Wygeneruj token (uprawnienia **Write**, brak wygasania). Zapisz go jako Twój główny API Token.

---

## 🔐 ETAP 2: Konfiguracja GitHub Secrets

W Twoim repozytorium GitHub wejdź w **Settings** -> **Secrets and variables** -> **Actions**. Dodaj 3 sekrety:

| Nazwa Sekretu | Wartość |
| :--- | :--- |
| `DO_PAT` | Główny token API DigitalOcean |
| `SPACES_ACCESS_KEY` | Access Key do Spaces (S3) |
| `SPACES_SECRET_KEY` | Secret Key do Spaces (S3) |

---

## 🚀 ETAP 3: Budowa Infrastruktury (IaC)

1. Wypchnij kod na gałąź `main` lub `DO-implementation`:
   ```bash
   git push origin DO-implementation
   ```
2. Obserwuj zakładkę **Actions** na GitHubie. Po ok. 15 minutach w panelu DigitalOcean zobaczysz:
   * **VPC:** `sendr-vpc-dev`
   * **Baza danych:** `sendr-db-dev` (PostgreSQL)
   * **Kubernetes:** `sendr-k8s-dev`
   * **Spaces:** `sendr-app-data-dev-fra1` (Dysk na pliki)

---

## 💾 ETAP 4: Migracja Danych (Local -> Cloud)

Gdy chmura już działa, musisz przenieść swoich użytkowników i pliki. Wykonaj to w terminalu **PowerShell** w głównym folderze projektu:

### 4.1 Dane Połączenia (Zmienne)
*Pobierz URL bazy z zakładki "Connection Details" w panelu DO (wybierz bazę 'sendr' i użytkownika 'doadmin').*
```powershell
# Baza Danych (Użyj prefixu postgresql+asyncpg://)
$env:DATABASE_URL="postgresql+asyncpg://user:password@host:port/sendr"

# S3 / Spaces
$env:SPACES_ACCESS_KEY="TWÓJ_ACCESS_KEY"
$env:SPACES_SECRET_KEY="TWÓJ_SECRET_KEY"
$env:SPACES_BUCKET_NAME="sendr-app-data-dev-fra1"

# Ścieżka dla importów Pythona
$env:PYTHONPATH="backend/src"
```

### 4.2 Uruchomienie Skryptów
```bash
# 1. Przeniesienie rekordów z SQLite do Postgres (Użytkownicy, Tagi itp.)
uv run --project backend python scripts/migrate_sqlite_to_postgres.py

# 2. Przesłanie fizycznych plików z folderu backend/uploads do chmury S3
uv run --project backend python scripts/sync_files_to_spaces.py
```

---

## 💻 ETAP 5: Uruchomienie Aplikacji Lokalnie (Tryb Chmury)

Aby sprawdzić czy aplikacja widzi dane w chmurze:
```powershell
cd backend
$env:PYTHONPATH="src"
# Mapowanie zmiennych na format aplikacji
$env:SENDR_DATABASE_URL=$env:DATABASE_URL
$env:SENDR_SPACES_ACCESS_KEY=$env:SPACES_ACCESS_KEY
$env:SENDR_SPACES_SECRET_KEY=$env:SPACES_SECRET_KEY
$env:SENDR_SPACES_BUCKET_NAME=$env:SPACES_BUCKET_NAME

uv run uvicorn app:app --reload --app-dir src
```
**Test:** Wejdź na [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Każdy nowy upload i download będzie teraz obsługiwany przez DigitalOcean Spaces!

---

## ⏭️ CO DALEJ?

Aktualnie zakończyliśmy przygotowanie kodu i bazy. Następne kroki to:
1. **Dockerfile:** Budowa kontenerów backendu i frontendu.
2. **Kustomize:** Przygotowanie manifestów Kubernetes.
3. **Traefik:** Konfiguracja domen i SSL (HTTPS).
