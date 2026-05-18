# 🚀 SendR - Kompleksowa Instrukcja Wdrożenia i Administracji

Ten dokument zawiera szczegółową instrukcję konfiguracji, wdrożenia oraz zarządzania profesjonalną infrastrukturą chmurową SendR na platformie DigitalOcean.

---

## 🏗️ ARCHITEKTURA DOCELOWA

- **3 Odizolowane Klastry:** DEV, STAGING, PROD (osobne klastry K8s i bazy danych).
- **Bezpieczeństwo:** Izolacja NetworkPolicy, RBAC, Firewall bazy danych (Trusted Sources).
- **Automatyzacja:** GitHub Actions z sekretami repozytorium i środowisk GitHub.
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

## 🔑 ETAP 2: GitHub Secrets

W repozytorium (Settings -> Secrets and variables -> Actions) dodaj:
* `DEV_DO_TOKEN`, `STAGING_DO_TOKEN`, `PROD_DO_TOKEN`
* `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (DigitalOcean Spaces key pair)
* `SENDR_SECRET_KEY` (wygeneruj: `openssl rand -base64 32`)
* `SENDR_RESEND_API_KEY` albo komplet `SENDR_SMTP_HOST`, `SENDR_SMTP_PORT`, `SENDR_SMTP_USER`, `SENDR_SMTP_PASSWORD`

Sekrety produkcyjne najlepiej dodać jako sekrety środowiska GitHub (`dev`, `staging`, `prod`), aby wdrożenia mogły korzystać z innych wartości dla każdego środowiska.

Automatyczne deploymenty z gałęzi/tagów są wyłączone, dopóki zmienna repozytorium `SENDR_AUTO_DEPLOY_ENABLED` nie ma wartości `true`. Ręczne uruchomienie przez `workflow_dispatch` nadal działa po podaniu poprawnych sekretów.

---

## ⚙️ ETAP 3: Konfiguracja Środowisk

Pliki `terraform/environments/*/terraform.tfvars.example` zawierają tylko niesekretne wartości środowiskowe, takie jak domena, region i rozmiar klastra. Nie commituj plików `terraform.tfvars` z realnymi sekretami.

Backend stanu Terraform używa `terraform/environments/*/backend.conf`. W tych plikach trzymaj tylko niesekretne ustawienia, np. nazwę bucketa i klucz stanu. Dane dostępowe Spaces są przekazywane przez `AWS_ACCESS_KEY_ID` i `AWS_SECRET_ACCESS_KEY` z sekretów GitHub.

---

## 🚀 ETAP 4: Wdrożenie (GitFlow)

- **DEV:** Ręcznie uruchom `.github/workflows/terraform.yml` i `.github/workflows/deploy-k8s.yml` z opcją `dev`; push na `main` wdraża automatycznie tylko gdy `SENDR_AUTO_DEPLOY_ENABLED=true`.
- **STAGING:** Ręczne uruchomienie z opcją `staging`; gałąź `release/*` wdraża automatycznie tylko gdy `SENDR_AUTO_DEPLOY_ENABLED=true`.
- **PROD:** Ręczne uruchomienie z opcją `prod`; tag wersji (np. `v1.0.0`) wdraża automatycznie tylko gdy `SENDR_AUTO_DEPLOY_ENABLED=true`.

---

## 💾 ETAP 5: Migracja Danych i Plików

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

## 📊 ETAP 6: Diagnostyka (Po wdrożeniu)

### 7.1 Firewall Bazy Danych
Domyślnie tylko klaster K8s ma dostęp. Aby uruchomić skrypty z punktu 6.2, musisz dodać swoje IP w panelu DO: **Databases -> Settings -> Trusted Sources**.

### 7.2 Logi i SSL
- **Pody:** `kubectl get pods -n sendr`
- **SSL:** `kubectl logs -l app=traefik -n sendr | grep "ACME"`
- **Backend:** `kubectl logs -l app=sendr-backend -n sendr -f`
