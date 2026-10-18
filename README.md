# OpenContext MCP Portal Wrapper

Deploys one [OpenContext](https://github.com/sgarcese/OpenContext) MCP server
per open data portal (cities, states, and federal agencies) to AWS Lambda. In
production each portal is served at `https://<slug>.responsive.city/mcp`, e.g.
`https://hud.responsive.city/mcp`.

## Structure

- `opencontext/` — vendored snapshot of the OpenContext source (the Lambda runtime).
- `portal-wrapper/` — portal definitions, the `portal_manager.py` CLI, Terraform,
  and a local usage dashboard. See [portal-wrapper/README.md](portal-wrapper/README.md).
- `docs/` — [portal list](docs/portals.md), [architecture](docs/architecture.md),
  and the [AWS deployment runbook](docs/aws-deployment.md).

## Adding a portal

1. Add it to `portal-wrapper/config/portal_definitions.yaml` and the table in
   `docs/portals.md`.
2. `python portal-wrapper/portal_manager.py validate`
3. Plan and apply per [aws-deployment.md §10](docs/aws-deployment.md#10-responsive-cities-deployment-rc-deploy-role-slugresponsivecity).
   A new portal should plan as add-only.

## Updating OpenContext

`opencontext/` is a hand-synced copy of
[sgarcese/OpenContext](https://github.com/sgarcese/OpenContext) `main`, not a
submodule. Each sync commit names the upstream range it covers
(`git log -- opencontext`).

1. Diff upstream runtime code (`core/`, `plugins/`, `server/`) from the last
   synced upstream commit to `main`, and confirm the vendored files still match
   the last-synced version before copying the changed ones over.
2. Run the vendored tests:
   ```bash
   cd opencontext
   uv run --frozen --with-requirements requirements-dev.txt pytest -q
   ```
   Upstream's own new tests can be run against the vendored code too (with
   `-o asyncio_mode=auto` if run outside this directory).
3. Commit the sync, then redeploy — a code-only change plans as one in-place
   update per portal Lambda (see
   [aws-deployment.md §10](docs/aws-deployment.md#10-responsive-cities-deployment-rc-deploy-role-slugresponsivecity)).
