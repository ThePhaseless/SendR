# Infrastruktura jako Kod (IaC) - SendR

Ten folder zawiera kod Terraform odpowiedzialny za zautomatyzowane budowanie i zarządzanie infrastrukturą chmurową na platformie DigitalOcean dla projektu SendR.

## 🏗️ Co udało się dotychczas zbudować (Stan obecny)

Zaprojektowaliśmy w pełni modułową architekturę, zgodną z najlepszymi praktykami "Infrastruktury jako Kodu", gotową do zautomatyzowanego wdrożenia przez GitHub Actions. 

Oto podsumowanie zrealizowanych kroków:

1. **Podział na środowiska (Environments):**
   * Utworzono odseparowane środowiska `dev`, `staging` oraz `prod`.
   * Stan infrastruktury (`.tfstate`) dla każdego środowiska jest bezpiecznie przechowywany w zdalnym buckecie (DO Spaces) w podfolderach.

2. **Zaprojektowano 4 Główne Moduły Chmurowe:**
   * `network_vpc` - Zabezpieczona, prywatna sieć dla Klastra K8s i Bazy Danych.
   * `kubernetes_doks` - Klaster DigitalOcean Kubernetes (DOKS), docelowo pod serwowanie Backendu i Frontendu (Angular/FastAPI).
   * `database_postgres` - Zarządzalny klaster bazy danych PostgreSQL.
   * `storage_spaces` - Bucket Object Storage dla przetrzymywania ciężkich plików użytkowników aplikacji SendR.
   * `dns_domain` - Zautomatyzowany moduł do zarządzania strefą DNS i subdomenami, przygotowany pod dynamiczne LoadBalancery z Klastra K8s.

3. **Zabezpieczenia i Stabilność:**
   * Kod został zwalidowany poleceniem `terraform validate` oraz sformatowany.
   * Wprowadzono `.gitignore` zabezpieczający przed wyciekiem wrażliwych danych (logów, .tfstate, haseł).
   * Dodano mechanizm "Fail-Safe" w module DNS – Terraform nie wyrzuca błędów (HTTP 404), dopóki rzeczywista domena i publiczny adres IP z K8s nie zostaną jawnie zadeklarowane.

4. **Automatyzacja CI/CD (GitHub Actions):**
   * Skonfigurowano rurociąg w `.github/workflows/terraform.yml`.
   * Potok jest przygotowany do automatycznego autoryzowania się za pomocą kluczy S3 i DO API. Wykonuje on walidację, plany wdrożeniowe (dla Pull Requestów) i wdrożenia na żywo (Apply) dla środowiska deweloperskiego.

## 🚀 Następne Kroki (TODO)

* [ ] Wykonanie przez CI/CD pierwszego udanego `terraform apply` (stworzenie "pustej" infrastruktury bazowej).
* [ ] Migracja aplikacji na nową bazę danych. Modyfikacja modeli SQLModel w `backend/` pod kątem pełnej kompatybilności z PostgreSQL (w miejsce SQLite).
* [ ] Wdrożenie Ingress controllera (Traefik) na Klastrze K8s w celu uzyskania zewnętrznego IP (Load Balancer).
* [ ] Ustawienie publicznego IP z K8s do modułu `dns_domain` i odpalenie Terraform ponownie, by ostatecznie przypiąć domenę SendR.
