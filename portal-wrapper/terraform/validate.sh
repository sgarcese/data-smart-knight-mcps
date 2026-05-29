#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v terraform >/dev/null 2>&1; then
  echo "Terraform is not installed. Install Terraform to validate this configuration."
  exit 1
fi

# -backend=false so validation works without configuring remote state.
terraform init -backend=false -input=false
terraform fmt -check -recursive
terraform validate

echo "Terraform validation passed."
echo "To preview a deployment (configures state + AWS provider):"
echo "  terraform init"
echo "  terraform plan -var='deployment_environment=dev'"
echo "Or via the wrapper CLI:"
echo "  python ../portal_manager.py plan --environment dev"
