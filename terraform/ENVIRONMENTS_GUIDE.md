# Przewodnik po środowiskach i CI/CD

Ten dokument opisuje, kiedy GitHub Actions waliduje kod Terraform, kiedy wykonuje realne zmiany w DigitalOcean i które gałęzie są traktowane jako wdrożeniowe.

Infrastruktura jest obsługiwana przez jeden wspólny workflow Terraform: `.github/workflows/terraform.yml`. Wdrożenie aplikacji do Kubernetes obsługuje `.github/workflows/deploy-k8s.yml`, a obrazy kontenerów buduje `.github/workflows/docker-publish.yml`.

## Gałęzie i środowiska

| Źródło uruchomienia | Środowisko | Zachowanie |
| --- | --- | --- |
| Pull request z plikami Terraform | brak | `terraform fmt`, `terraform init -backend=false`, `terraform validate` |
| `DO-implementation` | brak | walidacja Terraform bez `apply` i bez deploymentu Kubernetes |
| `main` | `dev` | build obrazów i walidacja; `apply` oraz deployment tylko gdy `SENDR_AUTO_DEPLOY_ENABLED=true` |
| `release/**` | `staging` | build obrazów i walidacja; `apply` oraz deployment tylko gdy `SENDR_AUTO_DEPLOY_ENABLED=true` |
| tag `v*` | `prod` | build obrazów i walidacja; `apply` oraz deployment tylko gdy `SENDR_AUTO_DEPLOY_ENABLED=true` |
| `workflow_dispatch` | wybrane ręcznie | ręczne uruchomienie `apply` i deploymentu dla `dev`, `staging` albo `prod` |

`DO-implementation` jest gałęzią integracyjną. Może budować obrazy i walidować Terraform, ale nie powinna zużywać sekretów produkcyjnych ani wykonywać zmian w chmurze.

## Włączanie automatycznych deploymentów

Realne zmiany w DigitalOcean są domyślnie bezpiecznie zatrzymane po walidacji, dopóki repozytorium nie ma poprawnych sekretów DigitalOcean i Spaces. Aby włączyć automatyczny `apply` i deployment z gałęzi/tagów, ustaw zmienną repozytorium GitHub `SENDR_AUTO_DEPLOY_ENABLED` na `true` w **Settings** -> **Secrets and variables** -> **Actions** -> **Variables**.

Ręczne uruchomienia przez `workflow_dispatch` zawsze wymagają sekretów wybranego środowiska, ale nie wymagają tej zmiennej.

## DEV

Środowisko `dev` jest aktualizowane ręcznie przez `workflow_dispatch` z opcją `dev`. Push na `main` może wdrażać automatycznie tylko po ustawieniu `SENDR_AUTO_DEPLOY_ENABLED=true`.

```bash
git checkout main
git add .
git commit -m "feat: update infrastructure"
git push origin main
```

## STAGING

Środowisko `staging` jest aktualizowane ręcznie przez `workflow_dispatch` z opcją `staging`. Gałęzie `release/**` mogą wdrażać automatycznie tylko po ustawieniu `SENDR_AUTO_DEPLOY_ENABLED=true`.

```bash
git checkout main
git checkout -b release/v1.2.0
git push origin release/v1.2.0
```

## PROD

Środowisko `prod` jest aktualizowane ręcznie przez `workflow_dispatch` z opcją `prod`. Tagi `v*` mogą wdrażać automatycznie tylko po ustawieniu `SENDR_AUTO_DEPLOY_ENABLED=true`.

```bash
git checkout main
git tag v1.2.0
git push origin v1.2.0
```

## Manual approval

Workflowy używają środowisk GitHub `dev`, `staging` i `prod`. Dla produkcji warto włączyć ręczne zatwierdzanie:

1. Wejdź w **Settings** -> **Environments**.
2. Utwórz albo otwórz środowisko `prod`.
3. Włącz **Required reviewers** i dodaj osoby odpowiedzialne za wydania.

Po tej zmianie deployment produkcyjny zatrzyma się przed wykonaniem kroków wymagających zatwierdzenia.
