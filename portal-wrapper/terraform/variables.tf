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
  description = "Deployment environment: dev, staging, or prod."
  type        = string
  default     = "dev"
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
