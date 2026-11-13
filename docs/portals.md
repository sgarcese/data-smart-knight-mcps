# Data Portal Definitions

The portals deployed by this project. The source of truth is
`portal-wrapper/config/portal_definitions.yaml` — keep this table in sync when
adding or changing a portal. Each one is served at
`https://<slug>.responsive.city/mcp` (`portal_manager.py list` prints the slugs).

| City | Portal URL | Portal Type | Notes |
|------|------------|-------------|-------|
| Austin, TX | https://data.austintexas.gov | Socrata | Supported by OpenContext. Requires a Socrata app token.
| Bakersfield, CA | https://bakersfielddatalibrary-cob.opendata.arcgis.com | ArcGIS Hub | Supported by OpenContext.
| Bogotá, Colombia | https://datosabiertos.bogota.gov.co | CKAN | Supported by OpenContext.
| Boulder, CO | https://open-data.bouldercolorado.gov | ArcGIS Hub | Supported by OpenContext.
| Cali, Colombia | https://datos.cali.gov.co | CKAN | Supported by OpenContext.
| California | https://data.ca.gov | CKAN | Statewide. Supported by OpenContext.
| Charlotte, NC | https://data.charlottenc.gov | ArcGIS Hub | Supported by OpenContext.
| Colorado | https://data.colorado.gov | Socrata | Statewide. Supported by OpenContext. Requires a Socrata app token.
| Columbia, SC | https://coc-colacitygis.opendata.arcgis.com | ArcGIS Hub | Supported by OpenContext.
| Detroit, MI | https://data.detroitmi.gov | ArcGIS Hub | Supported by OpenContext.
| Hawaii | https://opendata.hawaii.gov | CKAN | Statewide. Supported by OpenContext.
| HUD | https://hudgis-hud.opendata.arcgis.com | ArcGIS Hub | Federal agency (U.S. Dept. of Housing and Urban Development). Supported by OpenContext.
| Indiana | https://hub.mph.in.gov | CKAN | Management Performance Hub (statewide). Supported by OpenContext.
| Lexington, KY | https://data.lexingtonky.gov | ArcGIS Hub | Supported by OpenContext.
| Long Beach, CA | https://data.longbeach.gov | Opendatasoft | Explore v2.1. Supported by OpenContext.
| Los Angeles, CA | https://data.lacity.org | Socrata | Supported by OpenContext. Requires a Socrata app token.
| New York | https://data.ny.gov | Socrata | Statewide. Supported by OpenContext. Requires a Socrata app token.
| New York City, NY | https://data.cityofnewyork.us | Socrata | Supported by OpenContext. Requires a Socrata app token.
| Philadelphia, PA | https://data-phl.opendata.arcgis.com | ArcGIS Hub | Geospatial portal. **Incomplete coverage** — carries a user-facing `warning`.
| San Francisco, CA | https://data.sf.gov | Socrata | DataSF. Supported by OpenContext. Requires a Socrata app token. Migrated from data.sfgov.org (2026-09); the old domain 301s every API path (the plugin now follows redirects, but the definition points at the new domain).
| San Jose, CA | https://data.sanjoseca.gov | CKAN | Supported by OpenContext.
| Sarasota County, FL | https://data-sarco.opendata.arcgis.com | ArcGIS Hub | Supported by OpenContext.
| St. Paul, MN | https://information.stpaul.gov | ArcGIS Hub | Supported by OpenContext.
| Texas | https://data.texas.gov | Socrata | Statewide. Supported by OpenContext. Requires a Socrata app token.
| Washington | https://data.wa.gov | Socrata | Statewide. Supported by OpenContext. Requires a Socrata app token.
| West Palm Beach, FL | https://gisportal-wpbgis.opendata.arcgis.com | ArcGIS Hub | Supported by OpenContext.

## Definition fields

Definitions live in `portal-wrapper/config/portal_definitions.yaml`. Required:
`city`, `url`, `type` (`arcgis` | `socrata` | `ckan` | `opendatasoft`). Optional: `notes`
(internal only) and `warning` (appended to the MCP server description shown to
users — use it to flag incomplete or limited portals, as with Philadelphia).

## Socrata credentials: App Token, not API Key

Socrata portals (`type: socrata`) require a credential in `portal_app_tokens`
(`portal-wrapper/terraform/secret.auto.tfvars`, gitignored). Socrata's
developer console issues two different credential types — only one of them
works here:

- **App Token** — a single string from a portal's *Developer Settings → App
  Tokens* (or `dev.socrata.com/register`). This is what's required: the
  plugin (`opencontext/plugins/socrata/plugin.py`) sends it bare as the
  `X-App-Token` header.
- **API Key (Key ID + Key Secret)** — a newer credential *pair* from
  *Developer Settings → API Keys*, meant for HTTP Basic Auth on authenticated
  requests (writes, private datasets). The plugin does not implement Basic
  Auth. Pasting only the Key ID in as if it were an App Token will look like
  it works for catalog search and dataset metadata, but fails with
  `"Invalid app_token specified"` (HTTP 403) on the actual data-query
  endpoint (`/resource/{id}.json`) that `query_dataset` uses — i.e. it fails
  silently for some tools and not others. Confirmed on data.ny.gov,
  data.cityofnewyork.us, data.lacity.org, and data.sfgov.org.
- No secret/private key is needed for these portals — all datasets are
  public, so the bare App Token is sufficient. No plugin auth changes are
  needed either.

## Unsupported / skipped sources

- Philadelphia, PA — the broader `opendataphilly.org` catalog uses JKAN
  (Jekyll-based) and is not supported by OpenContext. The separate ArcGIS Hub
  geospatial portal (`data-phl.opendata.arcgis.com`, listed above) is supported.
- "Cities by the Numbers" (California State Controller's Office), `cities.bythenumbers.sco.ca.gov` — runs on Tyler Technologies' "Socrata Perspectives" financial-transparency product (Tyler acquired Socrata in 2018; the UI still carries Socrata-branded CSS/template namespaces). It is not a standard Socrata Open Data Portal: it exposes its own bespoke `/api/*.json` and `.csv` endpoints rather than the SODA3 + Discovery API the `socrata` plugin talks to, so it is not supported by OpenContext without new plugin code.
