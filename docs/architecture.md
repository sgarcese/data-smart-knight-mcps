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
- Support separate environments for staging and production.
- Use modular AWS resources per portal, such as:
  - AWS Lambda for OpenContext hosting
  - Function URLs or API Gateway for routing requests
  - IAM roles for Lambda execution
  - CloudWatch Logs for observability

## Portal wrapper deployment scaffold

The wrapper includes Terraform scaffolding under `portal-wrapper/terraform`.
It packages the local `opencontext/` source tree, generates portal-specific OpenContext config files, and deploys one AWS Lambda per supported portal.

Validation steps:

1. `cd portal-wrapper/terraform`
2. `./validate.sh`
3. `terraform plan -var='portal_definitions_file=../config/portal_definitions.yaml'`
