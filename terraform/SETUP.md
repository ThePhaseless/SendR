# 🚀 SendR - Instrukcja Konfiguracji od Zera (Step-by-Step)

Ten dokument jest przeznaczony dla osób, które po raz pierwszy konfigurują środowisko chmurowe dla projektu SendR. Zawiera on precyzyjne ścieżki do panelu DigitalOcean oraz gotowe bloki komend do skopiowania.

---

## 🛠️ WYMAGANIA WSTĘPNE

Zanim zaczniesz, upewnij się, że masz zainstalowane:
1. **Git**
2. **Python 3.11+**
3. **uv** (nowoczesny manager pakietów Pythona): `pip install uv`
4. **Terraform** (opcjonalnie, do testów lokalnych IaC)

---

## 🏗️ ETAP 1: Przygotowanie DigitalOcean (Gdzie szukać kluczy?)

Zaloguj się na [cloud.digitalocean.com](https://cloud.digitalocean.com/).

### 1.1 Tworzenie miejsca na pliki stanu (Spaces)
Terraform musi współdzielić stan infrastruktury z GitHubem.
1. Z lewego menu wybierz: **Spaces Object Storage**.
2. Kliknij: **Create Spaces Bucket**.
3. Wybierz region: **Frankfurt (fra1)**.
4. Wybierz unikalną nazwę (np. `sendr-tfstate-twojeinicjaly`).
5. **Zapisz tę nazwę** - musisz ją wpisać do plików `terraform/environments/*/backend.conf` w polu `bucket`.
6. Kliknij **Create a Spaces Bucket**.

### 1.2 Pobieranie Kluczy S3 (Spaces Keys)
Służą one do autoryzacji zapisu plików stanu oraz plików użytkowników.
1. Z lewego menu wybierz: **API**.
2. Kliknij zakładkę na górze: **Spaces Keys**.
3. Kliknij przycisk: **Generate New Key**.
4. Wpisz nazwę (np. `SendR-Admin`) i kliknij zielony ptaszek.
5. **SKOPIUJ OD RAZU:**
   * **Access Key** (np. `DO00PV...`)
   * **Secret Key** (wyświetla się tylko raz!)

### 1.3 Pobieranie Tokenu API (PAT)
Służy do tworzenia klastrów K8s i baz danych.
1. W tym samym menu **API**, zostań w zakładce: **Tokens/Keys**.
2. Kliknij: **Generate New Token**.
3. Nazwa: `Terraform-GitHub`.
4. Uprawnienia: Zaznacz **Write** (zapis).
5. Wygaśnięcie: **No expiration** (zalecane dla CI/CD).
6. **SKOPIUJ TOKEN** (zaczyna się od `dop_v1_...`).

---

## 🔐 ETAP 2: Konfiguracja GitHub Secrets

Przejdź do swojego repozytorium na GitHubie.
1. Kliknij zakładkę: **Settings** (u góry).
2. Z lewego menu wybierz: **Secrets and variables** -> **Actions**.
3. Kliknij: **New repository secret** dla każdego z poniższych:

| Nazwa (Name) | Wartość (Value) | Skąd wziąć? |
| :--- | :--- | :--- |
| `DO_PAT` | `dop_v1_...` | Z Etapu 1.3 |
| `SPACES_ACCESS_KEY` | `DO00PV...` | Z Etapu 1.2 |
| `SPACES_SECRET_KEY` | `twój_długi_klucz` | Z Etapu 1.2 |

---

## 🚀 ETAP 3: Budowa Infrastruktury

Wpisz w terminalu na swoim komputerze:

```bash
git checkout DO-implementation
git push origin DO-implementation
```

**Co się teraz dzieje?**
1. Przejdź do zakładki **Actions** w GitHubie.
2. Zobaczysz uruchomiony potok `Terraform CI/CD (DEV)`.
3. Poczekaj ok. 15 minut. Gdy skończy, DigitalOcean wybuduje dla Ciebie bazę i klaster.

---

## 💾 ETAP 4: Migracja Danych (Local -> Cloud)

Gdy infrastruktura jest gotowa, musisz pobrać dane dostępowe do nowej bazy, aby przenieść do niej lokalnych użytkowników.

### 4.1 Pobranie URL bazy danych
1. W DigitalOcean wejdź w: **Databases**.
2. Kliknij w: `sendr-db-dev`.
3. W sekcji **Overview** znajdź ramkę **Connection Details**.
4. Wybierz z list rozwijanych:
   * **User:** `doadmin`
   * **Database:** `sendr`
   * **Network:** **Public Network** (ważne dla migracji z domu!).
5. Wybierz format: **Connection string** i skopiuj go.

### 4.2 Uruchomienie komend migracji (PowerShell)
Otwórz terminal w głównym folderze `SendR` i wklej (podmień `...` na swoje dane):

```powershell
# 1. Ustaw zmienne środowiskowe
$env:DATABASE_URL="WLEJ_TUTAJ_SKOPIOWANY_CONNECTION_STRING_I_DODAJ_+asyncpg_PO_POSTGRESQL"
# Przykład: postgresql+asyncpg://doadmin:haslo@host:port/sendr

$env:SPACES_ACCESS_KEY="TWÓJ_ACCESS_KEY"
$env:SPACES_SECRET_KEY="TWÓJ_SECRET_KEY"
$env:SPACES_BUCKET_NAME="sendr-app-data-dev-fra1"
$env:PYTHONPATH="backend/src"

# 2. Zainstaluj zależności i zmigruj rekordy (Użytkownicy itp.)
cd backend
uv sync
uv run python ../scripts/migrate_sqlite_to_postgres.py

# 3. Wyślij stare pliki z dysku lokalnego do chmury S3
uv run python ../scripts/sync_files_to_spaces.py
```

---

## 💻 ETAP 5: Uruchomienie Aplikacji w Trybie Chmury

Jeśli chcesz pracować nad kodem lokalnie, ale korzystać z bazy i plików w DigitalOcean:

```powershell
# Będąc w folderze 'backend'
$env:SENDR_DATABASE_URL=$env:DATABASE_URL
$env:SENDR_SPACES_ACCESS_KEY=$env:SPACES_ACCESS_KEY
$env:SENDR_SPACES_SECRET_KEY=$env:SPACES_SECRET_KEY
$env:SENDR_SPACES_BUCKET_NAME=$env:SPACES_BUCKET_NAME
$env:PYTHONPATH="src"

uv run uvicorn app:app --reload --app-dir src
```

**Weryfikacja:** 
Otwórz [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Jeśli widzisz listę endpointów, gratulacje! Twój lokalny komputer jest teraz połączony z profesjonalną chmurą.

---

## ❓ Rozwiązywanie problemów (FAQ)

* **Błąd 404 na stronie głównej?** To normalne. Backend to API. Wejdź na `/docs`.
* **Błąd "invalid version slug" w GitHub Actions?** Wypchnij najnowszy kod z gałęzi `DO-implementation`, poprawiliśmy to w module Kubernetes.
* **Błąd "unable to open database file"?** Skrypt migracji nie widzi pliku `sendr.db`. Upewnij się, że uruchamiasz komendy z odpowiedniego folderu zgodnie z Etapem 4.2.
