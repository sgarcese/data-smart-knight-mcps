# Architecture

## Design decisions

- The `OpenContext` source is stored as a local snapshot in `opencontext/`.
- The wrapper project lives in `portal-wrapper/` and orchestrates portal instantiation.
- This avoids dependency injection from external repos and preserves a stable codebase.

## High-level flow

1. Define MCP portals in `docs/portals.md` or `portal-wrapper/config/portal_definitions.example.yaml`.
2. Use `portal-wrapper` to generate environment-specific configuration for each portal.
3. Deploy the portal wrapper and OpenContext instance to AWS using consistent infrastructure patterns.

## AWS deployment approach

- Prefer Infrastructure as Code with Terraform.
- Support separate environments for dev, staging, and production.
- Use modular AWS resources per portal, such as:
  - AWS Lambda for OpenContext hosting
  - API Gateway for request routing
  - Route53 and ACM for production custom domains
  - CloudWatch Logs for observability

## Environment lifecycle

- `dev`: provision portal resources without DNS assignment. Use Lambda URLs or API Gateway invoke URLs for testing.
- `staging`: mirror production infrastructure in a non-production environment. Keep DNS assignment optional or skip it.
- `prod`: create DNS and SSL resources for custom subdomains.

## Production DNS strategy

DNS assignment should be managed during the production deployment step only.
The Terraform scaffold supports optional custom domain provisioning for each portal, but custom domains should typically be enabled only for the production environment.

- `base_domain` defines the shared domain suffix.
- Each portal gets a distinct subdomain derived from its city name.
- Route53 records and ACM certificates are created only when `use_custom_domain` is enabled.

## Portal wrapper deployment scaffold

The wrapper includes Terraform under `portal-wrapper/terraform`. For each portal
definition it builds a Lambda deployment package (runtime source plus pip
dependencies, via `build_lambda.sh`), renders a plugin-type-aware OpenContext
config, and deploys one AWS Lambda behind an HTTP API Gateway with CloudWatch
logs. `portal_manager.py` is the orchestration entry point: it validates
definitions and drives Terraform with the same slug algorithm.

Resource names are environment-scoped (`<slug>-<prefix>-<env>`) so multiple
environments can coexist in one account.

For an end-to-end AWS deployment runbook — prerequisites, encrypted S3 state, the
required Socrata token, and a least-privilege deployer IAM policy — see
[aws-deployment.md](aws-deployment.md).

Validation steps:

1. `cd portal-wrapper/terraform`
2. `./validate.sh`
3. `terraform init && terraform plan -var='deployment_environment=dev'`
   (or `python ../portal_manager.py plan -e dev`)

## Security and operations posture

- API Gateway is the single public ingress; the direct Lambda Function URL is
  opt-in (`enable_function_url`). API Gateway throttling is enabled by default.
- Secrets (Socrata `app_token`, optional CKAN `api_key`) are supplied via the
  sensitive `portal_app_tokens` variable / `TF_VAR_portal_app_tokens`, never
  committed. They are held in Terraform state, so use the encrypted, locked S3
  backend (`backend.s3.hcl.example`) for shared/production deployments.
- All resources are tagged via provider `default_tags`
  (Project/Component/Environment/ManagedBy).

### Known follow-ups

- Endpoints use `authorization_type = NONE` (public read-only open data). Add
  an authorizer or WAF if access needs restricting.
- Runtime secret fetching from AWS Secrets Manager would remove tokens from
  state entirely but requires changes in the OpenContext snapshot.
