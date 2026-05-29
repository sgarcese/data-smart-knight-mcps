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
    lower(regexreplace(portal.city, "[^A-Za-z0-9]+", "-")) => portal
  }
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
      OPENCONTEXT_CONFIG = jsonencode(yamldecode(file(local_file.portal_config[each.key].filename)))
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

resource "aws_cloudwatch_log_group" "lambda_logs" {
  for_each = local.portal_map

  name              = "/aws/lambda/${aws_lambda_function.mcp_server[each.key].function_name}"
  retention_in_days = 14
}
