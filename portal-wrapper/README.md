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
- `requirements.txt` — wrapper dependencies.

## Supported portals

Current supported portal sources:
- ArcGIS Hub
- Socrata
- CKAN

Unsupported portals are intentionally skipped because OpenContext does not support JKAN or OpenDataSoft.

## Getting started

1. Review `docs/portals.md` and the supported portal list.
2. Add or update `portal-wrapper/config/portal_definitions.yaml`.
3. Validate the definitions: `python portal-wrapper/portal_manager.py validate`.
4. Plan/apply the deployment with the CLI (see below) or directly with Terraform.

## CLI

`portal_manager.py` validates definitions and orchestrates Terraform using the
same portal-slug algorithm and definitions file the infrastructure uses.

```bash
python portal-wrapper/portal_manager.py list                 # list portals + derived slugs
python portal-wrapper/portal_manager.py validate             # validate definitions
python portal-wrapper/portal_manager.py plan -e dev          # terraform plan
python portal-wrapper/portal_manager.py apply -e staging     # terraform apply
```

The current 8 portals are all ArcGIS Hub / CKAN and need no secrets. If you add a
**Socrata** portal, it requires an app token (passed via the environment, never on
argv) keyed by its slug:

```bash
python portal-wrapper/portal_manager.py apply -e prod \
  --app-token <socrata-slug>=YOUR_SOCRATA_TOKEN
```

## AWS deployment scaffolding

> Full step-by-step AWS runbook (prerequisites, encrypted S3 state, Socrata token,
> and a least-privilege deployer IAM policy): [`docs/aws-deployment.md`](../docs/aws-deployment.md).

Terraform lives in `portal-wrapper/terraform`. For each portal definition it:

- builds a Lambda deployment package via `build_lambda.sh` (runtime source +
  pip dependencies for Linux x86_64 / Python 3.11 — not just the raw source),
- renders a plugin-type-aware OpenContext config (`config_template.yaml.tftpl`),
- deploys one Lambda behind an HTTP API Gateway, with CloudWatch logs.

Resource names are scoped per environment (`<slug>-<prefix>-<env>`) so `dev`,
`staging`, and `prod` can coexist in one account.

### Environments

- `dev` / `staging`: API Gateway invoke URL, no DNS. Enable the direct Lambda
  Function URL only for testing with `-var enable_function_url=true`.
- `prod`: enable custom domains and Route53 DNS records.

### Custom domain model

When `use_custom_domain` is enabled, each portal gets `<portal-slug>.<base_domain>`,
e.g. `boulder-co.data-portals.example.com`.

### Validate and plan

```bash
cd portal-wrapper/terraform
./validate.sh                                      # init -backend=false, fmt -check, validate
terraform init -backend-config=backend.s3.hcl      # configure remote state + AWS provider
terraform plan -var='deployment_environment=dev'
```

See [`docs/aws-deployment.md`](../docs/aws-deployment.md) for the full runbook
(state bucket, credentials, the `/mcp` connector path, and verification).

Production with a custom domain:

```bash
terraform plan \
  -var='deployment_environment=prod' \
  -var='use_custom_domain=true' \
  -var='base_domain=data-portals.example.com' \
  -var='route53_zone_id=ZXXXXXXXXXXX'
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
