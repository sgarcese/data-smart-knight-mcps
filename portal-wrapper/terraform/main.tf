terraform {
  required_version = ">= 1.0"
  backend "local" {
    path = "terraform.tfstate"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  portal_definitions = yamldecode(file(var.portal_definitions_file)).portals
  portal_map = {
    for portal in local.portal_definitions :
    trim(lower(replace(portal.city, "/[^A-Za-z0-9]+/", "-")), "-") => portal
  }
  portal_hostname = {
    for key, portal in local.portal_map :
    key => "${key}.${var.base_domain}"
  }
  custom_domain_enabled = var.use_custom_domain && var.base_domain != "" && var.route53_zone_id != ""
  portal_domain_map = local.custom_domain_enabled ? local.portal_map : {}
}

resource "archive_file" "opencontext_lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../../opencontext"
  output_path = "${path.module}/opencontext-lambda.zip"
}

resource "local_file" "portal_config" {
  for_each = local.portal_map

  content = templatefile(
    "${path.module}/config_template.yaml.tftpl",
    {
      city           = each.value.city
      url            = each.value.url
      plugin_type    = each.value.type
      lambda_name    = "${each.key}-${var.deployment_prefix}"
      aws_region     = var.aws_region
      lambda_memory  = var.lambda_memory
      lambda_timeout = var.lambda_timeout
    }
  )

  filename = "${path.module}/generated-configs/${each.key}.yaml"
}

resource "aws_iam_role" "lambda_role" {
  for_each = local.portal_map

  name = "${each.key}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  for_each = local.portal_map

  role       = aws_iam_role.lambda_role[each.key].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "mcp_server" {
  for_each = local.portal_map

  filename         = archive_file.opencontext_lambda.output_path
  function_name    = "${each.key}-${var.deployment_prefix}"
  role             = aws_iam_role.lambda_role[each.key].arn
  handler          = "server.adapters.aws_lambda.lambda_handler"
  source_code_hash = filebase64sha256(archive_file.opencontext_lambda.output_path)
  runtime          = "python3.11"
  memory_size      = var.lambda_memory
  timeout          = var.lambda_timeout

  environment {
    variables = {
      OPENCONTEXT_CONFIG = jsonencode(yamldecode(local_file.portal_config[each.key].content))
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic,
  ]
}

resource "aws_lambda_function_url" "mcp_server_url" {
  for_each = local.portal_map

  function_name      = aws_lambda_function.mcp_server[each.key].function_name
  authorization_type = "NONE"

  cors {
    allow_origins  = ["*"]
    allow_methods  = ["POST"]
    allow_headers  = ["content-type"]
    expose_headers = ["x-request-id", "mcp-session-id"]
    max_age        = 86400
  }
}

resource "aws_apigatewayv2_api" "mcp_server_api" {
  for_each      = local.portal_map
  name          = "${each.key}-${var.deployment_prefix}-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda" {
  for_each               = local.portal_map
  api_id                 = aws_apigatewayv2_api.mcp_server_api[each.key].id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.mcp_server[each.key].arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default" {
  for_each = local.portal_map

  api_id    = aws_apigatewayv2_api.mcp_server_api[each.key].id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda[each.key].id}"
}

resource "aws_apigatewayv2_stage" "default" {
  for_each   = local.portal_map
  api_id     = aws_apigatewayv2_api.mcp_server_api[each.key].id
  name       = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "allow_api_gateway" {
  for_each = local.portal_map

  statement_id  = "AllowExecutionFromAPIGateway-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.mcp_server[each.key].arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.mcp_server_api[each.key].execution_arn}/*/*"
}

resource "aws_acm_certificate" "portal_domain" {
  for_each = local.portal_domain_map

  domain_name       = local.portal_hostname[each.key]
  validation_method = "DNS"
}

resource "aws_route53_record" "cert_validation" {
  for_each = aws_acm_certificate.portal_domain

  zone_id = var.route53_zone_id
  name    = each.value.domain_validation_options[0].resource_record_name
  type    = each.value.domain_validation_options[0].resource_record_type
  records = [each.value.domain_validation_options[0].resource_record_value]
  ttl     = 60
}

resource "aws_acm_certificate_validation" "portal_domain" {
  for_each = aws_acm_certificate.portal_domain

  certificate_arn         = each.value.arn
  validation_record_fqdns = [aws_route53_record.cert_validation[each.key].fqdn]
}

resource "aws_apigatewayv2_domain_name" "portal_domain" {
  for_each = aws_acm_certificate_validation.portal_domain

  domain_name = local.portal_hostname[each.key]

  domain_name_configuration {
    endpoint_type   = "REGIONAL"
    certificate_arn = each.value.certificate_arn
    security_policy = "TLS_1_2"
  }
}

resource "aws_apigatewayv2_api_mapping" "portal_domain_mapping" {
  for_each = aws_apigatewayv2_domain_name.portal_domain

  api_id      = aws_apigatewayv2_api.mcp_server_api[each.key].id
  domain_name = each.value.domain_name
  stage       = aws_apigatewayv2_stage.default[each.key].name
}

resource "aws_route53_record" "portal_domain_alias" {
  for_each = aws_apigatewayv2_domain_name.portal_domain

  zone_id = var.route53_zone_id
  name    = each.value.domain_name
  type    = "A"

  alias {
    name                   = each.value.domain_name_configuration[0].host_name
    zone_id                = each.value.domain_name_configuration[0].hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_cloudwatch_log_group" "lambda_logs" {
  for_each = local.portal_map

  name              = "/aws/lambda/${aws_lambda_function.mcp_server[each.key].function_name}"
  retention_in_days = 14
}
