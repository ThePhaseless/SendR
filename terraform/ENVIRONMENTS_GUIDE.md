# Przewodnik po Środowiskach i CI/CD (GitHub Actions)

Ten dokument wyjaśnia, jak dokładnie działa automatyzacja (CI/CD) w naszym projekcie i w jaki sposób kod zamienia się na fizyczną infrastrukturę w DigitalOcean w zależności od środowiska.

Wdrożyliśmy architekturę opartą na **GitOps**. Oznacza to, że to co znajduje się w Git, bezpośrednio odzwierciedla to, co działa na serwerach, a zmiany w chmurze są wprowadzane **wyłącznie** poprzez akcje na odpowiednich gałęziach.

Nasz projekt jest podzielony na 3 niezależne środowiska. Każde środowisko ma swój własny stan infrastruktury i własny dedykowany potok (pipeline) w folderze `.github/workflows/`.

---

## 🟢 Środowisko DEV (Development)
**Plik rurociągu:** `terraform-dev.yml`

Jest to środowisko robocze, najczęściej aktualizowane. Służy programistom do ciągłego testowania nowych funkcji.

* **Kiedy Terraform generuje PLAN (sprawdza zmiany):** 
  Za każdym razem, gdy otworzysz Pull Request do gałęzi `main`. Potok sprawdza, co nowy kod zmieniłby w chmurze i wrzuca wynik (Plan) jako komentarz pod Pull Requestem.
* **Kiedy Terraform robi APPLY (wdraża na żywo):** 
  Za każdym razem, gdy zatwierdzisz Pull Request i zmergujesz kod do gałęzi `main` (lub gdy po prostu zrobisz bezpośredni `git push origin main`).

**Jak opublikować na DEV?**
```bash
git checkout main
git add .
git commit -m "feat: nowa baza"
git push origin main
```

---

## 🟡 Środowisko STAGING (Przedprodukcja)
**Plik rurociągu:** `terraform-staging.yml`

To środowisko służy jako "próba generalna" przed produkcją. Powinno być odzwierciedleniem 1:1 tego, co chcemy wypuścić dla klientów. Służy dla testerów (QA) i ostatecznej akceptacji.

* **Kiedy uruchamia się potok STAGING:**
  Gdy wypychasz kod na gałąź, która w nazwie zaczyna się od słowa `release/` (np. `release/v1.2.0`).

**Jak opublikować na STAGING?**
Gdy kod na `main` jest gotowy do testów akceptacyjnych:
```bash
git checkout main
git checkout -b release/v1.2.0
git push origin release/v1.2.0
```
*(GitHub Actions wykryje przedrostek `release/` i automatycznie utworzy klastry dla Stagingu)*

---

## 🔴 Środowisko PROD (Produkcja)
**Plik rurociągu:** `terraform-prod.yml`

Docelowe, na żywo działające środowisko z prawdziwymi klientami. Jest ono maksymalnie restrykcyjne. Żaden bezpośredni `git push` nie podmieni tutaj infrastruktury.

* **Kiedy uruchamia się potok PROD:**
  Wdrażanie na produkcję jest wyzwalane **wyłącznie poprzez tworzenie Tagów** zaczynających się od litery `v` (np. `v1.2.0`). Tagi to swoiste "zakładki" w historii Git, które oznaczają konkretne, nienaruszalne wydanie.

**Jak opublikować na PROD?**
Gdy środowisko STAGING przeszło testy i chcesz wypuścić nową wersję do klientów:
```bash
git checkout main
# Zrób merge z gałęzi release (jeśli tam były poprawki)
git tag v1.2.0
git push origin v1.2.0
```
*(GitHub Actions zignoruje zwykłe pliki i gałęzie. Wykryje tylko fakt wrzucenia Taga 'v1.2.0' i wdroży ten dokładnie zamrożony kod prosto do środowiska produkcyjnego).*

---

### Dodatkowa Ochrona Produkcji (Manual Approval)
Potok `terraform-prod.yml` posiada specjalny atrybut `environment: production`. 
Dzięki temu, nawet jeśli ktoś wrzuci tag `v...`, możesz w ustawieniach repozytorium GitHub wymusić **Manual Approval**.

**Jak to włączyć?**
1. Na GitHubie wejdź w **Settings** -> **Environments**.
2. Kliknij **New environment** i nazwij je `production`.
3. Zaznacz pole **Required reviewers** i dodaj siebie.
4. Od teraz, gdy rurociąg produkcyjny wystartuje, zatrzyma się w połowie i wyśle Ci maila. Dopiero po kliknięciu przez Ciebie "Approve" na GitHubie, Terraform zmodyfikuje infrastrukturę chmurową.
