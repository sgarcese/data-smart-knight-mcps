"""Discover deployed MCP portal Lambda functions and map them to city names."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import boto3
import yaml
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from portal_manager import portal_slug  # noqa: E402

CONFIG_FILE = ROOT / "config" / "portal_definitions.yaml"


@dataclass(frozen=True)
class Portal:
    slug: str
    function_name: str
    city: str

    @property
    def log_group(self) -> str:
        return f"/aws/lambda/{self.function_name}"


def _slug_to_city() -> dict[str, str]:
    """Map portal slug -> display city name from portal_definitions.yaml.

    Best-effort: a portal deployed but missing from the YAML (or vice versa)
    should never break discovery, so callers fall back to the raw slug.
    """
    if not CONFIG_FILE.exists():
        return {}
    data = yaml.safe_load(CONFIG_FILE.read_text()) or {}
    return {portal_slug(p["city"]): p["city"] for p in data.get("portals", [])}


def discover_portal_functions(
    env: str,
    prefix: str = "rc-",
    deployment_prefix: str = "mcp",
) -> list[Portal]:
    """Find deployed ``<prefix><slug>-<deployment_prefix>-<env>`` Lambda functions.

    Matches the naming built by ``terraform/main.tf`` (``local.portal_resource_name``
    = ``"${resource_name_prefix}${slug}-${deployment_prefix}-${deployment_environment}"``).

    Deliberately uses ``GetFunction`` per candidate slug rather than
    ``ListFunctions``: the dashboard's read-only IAM grant (see
    ``../iam/rc-deploy-dashboard-readonly-policy.json``) doesn't include
    ``lambda:ListFunctions`` (which can't be resource-scoped to ``rc-*`` and
    so would need a broader grant than this dashboard needs), while
    ``lambda:GetFunction`` on ``rc-*`` is already covered by the existing
    deploy policy.
    """
    client = boto3.client("lambda")
    slug_to_city = _slug_to_city()

    portals = []
    for slug in sorted(slug_to_city):
        function_name = f"{prefix}{slug}-{deployment_prefix}-{env}"
        try:
            client.get_function(FunctionName=function_name)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                continue
            raise
        portals.append(Portal(slug=slug, function_name=function_name, city=slug_to_city[slug]))
    return portals
