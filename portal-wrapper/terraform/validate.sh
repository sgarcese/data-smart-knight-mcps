#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v terraform >/dev/null 2>&1; then
  echo "Terraform is not installed. Install Terraform to validate this configuration."
  exit 1
fi

terraform init -input=false
terraform fmt -check -recursive
terraform validate

echo "Terraform validation passed."
echo "To preview the deployment, run:"
echo "  terraform plan -var='portal_definitions_file=../config/portal_definitions.yaml'"
