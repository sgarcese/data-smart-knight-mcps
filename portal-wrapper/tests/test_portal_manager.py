"""Tests for the portal wrapper validation and Terraform orchestration."""

import json
import pathlib
import subprocess
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from portal_manager import (  # noqa: E402
    PortalManager,
    TerraformOrchestrator,
    _parse_app_tokens,
    portal_slug,
)


def _write_defs(tmp_path, portals):
    import yaml

    path = tmp_path / "defs.yaml"
    path.write_text(yaml.safe_dump({"portals": portals}))
    return path


@pytest.mark.parametrize(
    "city,expected",
    [
        ("Boulder, CO", "boulder-co"),
        ("West Palm Beach, FL", "west-palm-beach-fl"),
        ("St. Paul, MN", "st-paul-mn"),
        ("  Spaced  ", "spaced"),
    ],
)
def test_portal_slug_matches_terraform(city, expected):
    assert portal_slug(city) == expected


def test_valid_definitions_pass(tmp_path):
    path = _write_defs(
        tmp_path,
        [
            {"city": "Detroit, MI", "url": "https://data.detroitmi.gov", "type": "socrata"},
            {"city": "San Jose, CA", "url": "https://data.sanjoseca.gov", "type": "ckan"},
        ],
    )
    assert PortalManager(path).validate_definitions() == []


def test_unsupported_type_is_rejected(tmp_path):
    path = _write_defs(
        tmp_path, [{"city": "Boston", "url": "https://x.gov", "type": "opencontext"}]
    )
    errors = PortalManager(path).validate_definitions()
    assert any("unsupported type" in e for e in errors)


def test_missing_fields_reported(tmp_path):
    path = _write_defs(tmp_path, [{"city": "Boston"}])
    errors = PortalManager(path).validate_definitions()
    assert any("missing required field" in e for e in errors)


def test_slug_collision_detected(tmp_path):
    path = _write_defs(
        tmp_path,
        [
            {"city": "San Jose", "url": "https://a.gov", "type": "ckan"},
            {"city": "San-Jose", "url": "https://b.gov", "type": "ckan"},
        ],
    )
    errors = PortalManager(path).validate_definitions()
    assert any("collides" in e for e in errors)


def test_empty_definitions_reported(tmp_path):
    path = _write_defs(tmp_path, [])
    assert PortalManager(path).validate_definitions() == ["No portals defined in the definitions file."]


def test_shipped_definitions_are_valid():
    """The committed portal_definitions.yaml must always validate."""
    assert PortalManager().validate_definitions() == []


def test_build_command_includes_environment_and_definitions(tmp_path):
    defs = _write_defs(tmp_path, [])
    orch = TerraformOrchestrator(definitions_file=defs)
    cmd = orch.build_command("plan", environment="prod")
    assert cmd[:2] == ["terraform", "plan"]
    assert f"deployment_environment=prod" in cmd
    assert f"portal_definitions_file={defs}" in cmd


def test_build_command_custom_domain(tmp_path):
    orch = TerraformOrchestrator(definitions_file=_write_defs(tmp_path, []))
    cmd = orch.build_command(
        "apply",
        environment="prod",
        use_custom_domain=True,
        base_domain="example.com",
        route53_zone_id="Z123",
        auto_approve=True,
    )
    assert "use_custom_domain=true" in cmd
    assert "base_domain=example.com" in cmd
    assert "route53_zone_id=Z123" in cmd
    assert "-auto-approve" in cmd


def test_build_command_var_file_precedes_and_is_overridden_by_environment(tmp_path):
    """-var-file must come first so the explicit -e/--environment value (which
    the run() safety guard already checked) always wins for
    deployment_environment, even if the var file sets it too."""
    orch = TerraformOrchestrator(definitions_file=_write_defs(tmp_path, []))
    var_file = tmp_path / "rc-prod.tfvars"
    cmd = orch.build_command("plan", environment="prod", var_files=[var_file])

    assert cmd == [
        "terraform",
        "plan",
        f"-var-file={var_file}",
        "-var",
        f"portal_definitions_file={orch.definitions_file}",
        "-var",
        "deployment_environment=prod",
    ]


def test_build_command_no_auto_approve_for_plan(tmp_path):
    orch = TerraformOrchestrator(definitions_file=_write_defs(tmp_path, []))
    assert "-auto-approve" not in orch.build_command("plan", auto_approve=True)


def _fake_show_json(environment_tag):
    """Build a fake `terraform show -json` payload with one tagged resource."""
    return json.dumps(
        {
            "values": {
                "root_module": {
                    "resources": [
                        {
                            "address": 'aws_lambda_function.mcp_server["boulder-co"]',
                            "values": {"tags_all": {"Environment": environment_tag}},
                        }
                    ]
                }
            }
        }
    )


def _patch_subprocess(monkeypatch, *, show_stdout, show_returncode=0):
    """Stub subprocess.run: `terraform show -json` returns show_stdout, every
    other command (the real terraform action) is recorded and returns rc=0.
    """
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:3] == ["terraform", "show", "-json"]:
            if show_returncode != 0:
                raise subprocess.CalledProcessError(show_returncode, cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout=show_stdout, stderr="")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def test_run_refuses_on_environment_mismatch(tmp_path, monkeypatch):
    orch = TerraformOrchestrator(definitions_file=_write_defs(tmp_path, []))
    calls = _patch_subprocess(monkeypatch, show_stdout=_fake_show_json("prod"))

    rc = orch.run("plan", environment="staging")

    assert rc == 1
    # Only the `terraform show -json` probe ran; the real plan was never invoked.
    assert calls == [["terraform", "show", "-json"]]


def test_run_proceeds_on_environment_match(tmp_path, monkeypatch):
    orch = TerraformOrchestrator(definitions_file=_write_defs(tmp_path, []))
    calls = _patch_subprocess(monkeypatch, show_stdout=_fake_show_json("prod"))

    rc = orch.run("plan", environment="prod")

    assert rc == 0
    assert calls[0] == ["terraform", "show", "-json"]
    assert calls[1][:2] == ["terraform", "plan"]


def test_run_proceeds_when_state_is_empty(tmp_path, monkeypatch):
    orch = TerraformOrchestrator(definitions_file=_write_defs(tmp_path, []))
    calls = _patch_subprocess(monkeypatch, show_stdout="")

    rc = orch.run("plan", environment="staging")

    assert rc == 0
    assert calls[1][:2] == ["terraform", "plan"]


def test_run_proceeds_when_not_yet_initialized(tmp_path, monkeypatch):
    orch = TerraformOrchestrator(definitions_file=_write_defs(tmp_path, []))
    _patch_subprocess(monkeypatch, show_stdout="", show_returncode=1)

    rc = orch.run("plan", environment="staging")

    assert rc == 0


def test_run_skip_environment_check_bypasses_guard(tmp_path, monkeypatch):
    orch = TerraformOrchestrator(definitions_file=_write_defs(tmp_path, []))
    calls = _patch_subprocess(monkeypatch, show_stdout=_fake_show_json("prod"))

    rc = orch.run("plan", environment="staging", skip_environment_check=True)

    assert rc == 0
    # The `terraform show -json` probe never ran; only the real plan did.
    assert len(calls) == 1
    assert calls[0][:2] == ["terraform", "plan"]


def test_parse_app_tokens():
    assert _parse_app_tokens(["detroit-mi=abc", "x=y=z"]) == {
        "detroit-mi": "abc",
        "x": "y=z",
    }


def test_parse_app_tokens_rejects_bad_pair():
    with pytest.raises(ValueError):
        _parse_app_tokens(["nokey"])
