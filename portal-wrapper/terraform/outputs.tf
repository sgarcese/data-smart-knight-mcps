output "portal_function_urls" {
  description = "Function URLs for each deployed portal lambda."
  value = {
    for key, resource in aws_lambda_function_url.mcp_server_url : key => resource.function_url
  }
}

output "portal_config_files" {
  description = "Generated OpenContext config files for each portal."
  value = {
    for key, resource in local_file.portal_config : key => resource.filename
  }
}
