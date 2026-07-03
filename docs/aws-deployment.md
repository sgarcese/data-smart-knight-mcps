# Deploying the MCP Portals to AWS

This runbook deploys the portal Lambdas in `portal-wrapper/` to AWS. It is
written for a **staging** environment with **encrypted remote S3 state**, starting
from a machine where **AWS credentials are not yet configured**. The same steps
apply to `dev`/`prod` by changing `deployment_environment` (prod additionally
enables custom domains — see §9).

Staging deploys the same infrastructure as prod (one Lambda + HTTP API Gateway +
CloudWatch log group per portal) but **without custom DNS** — you use the API
Gateway invoke URLs. Resources are named `<slug>-mcp-staging`, so dev/staging/prod
can coexist in one account.

The current portals are all ArcGIS Hub or CKAN, which need **no secrets**. A
token is only required if you add a **Socrata** portal — see §4.

---

## 1. Local tooling (build/deploy machine)

| Tool | Version | Why |
|------|---------|-----|
| Terraform | **≥ 1.5** | Runs the config. S3-native locking (`use_lockfile`) needs ≥ 1.11; some builds reject it (see §3). |
| Python | **3.11+** | Runs `portal_manager.py`; build targets the py3.11 Lambda runtime. |
| `uv` (preferred) or `pip3` | recent | `build_lambda.sh` installs deps for `x86_64-manylinux2014` / py3.11. |
| bash | any | Runs `build_lambda.sh`. |
| AWS CLI v2 | recent | Configure/verify credentials (`brew install awscli`). |

The build produces a Linux x86_64 package from macOS via cross-platform wheels —
no Docker needed.

## 2. AWS account + credentials

Configure credentials (pick one):

- SSO: `aws configure sso` then `export AWS_PROFILE=<name>`
- Static keys: `aws configure` (writes `~/.aws/credentials`)
- Verify: `aws sts get-caller-identity`

The Terraform AWS provider uses the default credential chain — `AWS_PROFILE` or
`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` both work. Region defaults to
`us-east-1` (override with `-var aws_region=...`).

> **Custom login tools.** If your `aws` CLI is fronted by a wrapper (e.g. a
> `login_session`-based `aws login` flow) that the AWS SDK's default chain can't
> read, the CLI will authenticate but Terraform will fail with *"No valid
> credential sources found."* Export standard env-var credentials for the
> Terraform command instead:
> ```bash
> eval "$(aws configure export-credentials --format env)"
> terraform plan ...   # run in the same shell
> ```

