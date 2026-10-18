# Portal Wrapper

This package wraps the `OpenContext` snapshot and provides a central entry point for portal instantiation.

## Purpose

- Load portal definitions for multiple MCP servers.
- Generate or configure portal instances based on city, URL, and portal type.
- Prepare deployment artifacts for AWS.

## Contents

- `portal_manager.py` — core wrapper logic.
- `config/portal_definitions.yaml` — active portal definitions.
- `config/portal_definitions.example.yaml` — example portal definitions.
- `terraform/` — per-portal Lambda + API Gateway infrastructure.
- `dashboard/` — local read-only usage dashboard (see its README).
- `requirements.txt` — wrapper dependencies.

## Supported portals

Portal types supported by OpenContext: ArcGIS Hub (`arcgis`), Socrata
(`socrata`), CKAN (`ckan`), and Opendatasoft (`opendatasoft`). Other platforms
(e.g. JKAN) are skipped — see `docs/portals.md`.

## Definition fields

Each entry in `config/portal_definitions.yaml` supports:

| Field | Required | Purpose |
|-------|----------|---------|
| `city` | yes | Display name and source of the derived slug. |
| `url` | yes | Portal base URL. |
| `type` | yes | One of `arcgis`, `socrata`, `ckan`, `opendatasoft`. |
| `warning` | no | Appended to the user-facing MCP server description (e.g. flag incomplete coverage). Surfaces in Claude's connector list and to the model. |
| `notes` | no | Internal documentation only; never reaches users. |

## Getting started

1. Review `docs/portals.md` and the supported portal list.
2. Add or update `portal-wrapper/config/portal_definitions.yaml`.
3. Validate the definitions: `python portal-wrapper/portal_manager.py validate`.
4. Plan/apply the deployment with the CLI (see below).

> **Use the CLI, not bare `terraform plan`/`apply`.** One S3 state key holds
> every environment, and the CLI refuses to run when the state belongs to a
> different environment than `-e` — see
> [`docs/aws-deployment.md` §11](../docs/aws-deployment.md#11-environment-safety-one-shared-state-key-multiple-environments).

## CLI

`portal_manager.py` validates definitions and orchestrates Terraform using the
same portal-slug algorithm and definitions file the infrastructure uses.

```bash
python portal-wrapper/portal_manager.py list                 # list portals + derived slugs
python portal-wrapper/portal_manager.py validate             # validate definitions
python portal-wrapper/portal_manager.py plan -e dev          # terraform plan
python portal-wrapper/portal_manager.py apply -e staging     # terraform apply
```

Run `plan`/`apply` from `portal-wrapper/terraform` after `terraform init`. For
the Responsive Cities deployment (`<slug>.responsive.city`), see
[`docs/aws-deployment.md` §10](../docs/aws-deployment.md#10-responsive-cities-deployment-rc-deploy-role-slugresponsivecity):

```bash
AWS_PROFILE=rc-deploy python ../portal_manager.py apply -e prod --var-file=rc-prod.tfvars
```

Socrata portals need an app token keyed by slug — from the gitignored
`terraform/secret.auto.tfvars`, or `--app-token <slug>=TOKEN` (passed to
Terraform via the environment, never on argv). ArcGIS Hub, CKAN, and
Opendatasoft portals need no secrets.

## AWS deployment scaffolding

> Full step-by-step AWS runbook (prerequisites, encrypted S3 state, Socrata token,
> and a least-privilege deployer IAM policy): [`docs/aws-deployment.md`](../docs/aws-deployment.md).

Terraform lives in `portal-wrapper/terraform`. For each portal definition it:

- builds a Lambda deployment package via `build_lambda.sh` (runtime source +
  pip dependencies for Linux x86_64 / Python 3.11 — not just the raw source),
- renders a plugin-type-aware OpenContext config (`config_template.yaml.tftpl`),
- deploys one Lambda behind an HTTP API Gateway, with CloudWatch logs.

Resources are named `<resource_name_prefix><slug>-mcp-<env>` (the Responsive
Cities deployment uses prefix `rc-`), so `dev`, `staging`, and `prod` can
coexist in one account.

### Environments

- `dev` / `staging`: API Gateway invoke URL, no DNS. Enable the direct Lambda
  Function URL only for testing with `-var enable_function_url=true`.
- `prod`: custom domains — with `use_custom_domain` enabled each portal gets
  `<slug>.<base_domain>` (e.g. `boulder-co.responsive.city`) via ACM + Route53.

### Validate

```bash
cd portal-wrapper/terraform
./validate.sh                                      # init -backend=false, fmt -check, validate
terraform init -backend-config=backend.s3.hcl      # configure remote state + AWS provider
```

### State and secrets

The Terraform block declares `backend "s3" {}`, so state is remote — supply the
bucket/key/region at init from a gitignored `backend.s3.hcl` (copy
`backend.s3.hcl.example`):

```bash
terraform init -backend-config=backend.s3.hcl
```

State holds `portal_app_tokens` and the rendered config in plaintext, so the
bucket must be encrypted. `./validate.sh` uses `terraform init -backend=false`
and needs no backend values. For purely local experimentation, drop a
`backend_override.tf` containing `terraform { backend "local" {} }`.

## Tests

```bash
pip install -r portal-wrapper/requirements-dev.txt
python -m pytest portal-wrapper/tests -q
```
