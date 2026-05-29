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

- Prefer Infrastructure as Code with Terraform or CloudFormation.
- Support separate environments for staging and production.
- Use modular AWS resources per portal, such as:
  - ECS/Fargate or Lambda for application hosting
  - RDS or managed database if needed
  - API Gateway / ALB for routing
  - S3 for static assets and backups