For a first solo deploy, an admin/PowerUser identity is the fast path. For a
dedicated least-privilege deployer, use the policy and identity in
[Appendix A](#appendix-a--least-privilege-deploy-identity).

## 3. One-time: provision the state bucket

The S3 backend bucket must exist **before** `terraform init`. Create it once
(bucket names are globally unique):

```bash
aws s3api create-bucket --bucket YOUR-tfstate-bucket --region us-east-1
aws s3api put-bucket-versioning --bucket YOUR-tfstate-bucket \
  --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption --bucket YOUR-tfstate-bucket \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"aws:kms"}}]}'
```

(`opencontext/terraform/bootstrap/` is a Terraform alternative, but the three CLI
calls above are simpler for one bucket.)

The Terraform block already declares `backend "s3" {}`, so init only needs the
values. Create `portal-wrapper/terraform/backend.s3.hcl` from the committed
`backend.s3.hcl.example` (this file is gitignored):

```hcl
bucket  = "YOUR-tfstate-bucket"
key     = "portal-wrapper/staging.tfstate"
region  = "us-east-1"
encrypt = true
```

> State locking is optional and omitted above. `use_lockfile = true` enables
> S3-native locking but requires Terraform ≥ 1.11 and is rejected by some builds;
> a single operator can safely skip it, or use a `dynamodb_table` instead.

## 4. Socrata app token (only if you add a Socrata portal)

**None of the current portals are Socrata, so you can skip this section.** It
applies only when a portal in `portal_definitions.yaml` has `type: socrata` —
then that portal needs a free token or `terraform plan` fails a precondition
(*"Socrata portal '<slug>' requires an app token"*).

Register at <https://dev.socrata.com/register>, then supply it at deploy time
(keyed by the portal slug, never committed):

- CLI flag: `--app-token <slug>=YOUR_TOKEN`
- Env var: `export TF_VAR_portal_app_tokens='{"<slug>":"YOUR_TOKEN"}'`
- Or a gitignored `secret.auto.tfvars`: `portal_app_tokens = { "<slug>" = "YOUR_TOKEN" }`

## 5. Deploy (staging)

```bash
cd portal-wrapper

# a. Validate the definitions (types, required fields, unique slugs)
python portal_manager.py validate

cd terraform

# b. Initialize the encrypted S3 backend
terraform init -backend-config=backend.s3.hcl

# c. If your CLI uses a custom login (see §2), export creds for Terraform:
eval "$(aws configure export-credentials --format env)"

# d. Plan + apply staging (no -var needed; all current portals are token-free)
terraform plan  -var=deployment_environment=staging -out=staging.tfplan
terraform apply staging.tfplan
```

Or drive it through the wrapper CLI:

```bash
# run `terraform init -backend-config=backend.s3.hcl` once first
python portal_manager.py apply -e staging
```

(If a Socrata portal is present, add `-var='portal_app_tokens={"<slug>":"…"}'` to
plan/apply, or `--app-token <slug>=…` to the CLI — see §4.)

`terraform apply` runs `build_lambda.sh` automatically (builds the ~22 MB package
with dependencies), then creates per portal: an IAM role, a Lambda, an HTTP API
Gateway, and a CloudWatch log group.

## 6. Get the endpoints

```bash
terraform output portal_api_endpoints
```

Returns `<slug> => https://<api-id>.execute-api.us-east-1.amazonaws.com/`. The MCP
server is served at the **`/mcp`** path, so the connector URL to register in
Claude is `<endpoint>mcp` (e.g. `https://abc123.execute-api.us-east-1.amazonaws.com/mcp`).
A `POST /` returns a 404 ("Expected '/mcp'").

## 7. Verify end-to-end

1. **Live smoke test** — MCP `initialize` handshake against one endpoint (note the
   `/mcp` path):
   ```bash
   base=$(terraform output -json portal_api_endpoints | python3 -c 'import sys,json;print(json.load(sys.stdin)["lexington-ky"].rstrip("/"))')
   curl -sS -X POST "$base/mcp" \
     -H 'content-type: application/json' -H 'accept: application/json' \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'
   ```
   Expect HTTP 200 with a JSON-RPC `result`. Common failures:
   - **500 import error** → the build step didn't run; re-run `terraform apply`.
   - **500 "plugin … initialization returned False"** → the portal `type`/`url` in
     `portal_definitions.yaml` is wrong for that portal (e.g. a portal labeled
     `ckan`/`socrata` that is actually ArcGIS Hub). Fix the definition and re-apply.
2. **Logs**: `aws logs tail /aws/lambda/lexington-ky-mcp-staging --since 5m`.

## 8. Teardown

```bash
terraform destroy -var=deployment_environment=staging
```

## 9. Prod with custom domains

For `deployment_environment=prod`, enable custom subdomains
(`<portal-slug>.<base_domain>`) backed by ACM + Route53:

```bash
terraform apply \
  -var=deployment_environment=prod \
  -var=use_custom_domain=true \
  -var=base_domain=data-portals.example.com \
  -var=route53_zone_id=ZXXXXXXXXXXX
```

Requires a registered domain with a Route53 hosted zone, and the deployer identity
needs the extra ACM/Route53 permissions noted in Appendix A.

---

## 10. Responsive Cities deployment (rc-deploy role, `<slug>.responsive.city`)

The canonical deployment of this project runs in the Responsive Cities AWS
account (`564762345093`) and follows its `rc-*` conventions. Everything is
captured in the checked-in `rc-prod.tfvars` / `rc-staging.tfvars`:

- **Resource naming**: `resource_name_prefix = "rc-"` → Lambdas
  `rc-<slug>-mcp-<env>`, roles `rc-<slug>-mcp-<env>-role`, etc. This matters
  because the deployment role is scoped to `rc-*` resources.
- **Deployment identity**: the `rc-deploy` IAM role (defined in the
  `phila-mcp` repo's `terraform/bootstrap/`, applied with admin credentials).
  It has enumerated, `rc-*`-scoped permissions, may only create IAM roles
  carrying the `rc-permissions-boundary`, and is explicitly denied from
  modifying itself. Locally it is used via the `rc-deploy` CLI profile
  (`role_arn`/`source_profile` chaining through the `rc-deployer` IAM user,
  because the account root user cannot assume roles). This replaces the
  Appendix A identity for this environment.
- **Boundary**: `permissions_boundary_arn` must be set (rc-prod/rc-staging
  tfvars do this) or `rc-deploy` will get AccessDenied on `iam:CreateRole`.
- **State**: `s3://rc-tfstate-564762345093`, key
  `rc/data-smart/portal-wrapper/terraform.tfstate` (see
  `backend.s3.hcl.example`).
- **DNS**: `base_domain = responsive.city` (hosted zone
  `Z02890412WHZ405FIOT0Y`, same account) → MCP endpoints at
  `https://<slug>.responsive.city/mcp` (e.g.
  `https://boulder-co.responsive.city/mcp`).

```bash
cd portal-wrapper/terraform
AWS_PROFILE=rc-deploy terraform init -backend-config=backend.s3.hcl
AWS_PROFILE=rc-deploy terraform plan  -var-file=rc-prod.tfvars
AWS_PROFILE=rc-deploy terraform apply -var-file=rc-prod.tfvars
```

---

## Summary

- **Install**: AWS CLI (Terraform/Python/uv assumed present).
- **AWS**: an account + configured credentials — admin for a first deploy, or the
  least-privilege `mcp-portal-deployer` identity in Appendix A.
- **Provision once**: an encrypted, versioned S3 state bucket (§3) + `backend.s3.hcl`.
- **Secrets**: none for the current portals (all ArcGIS Hub / CKAN); a Socrata
  portal would need a token (§4).
- **Run**: validate → `init -backend-config` → (export creds if needed) →
  `plan`/`apply` with `deployment_environment=staging` (§5), then read
  `portal_api_endpoints` and append `/mcp` (§6).

No custom domain, Route53, or ACM is needed for staging.

---

## Appendix A — Least-privilege deploy identity

A dedicated identity scoped to exactly what the portal deployment creates. All
resources are constrained to the `*-mcp-*` naming the Terraform uses, plus the one
state bucket. Replace `<ACCOUNT_ID>`, `<REGION>` (e.g. `us-east-1`), and
`<STATE_BUCKET>`.

> Bucket *creation* (§3) needs `s3:CreateBucket` etc. — do that one-time as an
> admin. This deployer policy only needs object access to the existing bucket.

### Policy document

Save the JSON below to `portal-wrapper/iam/mcp-portal-deployer-policy.json` and
fill in `<ACCOUNT_ID>`/`<REGION>`/`<STATE_BUCKET>`. That path is gitignored (see
`portal-wrapper/iam/.gitignore`) so your account-specific file stays local — this
template is the source of record.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "TerraformState",
      "Effect": "Allow",
      "Action": ["s3:ListBucket", "s3:GetBucketVersioning"],
      "Resource": "arn:aws:s3:::<STATE_BUCKET>"
    },
    {
      "Sid": "TerraformStateObjects",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::<STATE_BUCKET>/portal-wrapper/*"
    },
    {
      "Sid": "LambdaManage",
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction", "lambda:DeleteFunction",
        "lambda:GetFunction", "lambda:GetFunctionConfiguration",
        "lambda:UpdateFunctionCode", "lambda:UpdateFunctionConfiguration",
        "lambda:ListVersionsByFunction", "lambda:TagResource",
        "lambda:UntagResource", "lambda:ListTags",
        "lambda:AddPermission", "lambda:RemovePermission", "lambda:GetPolicy",
        "lambda:CreateFunctionUrlConfig", "lambda:GetFunctionUrlConfig",
        "lambda:UpdateFunctionUrlConfig", "lambda:DeleteFunctionUrlConfig"
      ],
      "Resource": "arn:aws:lambda:<REGION>:<ACCOUNT_ID>:function:*-mcp-*"
    },
    {
      "Sid": "IamLambdaExecutionRoles",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole", "iam:DeleteRole", "iam:GetRole",
        "iam:TagRole", "iam:UntagRole",
        "iam:AttachRolePolicy", "iam:DetachRolePolicy",
        "iam:ListRolePolicies", "iam:ListAttachedRolePolicies"
      ],
      "Resource": "arn:aws:iam::<ACCOUNT_ID>:role/*-mcp-*-role"
    },
    {
      "Sid": "PassExecutionRoleToLambda",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "arn:aws:iam::<ACCOUNT_ID>:role/*-mcp-*-role",
      "Condition": {
        "StringEquals": { "iam:PassedToService": "lambda.amazonaws.com" }
      }
    },
    {
      "Sid": "ApiGatewayManage",
      "Effect": "Allow",
      "Action": ["apigateway:GET", "apigateway:POST", "apigateway:PUT", "apigateway:PATCH", "apigateway:DELETE"],
      "Resource": [
        "arn:aws:apigateway:<REGION>::/apis",
        "arn:aws:apigateway:<REGION>::/apis/*",
        "arn:aws:apigateway:<REGION>::/tags/*"
      ]
    },
    {
      "Sid": "CloudWatchLogGroups",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup", "logs:DeleteLogGroup",
        "logs:PutRetentionPolicy", "logs:TagResource", "logs:UntagResource",
        "logs:ListTagsForResource"
      ],
      "Resource": "arn:aws:logs:<REGION>:<ACCOUNT_ID>:log-group:/aws/lambda/*-mcp-*:*"
    },
    {
      "Sid": "CloudWatchLogGroupsDescribe",
      "Effect": "Allow",
      "Action": "logs:DescribeLogGroups",
      "Resource": "*"
    }
  ]
}
```

Notes:

- `logs:DescribeLogGroups` cannot be resource-scoped (`Resource: "*"`).
  `sts:GetCallerIdentity` (used by Terraform) is allowed for any caller by default.
- The `*FunctionUrlConfig` actions are only exercised when `enable_function_url=true`;
  harmless to keep for testing.
- For **prod with custom domains** (§9), add: `acm:RequestCertificate`,
  `acm:DescribeCertificate`, `acm:DeleteCertificate`, `acm:AddTagsToCertificate`,
  `acm:ListTagsForCertificate`; `route53:ChangeResourceRecordSets`,
  `route53:GetChange`, `route53:ListHostedZones`,
  `route53:GetHostedZone` (scoped to your zone); and `apigateway:*` access to
  `arn:aws:apigateway:<REGION>::/domainnames/*`.

### Create the identity

Preferred: an IAM **role** assumed via SSO/`AssumeRole` (no long-lived keys). The
simplest reproducible path is a dedicated IAM **user** for local/CI:

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
cd portal-wrapper/iam   # where mcp-portal-deployer-policy.json lives (gitignored)

# 1. Create the customer-managed policy from the JSON above
#    (fill in <ACCOUNT_ID>/<REGION>/<STATE_BUCKET> first)
aws iam create-policy \
  --policy-name mcp-portal-deployer \
  --policy-document file://mcp-portal-deployer-policy.json

# 2a. Attach to a NEW user (local/CI) ...
aws iam create-user --user-name mcp-portal-deployer
aws iam attach-user-policy --user-name mcp-portal-deployer \
  --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/mcp-portal-deployer
aws iam create-access-key --user-name mcp-portal-deployer   # store securely

# 2b. ... OR attach to a ROLE you assume (preferred; no static keys)
#     create the role with your trust policy, then:
# aws iam attach-role-policy --role-name mcp-portal-deployer \
#   --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/mcp-portal-deployer
```

Point Terraform at it (`export AWS_PROFILE=mcp-portal-deployer`, or assume the
role) and run the deploy in §5. If `apply` fails with `AccessDenied`, the message
names the exact missing action — add it to the matching statement.
