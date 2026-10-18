# Responsive Cities staging deployment: rc-<slug>-mcp-staging, no custom
# domains (use the API Gateway invoke URLs from terraform output).
#
# WARNING: the backend in backend.s3.hcl holds PROD state. Do not plan/apply
# this file against it — give staging its own state key first
# (docs/aws-deployment.md §11).

deployment_environment = "staging"

resource_name_prefix     = "rc-"
permissions_boundary_arn = "arn:aws:iam::564762345093:policy/rc-permissions-boundary"
