variable "portal_definitions_file" {
  description = "Path to the portal definitions YAML file."
  type        = string
  default     = "../config/portal_definitions.yaml"
}

variable "aws_region" {
  description = "AWS region for deployment."
  type        = string
  default     = "us-east-1"
}

variable "deployment_environment" {
  description = "Deployment environment: dev, staging, or prod. Scopes all resource names so environments can coexist in one account."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.deployment_environment)
    error_message = "deployment_environment must be one of: dev, staging, prod."
  }
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days for each portal lambda."
  type        = number
  default     = 14
}

variable "enable_function_url" {
  description = "Expose a direct Lambda Function URL in addition to API Gateway. Off by default to keep a single public ingress per portal."
  type        = bool
  default     = false
}

variable "cors_allow_origins" {
  description = "Allowed CORS origins for the Lambda Function URL. Defaults to any origin for public open-data access; restrict for tighter control."
  type        = list(string)
  default     = ["*"]
}

variable "api_throttling_burst_limit" {
  description = "API Gateway burst limit (concurrent requests) per portal stage."
  type        = number
  default     = 50
}

variable "api_throttling_rate_limit" {
  description = "API Gateway steady-state request rate (requests/sec) per portal stage."
  type        = number
  default     = 25
}

variable "use_custom_domain" {
  description = "Enable custom domain provisioning."
  type        = bool
  default     = false
}

variable "base_domain" {
  description = "Base DNS domain used for custom portal subdomains."
  type        = string
  default     = ""
}

variable "route53_zone_id" {
  description = "Route53 Hosted Zone ID for the custom base domain."
  type        = string
  default     = ""
}

variable "deployment_prefix" {
  description = "Optional prefix added to deployed Lambda names."
  type        = string
  default     = "mcp"
}

variable "lambda_memory" {
  description = "Lambda memory size in MB."
  type        = number
  default     = 512
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds."
  type        = number
  default     = 120
}

variable "plugin_timeout" {
  description = "HTTP request timeout (seconds) for the OpenContext plugin. Must be 1-300."
  type        = number
  default     = 120

  validation {
    condition     = var.plugin_timeout >= 1 && var.plugin_timeout <= 300
    error_message = "plugin_timeout must be between 1 and 300 seconds."
  }
}

variable "portal_app_tokens" {
  description = <<-EOT
    Per-portal secret API tokens, keyed by portal slug (e.g. "detroit-mi").
    Socrata portals require an app token; CKAN/ArcGIS may use one for
    authenticated access. Supply via a tfvars file or TF_VAR_portal_app_tokens
    rather than committing it. Held in state, so use an encrypted remote backend.
  EOT
  type        = map(string)
  default     = {}
  sensitive   = true
}
