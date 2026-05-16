# Przewodnik Konfiguracji (Setup Guide)

Ten dokument opisuje krok po kroku, jak przygotować środowisko chmurowe DigitalOcean i repozytorium GitHub do automatycznego wdrażania infrastruktury przy pomocy Terraform.

Wykonaj te czynności **tylko raz** dla całego projektu.

---

## KROK 1: Przygotowanie platformy DigitalOcean

Aby Terraform miał gdzie zapisywać swój bezpieczny stan i mógł tworzyć serwery, musimy najpierw manualnie utworzyć miejsce na ten stan oraz pobrać odpowiednie klucze.

### 1.1 Tworzenie miejsca na pliki stanu (DO Spaces)
1. Zaloguj się do panelu [DigitalOcean](https://cloud.digitalocean.com/).
2. W lewym menu wybierz **Spaces Object Storage**.
3. Kliknij **Create Spaces Bucket**.
4. Wybierz region: **Frankfurt (fra1)** (lub inny, o ile zmienisz to w plikach konfiguracyjnych).
5. Wybierz unikalną nazwę, np. `sendr-tfstate-12345`.
   * *Ważne:* Ta nazwa musi być wpisana w plikach `terraform/environments/*/backend.conf`.
6. Ustaw "File Listing" na **Restrict File Access** (Prywatne!).
7. Kliknij **Create a Spaces Bucket**.

### 1.2 Generowanie kluczy do Spaces (Klucze S3)
1. W lewym menu panelu DO kliknij **API** (na samym dole).
2. Na górze strony przejdź do zakładki **Spaces Keys**.
3. Kliknij **Generate New Key** i nazwij go np. `terraform-state`.
4. Platforma pokaże Ci dwa klucze:
   * **Access Key** (krótszy).
   * **Secret** (dłuższy). 
   * ⚠️ **Zapisz "Secret" od razu**, ponieważ wyświetla się on tylko raz!

### 1.3 Generowanie głównego Tokenu API
1. Wróć do menu **API** i przejdź do zakładki **Personal access tokens** (domyślna).
2. Kliknij **Generate New Token**.
3. Nazwij go np. `terraform-admin`.
4. Wybierz uprawnienia **Write** i ustaw czas wygaśnięcia (np. No expiration).
5. Kliknij **Generate Token**.
6. ⚠️ **Zapisz ten token**, zaczyna się on zazwyczaj od `dop_v1_...`.

---

## KROK 2: Konfiguracja GitHub Actions

Zdobyliśmy 3 wartości z DigitalOcean. Teraz musimy je bezpiecznie przekazać do GitHuba, aby automatyczne skrypty (CI/CD) mogły logować się w naszym imieniu.

1. Wejdź na stronę swojego repozytorium na **GitHubie**.
2. Pod nazwą repozytorium kliknij w zakładkę **Settings** (Ustawienia).
3. W lewym bocznym menu rozwiń **Secrets and variables** i kliknij **Actions**.
4. W sekcji "Repository secrets" dodaj 3 nowe sekrety klikając **New repository secret**:

| Nazwa Sekretu (Name) | Wartość (Secret) | Skąd wziąć? |
| :--- | :--- | :--- |
| `DO_PAT` | Wklej token zaczynający się od `dop_v1_...` | Wygenerowany w Kroku 1.3 |
| `SPACES_ACCESS_KEY` | Wklej krótki klucz Access Key | Wygenerowany w Kroku 1.2 |
| `SPACES_SECRET_KEY` | Wklej długi klucz Secret Key | Wygenerowany w Kroku 1.2 |

*Upewnij się, że podczas wklejania na początku lub na końcu kluczy nie ma spacji!*

---

## KROK 3: Uruchomienie Automatyzacji

Gdy powyższe kroki zostaną wykonane, cała magia dzieje się sama!

1. Na swoim komputerze wyślij kod na GitHuba:
   ```bash
   git push origin <nazwa-galezi>
   ```
2. Przejdź do zakładki **Actions** w GitHubie. Zobaczysz uruchomiony potok "Terraform CI/CD".
3. Jeśli wysyłasz kod na gałąź inną niż `main`, potok jedynie **zaplanuje** infrastrukturę (Terraform Plan). Wynik zobaczysz w logach oraz jako komentarz do Pull Requesta.
4. Gdy kod trafi na gałąź domyślną (np. zrobisz merge do `main` lub wypchniesz nasz specjalny kod na `DO-implementation`), potok dodatkowo wykona operację **Apply**, co fizycznie powoła w chmurze klaster Kubernetes, bazę danych PostgreSQL oraz sieć VPC.
