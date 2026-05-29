# Portal Wrapper

This package wraps the `OpenContext` snapshot and provides a central entry point for portal instantiation.

## Purpose

- Load portal definitions for multiple MCP servers.
- Generate or configure portal instances based on city, URL, and portal type.
- Prepare deployment artifacts for AWS.

## Contents

- `portal_manager.py` — core wrapper logic.
- `config/portal_definitions.example.yaml` — example portal definitions.
- `requirements.txt` — wrapper dependencies.

## Getting started

1. Review `docs/portals.md` and define the portal list.
2. Copy `portal-wrapper/config/portal_definitions.example.yaml` to `portal-wrapper/config/portal_definitions.yaml`.
3. Extend `portal_manager.py` with portal creation and deployment logic.
