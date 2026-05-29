# Portal Wrapper

This package wraps the `OpenContext` snapshot and provides a central entry point for portal instantiation.

## Purpose

- Load portal definitions for multiple MCP servers.
- Generate or configure portal instances based on city, URL, and portal type.
- Prepare deployment artifacts for AWS.

## Contents

- `portal_manager.py` — core wrapper logic.
- `config/portal_definitions.yaml` — active portal definitions.
- `config/portal_definitions.example.yaml` — example portal definitions.
- `requirements.txt` — wrapper dependencies.

## Supported portals

Current supported portal sources:
- ArcGIS Hub
- Socrata
- CKAN

Unsupported portals are intentionally skipped because OpenContext does not support JKAN or OpenDataSoft.

## Getting started

1. Review `docs/portals.md` and the supported portal list.
2. Add or update `portal-wrapper/config/portal_definitions.yaml`.
3. Run `python portal-wrapper/portal_manager.py` to load the portal definitions and instantiate them.
4. Extend `portal_manager.py` with actual portal creation and AWS deployment logic.
