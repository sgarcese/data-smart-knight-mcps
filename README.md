# OpenContext MCP Portal Wrapper

This repository contains a local snapshot of `OpenContext` and a wrapper project for instantiating Data Portals for MCP servers.

## Structure

- `opencontext/` — local snapshot of the OpenContext source tree.
- `portal-wrapper/` — wrapper code and portal deployment scaffolding.
- `docs/` — architectural decisions and portal definitions.

## Goals

- Keep the OpenContext source state under version control.
- Build a reusable portal wrapper around the snapshot.
- Support deployment to AWS using the same infrastructure approach across MCP servers.

## Next steps

1. Populate `docs/portals.md` with city, URL, and portal-type definitions.
2. Implement portal instantiation and AWS deployment automation in `portal-wrapper/`.
3. Keep changes small and branch-based, with documentation updates before merging.
