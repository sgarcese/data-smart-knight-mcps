output "portal_function_urls" {
  description = "Function URLs for each deployed portal lambda."
  value = {
    for key, resource in aws_lambda_function_url.mcp_server_url : key => resource.function_url
  }
}

output "portal_api_endpoints" {
  description = "API Gateway invoke URLs for each portal."
  value = {
    for key, resource in aws_apigatewayv2_stage.default : key => resource.invoke_url
  }
}

output "portal_custom_domain_urls" {
  description = "Custom domain names for each portal when custom domain provisioning is enabled."
  value = local.custom_domain_enabled ? {
    for key, resource in aws_apigatewayv2_domain_name.portal_domain : key => resource.domain_name
  } : {}
}

output "portal_config_files" {
  description = "Generated OpenContext config files for each portal."
  value = {
    for key, resource in local_file.portal_config : key => resource.filename
  }
}
