# Infrastruktura jako Kod (IaC) - SendR

Ten folder zawiera kod Terraform odpowiedzialny za zautomatyzowane budowanie i zarządzanie infrastrukturą chmurową na platformie DigitalOcean dla projektu SendR.

## 🏗️ Co udało się dotychczas zbudować (Stan obecny)

Zaprojektowaliśmy w pełni modułową architekturę, zgodną z najlepszymi praktykami "Infrastruktury jako Kodu", gotową do zautomatyzowanego wdrożenia przez GitHub Actions. 

Oto podsumowanie zrealizowanych kroków:

1. **Podział na środowiska (Environments):**
   * Utworzono odseparowane środowiska `dev`, `staging` oraz `prod`.
   * Stan infrastruktury (`.tfstate`) dla każdego środowiska jest bezpiecznie przechowywany w zdalnym buckecie (DO Spaces) w podfolderach.

2. **Zaprojektowano i wdrożono Moduły Chmurowe:**
   * `network_vpc` - Zabezpieczona, prywatna sieć dla Klastra K8s i Bazy Danych.
   * `database_postgres` - Zarządzalny klaster bazy danych PostgreSQL.
   * `storage_spaces` - Bucket Object Storage dla plików użytkowników (S3 compatible).
   * `kubernetes_doks` - Klaster DigitalOcean Kubernetes (DOKS), na którym działa aplikacja.
   * `dns_domain` - Moduł przygotowany pod dynamiczne przypisywanie domen.

3. **Zabezpieczenia i Stabilność:**
   * Kod zwalidowany i sformatowany.
   * Wprowadzono `.gitignore` zabezpieczający przed wyciekiem wrażliwych danych.
   * Klaster Kubernetes posiada dynamiczne pobieranie wersji z bezpiecznym fallbackiem.

4. **Migracja i Obsługa Cloud-Native:**
   * Backend (FastAPI) wspiera teraz natywnie PostgreSQL i DigitalOcean Spaces.
   * Stworzono skrypty migracyjne w `scripts/` do przenoszenia danych ze starego SQLite do nowej chmury.

## 🚀 Następne Kroki (TODO)

* [ ] **Konteneryzacja:** Budowa obrazów Docker dla frontendu i backendu.
* [ ] **Rejestr Obrazów:** Konfiguracja GitHub Container Registry (GHCR).
* [ ] **Kubernetes Manifests:** Przygotowanie plików Kustomize do wdrożenia aplikacji na klaster.
* [ ] **Ingress & TLS:** Wdrożenie Traefika z certyfikatami Let's Encrypt.
* [ ] **Domeny:** Ostateczne przypięcie domeny `sendr.com` do IP klastra.
