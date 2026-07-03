# Responsive Cities staging deployment: rc-<slug>-mcp-staging, no custom
# domains (use the API Gateway invoke URLs from terraform output).
#
#   AWS_PROFILE=rc-deploy terraform apply -var-file=rc-staging.tfvars

deployment_environment = "staging"

resource_name_prefix     = "rc-"
permissions_boundary_arn = "arn:aws:iam::564762345093:policy/rc-permissions-boundary"
