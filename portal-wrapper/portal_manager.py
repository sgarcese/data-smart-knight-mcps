"""Portal wrapper: validate portal definitions and orchestrate Terraform.

This is the single entry point that ties the portal definitions to the AWS
Terraform deployment. It validates definitions against the rules enforced by
OpenContext (supported plugin types, required fields, unique slugs) and then
drives `terraform` in ``terraform/`` so the Python wrapper and the
infrastructure stay in sync (same slug algorithm, same definitions file).
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "config" / "portal_definitions.yaml"
TERRAFORM_DIR = ROOT / "terraform"

SUPPORTED_TYPES = {"arcgis", "socrata", "ckan"}
REQUIRED_KEYS = ("city", "url", "type")
ENVIRONMENTS = ("dev", "staging", "prod")


def portal_slug(city: str) -> str:
    """Derive a portal slug from a city name.

    Must match the Terraform locals exactly:
    ``trim(lower(replace(city, "/[^A-Za-z0-9]+/", "-")), "-")``.
    """
    return re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-")


class PortalManager:
    """Load and validate portal definitions."""

    def __init__(self, config_path: pathlib.Path | None = None):
        self.config_path = config_path or CONFIG_FILE
        self.portals = self._load_portal_definitions()

    def _load_portal_definitions(self) -> list[dict]:
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Portal definitions file not found: {self.config_path}"
            )

        with self.config_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}

        return data.get("portals", [])

    def list_portals(self) -> list[dict]:
        """Return the loaded portal definitions."""
        return self.portals

    def validate_definitions(self) -> list[str]:
        """Validate all definitions and return the list of error messages.

        Checks required keys, supported plugin types, and unique slugs (so two
        cities cannot collide on the same Terraform resource name).
        """
        errors: list[str] = []

        if not self.portals:
            errors.append("No portals defined in the definitions file.")
            return errors

        seen_slugs: dict[str, str] = {}
        for index, portal in enumerate(self.portals):
            label = portal.get("city") or f"portal #{index}"

            missing = [k for k in REQUIRED_KEYS if not portal.get(k)]
            if missing:
                errors.append(f"{label}: missing required field(s): {', '.join(missing)}.")

            portal_type = portal.get("type")
            if portal_type and portal_type not in SUPPORTED_TYPES:
                errors.append(
                    f"{label}: unsupported type '{portal_type}'. "
                    f"Supported types: {', '.join(sorted(SUPPORTED_TYPES))}."
                )

            city = portal.get("city")
            if city:
                slug = portal_slug(city)
                if not slug:
                    errors.append(f"{label}: city name produces an empty slug.")
                elif slug in seen_slugs:
                    errors.append(
                        f"{label}: slug '{slug}' collides with '{seen_slugs[slug]}'."
                    )
                else:
                    seen_slugs[slug] = city

        return errors


class TerraformOrchestrator:
    """Build and run Terraform commands for the portal deployment."""

    def __init__(
        self,
        terraform_dir: pathlib.Path | None = None,
        definitions_file: pathlib.Path | None = None,
    ):
        self.terraform_dir = terraform_dir or TERRAFORM_DIR
        self.definitions_file = definitions_file or CONFIG_FILE

    def build_command(
        self,
        action: str,
        *,
        environment: str = "dev",
        use_custom_domain: bool = False,
        base_domain: str = "",
        route53_zone_id: str = "",
        auto_approve: bool = False,
    ) -> list[str]:
        """Return the terraform argv for the given action (pure, for testing)."""
        if action in {"init", "validate", "fmt"}:
            return ["terraform", action]

        cmd = ["terraform", action]
        cmd += ["-var", f"portal_definitions_file={self.definitions_file}"]
        cmd += ["-var", f"deployment_environment={environment}"]

        if use_custom_domain:
            cmd += ["-var", "use_custom_domain=true"]
            cmd += ["-var", f"base_domain={base_domain}"]
            cmd += ["-var", f"route53_zone_id={route53_zone_id}"]

        if action in {"apply", "destroy"} and auto_approve:
            cmd += ["-auto-approve"]

        return cmd

    def run(
        self,
        action: str,
        *,
        app_tokens: dict[str, str] | None = None,
        env: dict[str, str] | None = None,
        **kwargs,
    ) -> int:
        """Execute terraform, returning its exit code.

        Secret app tokens are passed via TF_VAR_portal_app_tokens in the
        environment so they never appear in argv or process listings.
        """
        cmd = self.build_command(action, **kwargs)
        run_env = dict(env if env is not None else os.environ)
        if app_tokens:
            import json

            run_env["TF_VAR_portal_app_tokens"] = json.dumps(app_tokens)

        completed = subprocess.run(cmd, cwd=str(self.terraform_dir), env=run_env)
        return completed.returncode


def _parse_app_tokens(pairs: list[str] | None) -> dict[str, str]:
    tokens: dict[str, str] = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise ValueError(f"Invalid --app-token '{pair}', expected slug=token.")
        slug, token = pair.split("=", 1)
        tokens[slug.strip()] = token
    return tokens


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and deploy MCP data portals.")
    parser.add_argument(
        "--definitions",
        type=pathlib.Path,
        default=CONFIG_FILE,
        help="Path to the portal definitions YAML file.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List loaded portal definitions.")
    sub.add_parser("validate", help="Validate portal definitions.")

    for action in ("plan", "apply", "destroy"):
        p = sub.add_parser(action, help=f"Run terraform {action}.")
        p.add_argument("--environment", "-e", choices=ENVIRONMENTS, default="dev")
        p.add_argument("--use-custom-domain", action="store_true")
        p.add_argument("--base-domain", default="")
        p.add_argument("--route53-zone-id", default="")
        p.add_argument(
            "--app-token",
            action="append",
            metavar="slug=token",
            help="Socrata/CKAN app token for a portal slug (repeatable).",
        )
        if action in ("apply", "destroy"):
            p.add_argument("--auto-approve", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manager = PortalManager(args.definitions)

    if args.command == "list":
        for portal in manager.list_portals():
            print(f"{portal_slug(portal.get('city', '')):20} {portal.get('type', '?'):8} {portal.get('url', '')}")
        return 0

    # Every deploy action validates definitions first.
    errors = manager.validate_definitions()
    if errors:
        print("Invalid portal definitions:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    if args.command == "validate":
        print(f"✓ {len(manager.list_portals())} portal definition(s) valid.")
        return 0

    orchestrator = TerraformOrchestrator(definitions_file=args.definitions)
    return orchestrator.run(
        args.command,
        app_tokens=_parse_app_tokens(getattr(args, "app_token", None)),
        environment=args.environment,
        use_custom_domain=args.use_custom_domain,
        base_domain=args.base_domain,
        route53_zone_id=args.route53_zone_id,
        auto_approve=getattr(args, "auto_approve", False),
    )


if __name__ == "__main__":
    raise SystemExit(main())
