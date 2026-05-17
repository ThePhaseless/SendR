# 🚀 SendR - Kompleksowa Instrukcja Wdrożenia i Administracji

Ten dokument opisuje proces pełnej konfiguracji, wdrożenia oraz bieżącego zarządzania profesjonalną infrastrukturą chmurową projektu SendR na platformie DigitalOcean.

---

## 🏗️ ARCHITEKTURA DOCELOWA

- **3 Odizolowane Klastry:** DEV, STAGING, PROD.
- **Bezpieczeństwo:** RBAC, NetworkPolicies, Firewall bazy danych (Trusted Sources).
- **Automatyzacja:** Pełne CI/CD (GitHub Actions) z użyciem GitHub App (Bot).
- **SSL:** Automatyczny Let's Encrypt przez Traefik Ingress Controller.

---

## 🔐 ETAP 1: Przygotowanie GitHub i Chmury

### 1.1 DigitalOcean Keys
1. **Spaces Keys:** Wygeneruj w API -> Spaces Keys (Access & Secret).
2. **DO Token (PAT):** Wygeneruj w API -> Tokens (z uprawnieniami Write).
3. **Domain:** Dodaj `sendr.email` w Networking -> Domains i ustaw NS u rejestratora na DigitalOcean.

### 1.2 GitHub App (Bot GHCR)
1. Stwórz nową **GitHub App** (np. `SendR-Deploy-Bot`).
2. Uprawnienia: **Packages -> Read-only**.
3. Zainstaluj na repozytorium i pobierz **Private Key**, **App ID** oraz **Installation ID**.

### 1.3 GitHub Secrets
Dodaj w Settings -> Secrets -> Actions:
- `DO_PAT`, `SPACES_ACCESS_KEY`, `SPACES_SECRET_KEY`
- `GH_APP_ID`, `GH_APP_INSTALLATION_ID`, `GH_APP_PRIVATE_KEY`

---

## ⚙️ ETAP 2: Konfiguracja Lokalna i Środowiska

### 2.1 Pliki .tfvars
Uzupełnij `terraform/environments/*/terraform.tfvars`. Te pliki są ignorowane przez Git.
```hcl
domain_name    = "sendr.email"
app_secret_key = "..." # Wygeneruj: openssl rand -base64 32
resend_api_key = "re_..."
spaces_access_key = "..."
spaces_secret_key = "..."
smtp_password     = "..."
```

---

## 🚀 ETAP 3: Wdrożenie i GitFlow

Zrób `git push` na odpowiednią gałąź:
- **`main` / `DO-implementation`** -> Wdraża na **DEV** (`dev.sendr.email`)
- **`release/*`** -> Wdraża na **STAGING** (`staging.sendr.email`)
- **`v*` (Tag)** -> Wdraża na **PROD** (`sendr.email`)

---

## 💾 ETAP 4: Administracja i Migracja Danych (PowerShell)

Jeśli chcesz uruchomić skrypty migracyjne lub zarządzać bazą z Twojego komputera, wykonaj poniższe kroki.

### 4.1 Przygotowanie połączenia
Skopiuj dane bazy z panelu DO (Connection Details) i ustaw zmienne w terminalu:

```powershell
# 1. Dane bazy chmurowej (wymagane ?sslmode=require)
$env:DATABASE_URL="postgresql+asyncpg://doadmin:HASLO@HOST:PORT/sendr?sslmode=require"

# 2. Dane Spaces (S3)
$env:SPACES_ACCESS_KEY="..."
$env:SPACES_SECRET_KEY="..."
$env:SPACES_BUCKET_NAME="sendr-app-data-dev-fra1"

# 3. Konfiguracja lokalna
$env:SENDR_DATABASE_URL=$env:DATABASE_URL
$env:SENDR_ENVIRONMENT="dev"
$env:PYTHONPATH="backend/src"
```

### 4.2 Uruchomienie skryptów
```powershell
cd backend
uv sync

# Migracja bazy (SQLite -> Cloud Postgres)
uv run --project . python ../scripts/migrate_sqlite_to_postgres.py

# Synchronizacja plików (Uploads -> Cloud S3)
uv run --project . python ../scripts/sync_files_to_spaces.py
```

---

## 📊 ETAP 5: Diagnostyka (Po wdrożeniu)

### 5.1 Logi aplikacji w klastrze
Aplikacja automatycznie wykonuje `alembic upgrade head` przy starcie.
```bash
doctl kubernetes cluster kubeconfig save sendr-k8s-dev
kubectl get pods -n sendr
kubectl logs -l app=sendr-backend -n sendr -f
```

### 5.2 Status SSL (Traefik)
```bash
kubectl logs -l app=traefik -n sendr | grep "ACME"
```

---

## 🧪 ETAP 6: Testy Poprawności

1. **API:** `https://api.dev.sendr.email/health` -> `{"status": "ok"}`.
2. **Swagger:** `https://api.dev.sendr.email/docs`.
3. **Frontend:** `https://dev.sendr.email`.
