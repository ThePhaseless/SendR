# 🚀 SendR - Instrukcja Konfiguracji od Zera (Step-by-Step)

Ten dokument jest przeznaczony dla osób, które po raz pierwszy konfigurują środowisko chmurowe dla projektu SendR. Zawiera on precyzyjne ścieżki do panelu DigitalOcean oraz gotowe bloki komend do skopiowania.

---

## 🛠️ WYMAGANIA WSTĘPNE

Zanim zaczniesz, upewnij się, że masz zainstalowane:
1. **Git**
2. **Python 3.11+**
3. **uv** (nowoczesny manager pakietów Pythona): `pip install uv`

---

## 🏗️ ETAP 1: Przygotowanie DigitalOcean (Gdzie szukać kluczy?)

Zaloguj się na [cloud.digitalocean.com](https://cloud.digitalocean.com/).

### 1.1 Tworzenie miejsca na pliki stanu (Spaces)
1. Z lewego menu wybierz: **Spaces Object Storage** -> **Create Spaces Bucket**.
2. Wybierz region: **Frankfurt (fra1)**.
3. Wybierz unikalną nazwę (np. `sendr-tfstate-twojeinicjaly`).
4. **Zapisz tę nazwę** - wpisz ją w `terraform/environments/*/backend.conf`.

### 1.2 Pobieranie Kluczy S3 (Spaces Keys)
1. Z lewego menu wybierz: **API** -> zakładka **Spaces Keys**.
2. Kliknij **Generate New Key**. Zapisz **Access Key** i **Secret Key**.

### 1.3 Pobieranie Tokenu API (PAT)
1. W menu **API** -> zakładka **Tokens/Keys**.
2. Kliknij **Generate New Token** (uprawnienia **Write**). Zapisz go.

### 1.4 Odblokowanie Twojego IP (Krytyczne!)
1. Wejdź w **Databases** -> wybierz swój klaster (np. `sendr-db-dev`).
2. Wejdź w **Settings** -> sekcja **Trusted Sources**.
3. Kliknij **Add Trusted Source** -> wybierz **"Add your current IP"** -> kliknij **Save**.

---

## 🔐 ETAP 2: Konfiguracja GitHub Secrets

W Twoim repozytorium GitHub (Settings -> Secrets and variables -> Actions) dodaj:
* `DO_PAT` (Z Etapu 1.3)
* `SPACES_ACCESS_KEY` (Z Etapu 1.2)
* `SPACES_SECRET_KEY` (Z Etapu 1.2)

---

## 🚀 ETAP 3: Budowa Infrastruktury

Wypchnij kod na gałąź `DO-implementation`:
```bash
git push origin DO-implementation
```
Poczekaj ok. 15 minut, aż GitHub Actions zbuduje klaster i bazę danych.

---

## 💾 ETAP 4: Pełna Konfiguracja i Start (PowerShell)

Gdy chmura już działa, wykonaj poniższe kroki w jednym oknie terminala.

### KROK 1: Przygotowanie terminala
Skopiuj i wklej poniższy blok, uzupełniając swoje dane (Connection String pobierzesz z zakładki "Connection Details" klastra bazy w DO):

```powershell
# 1. Dane z DigitalOcean (Connection String)
# PAMIĘTAJ: na końcu musi być ?sslmode=require
$env:DATABASE_URL="postgresql://doadmin:HASLO@HOST:PORT/sendr?sslmode=require"

# 2. Klucze Spaces (S3)
$env:SPACES_ACCESS_KEY="TWÓJ_ACCESS_KEY"
$env:SPACES_SECRET_KEY="TWÓJ_SECRET_KEY"
$env:SPACES_BUCKET_NAME="sendr-app-data-dev-fra1"
$env:SPACES_REGION="fra1"

# 3. Konfiguracja Systemowa (Kopie dla aplikacji)
$env:SENDR_DATABASE_URL=$env:DATABASE_URL
$env:SENDR_SPACES_ACCESS_KEY=$env:SPACES_ACCESS_KEY
$env:SENDR_SPACES_SECRET_KEY=$env:SPACES_SECRET_KEY
$env:SENDR_SPACES_BUCKET_NAME=$env:SPACES_BUCKET_NAME
$env:SENDR_ENVIRONMENT="local"
$env:PYTHONPATH="backend/src"
```

### KROK 2: Inicjalizacja Systemu (Jednorazowo)
```powershell
cd backend
uv sync
uv add argon2-cffi
# Stworzenie tabel w chmurze
uv run alembic upgrade head
```

### KROK 3: Migracja i Start
```powershell
# 1. Przenieś stare dane (opcjonalnie)
uv run --project . python ../scripts/migrate_sqlite_to_postgres.py
uv run --project . python ../scripts/sync_files_to_spaces.py

# 2. Odblokuj port 8000 (na wszelki wypadek)
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess -ErrorAction SilentlyContinue | Stop-Process -Force

# 3. Uruchom aplikację
uv run uvicorn app:app --reload --app-dir src
```

---

## 🧪 ETAP 5: Testowanie w Swaggerze (Scenariusz Sukcesu)

1. Otwórz: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
2. **Zaloguj się:** Sekcja `dev` -> `POST /api/dev/login/premium` -> Try it out -> wpisz `premium` -> **Execute**. (Powinieneś dostać Code 200).
3. **Uploaduj:** Sekcja `files` -> `POST /api/files/upload`.
    * Wybierz plik.
    * **Wyczyść wszystkie pola tekstowe** (usuń słowo "string" z altcha, emails, passwords, title, description).
    * Kliknij **Execute**.
4. **Wynik:** Otrzymasz **Code 201**. W terminalu zobaczysz `INFO: STORAGE: Storing file ... in S3`.
