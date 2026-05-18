# Przewodnik po środowiskach i CI/CD

Ten dokument opisuje, kiedy GitHub Actions waliduje kod Terraform, kiedy wykonuje realne zmiany w DigitalOcean i które gałęzie są traktowane jako wdrożeniowe.

Infrastruktura jest obsługiwana przez jeden wspólny workflow Terraform: `.github/workflows/terraform.yml`. Wdrożenie aplikacji do Kubernetes obsługuje `.github/workflows/deploy-k8s.yml`, a obrazy kontenerów buduje `.github/workflows/docker-publish.yml`.

## Gałęzie i środowiska

| Źródło uruchomienia | Środowisko | Zachowanie |
| --- | --- | --- |
| Pull request z plikami Terraform | brak | `terraform fmt`, `terraform init -backend=false`, `terraform validate` |
| `DO-implementation` | brak | walidacja Terraform bez `apply` i bez deploymentu Kubernetes |
| `main` | `dev` | Terraform `apply`, build obrazów i deployment Kubernetes |
| `release/**` | `staging` | Terraform `apply`, build obrazów i deployment Kubernetes |
| tag `v*` | `prod` | Terraform `apply` i deployment wydania produkcyjnego |
| `workflow_dispatch` | wybrane ręcznie | ręczne uruchomienie dla `dev`, `staging` albo `prod` |

`DO-implementation` jest gałęzią integracyjną. Może budować obrazy i walidować Terraform, ale nie powinna zużywać sekretów produkcyjnych ani wykonywać zmian w chmurze.

## DEV

Środowisko `dev` jest aktualizowane z gałęzi `main` albo ręcznie przez `workflow_dispatch` z opcją `dev`.

```bash
git checkout main
git add .
git commit -m "feat: update infrastructure"
git push origin main
```

## STAGING

Środowisko `staging` jest aktualizowane z gałęzi `release/**` albo ręcznie przez `workflow_dispatch` z opcją `staging`.

```bash
git checkout main
git checkout -b release/v1.2.0
git push origin release/v1.2.0
```

## PROD

Środowisko `prod` jest aktualizowane przez tagi `v*` albo ręcznie przez `workflow_dispatch` z opcją `prod`.

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
