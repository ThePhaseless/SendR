# 🚀 SendR - Kompleksowa Instrukcja Wdrożenia i Administracji

Ten dokument zawiera szczegółową instrukcję konfiguracji, wdrożenia oraz zarządzania profesjonalną infrastrukturą chmurową SendR na platformie DigitalOcean.

---

## 🏗️ ARCHITEKTURA DOCELOWA

- **3 Odizolowane Klastry:** DEV, STAGING, PROD (osobne klastry K8s i bazy danych).
- **Bezpieczeństwo:** Izolacja NetworkPolicy, RBAC, Firewall bazy danych (Trusted Sources).
- **Automatyzacja:** Pełne CI/CD (GitHub Actions) z autoryzacją przez GitHub App (Bot).
- **SSL/TLS:** Automatyczne certyfikaty Let's Encrypt zarządzane przez Traefik.

---

## 🏁 KROK 0: ZASOBY TWORZONE RĘCZNIE (Tylko raz)

Zanim uruchomisz automatyzację, musisz ręcznie przygotować "fundamenty", których Terraform nie może stworzyć sam (ponieważ sam z nich korzysta).

### 0.1 Bucket na stan Terraforma (S3 State)
Terraform musi gdzieś bezpiecznie przechowywać informację o tym, co już zbudował.
1. Zaloguj się na [cloud.digitalocean.com](https://cloud.digitalocean.com).
2. Przejdź do **Spaces Object Storage** -> **Create Spaces Bucket**.
3. **Region:** Frankfurt (fra1).
4. **Nazwa:** Musi być unikalna, np. `sendr-tfstate-twójnick`.
5. **Ważne:** Zaktualizuj tę nazwę w plikach `terraform/environments/*/backend.conf` w linii `bucket = "..."`.

### 0.2 Konfiguracja Domeny u Rejestratora
1. Dodaj domenę (np. `sendr.email`) w DigitalOcean: **Networking -> Domains -> Add Domain**.
2. Zaloguj się tam, gdzie kupiłeś domenę i zmień serwery DNS (Nameservers) na:
   - `ns1.digitalocean.com`
   - `ns2.digitalocean.com`
   - `ns3.digitalocean.com`

### 0.3 Weryfikacja Domeny w Resend.com (Dla e-maili)
1. Załóż konto na [resend.com](https://resend.com).
2. Wejdź w zakładkę **Domains** -> **Add Domain**.
3. Resend poda Ci 3-4 rekordy DNS (TXT/MX). **Wpisz je do panelu DigitalOcean** (Networking -> Domains -> Twoja Domena), aby e-maile nie trafiały do spamu.

---

## 🛠️ ETAP 1: Przygotowanie Kluczy i Tokenów

### 1.1 Klucze Spaces (S3)
1. W panelu DO wybierz: **API** -> zakładka **Spaces Keys**.
2. Kliknij **Generate New Key**. Zapisz **Access Key** i **Secret Key**.

### 1.2 Token API (PAT)
1. W menu **API** -> zakładka **Tokens/Keys**.
2. Kliknij **Generate New Token** (uprawnienia **Write**). Zapisz go.

---

## 🔐 ETAP 2: Konfiguracja GitHub App (Bot GHCR)

Aby klastry mogły pobierać obrazy bez haseł PAT:
1. Przejdź do **GitHub Settings** -> **Developer settings** -> **GitHub Apps** -> **New GitHub App**.
2. **App name**: `SendR-Deploy-Bot-TwojNick`.
3. **Webhook**: Odznacz pole **Active**.
4. **Permissions**: **Repository permissions -> Packages -> Access: Read-only**.
5. Kliknij **Create GitHub App**.
6. Wygeneruj **Private Key** (plik `.pem`), zanotuj **App ID** oraz **Installation ID** (po instalacji na repozytorium).

---

## 🔑 ETAP 3: GitHub Secrets

W repozytorium (Settings -> Secrets and variables -> Actions) dodaj:
* `DO_PAT`, `SPACES_ACCESS_KEY`, `SPACES_SECRET_KEY`
* `GH_APP_ID`, `GH_APP_INSTALLATION_ID`, `GH_APP_PRIVATE_KEY`

---

## ⚙️ ETAP 4: Konfiguracja Środowisk (.tfvars)

Uzupełnij pliki `terraform/environments/*/terraform.tfvars`:
- `domain_name = "sendr.email"`
- `app_secret_key = "..."` (wygeneruj: `openssl rand -base64 32`)
- `resend_api_key = "re_..."`
- `spaces_access_key` i `spaces_secret_key` (te same co w Etapie 1.1)

---

## 🚀 ETAP 5: Wdrożenie (GitFlow)

- **DEV:** Push na `main` lub `DO-implementation`.
- **STAGING:** Push na gałąź `release/*`.
- **PROD:** Push Taga wersji (np. `v1.0.0`).

---

## 💾 ETAP 6: Migracja Danych i Plików

### 6.1 Przygotowanie terminala (PowerShell)
```powershell
$env:DATABASE_URL="postgresql+asyncpg://doadmin:HASLO@HOST:PORT/sendr?sslmode=require"
$env:SPACES_ACCESS_KEY="..."
$env:SPACES_SECRET_KEY="..."
$env:SPACES_BUCKET_NAME="sendr-app-data-dev-fra1"
$env:SENDR_DATABASE_URL=$env:DATABASE_URL
$env:SENDR_ENVIRONMENT="dev"
$env:PYTHONPATH="backend/src"
```

### 6.2 Uruchomienie skryptów
```powershell
cd backend
uv sync
uv run --project . python ../scripts/migrate_sqlite_to_postgres.py
uv run --project . python ../scripts/sync_files_to_spaces.py
```

---

## 📊 ETAP 7: Diagnostyka (Po wdrożeniu)

### 7.1 Firewall Bazy Danych
Domyślnie tylko klaster K8s ma dostęp. Aby uruchomić skrypty z punktu 6.2, musisz dodać swoje IP w panelu DO: **Databases -> Settings -> Trusted Sources**.

### 7.2 Logi i SSL
- **Pody:** `kubectl get pods -n sendr`
- **SSL:** `kubectl logs -l app=traefik -n sendr | grep "ACME"`
- **Backend:** `kubectl logs -l app=sendr-backend -n sendr -f`
