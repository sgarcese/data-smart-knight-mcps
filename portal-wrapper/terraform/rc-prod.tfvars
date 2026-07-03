# Responsive Cities production deployment.
#
# Deploys every portal as rc-<slug>-mcp-prod with a custom domain at
# <slug>.responsive.city (MCP endpoint: https://<slug>.responsive.city/mcp).
#
# Deploy as the rc-deploy role (defined in the responsive-cities bootstrap,
# see phila-mcp/terraform/bootstrap/):
#
#   AWS_PROFILE=rc-deploy terraform init -backend-config=backend.s3.hcl
#   AWS_PROFILE=rc-deploy terraform plan  -var-file=rc-prod.tfvars
#   AWS_PROFILE=rc-deploy terraform apply -var-file=rc-prod.tfvars
#
# Contains no secrets (Socrata tokens stay in secret.auto.tfvars, gitignored).

deployment_environment = "prod"

# rc-* naming so resources fall inside the rc-deploy role's scoping
resource_name_prefix     = "rc-"
permissions_boundary_arn = "arn:aws:iam::564762345093:policy/rc-permissions-boundary"

# <slug>.responsive.city custom domains (hosted zone in the same account)
use_custom_domain = true
base_domain       = "responsive.city"
route53_zone_id   = "Z02890412WHZ405FIOT0Y"
