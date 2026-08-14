# Data Portal Definitions

These portal definitions cover the supported MCP portal sources for the current project.

| City | Portal URL | Portal Type | Notes |
|------|------------|-------------|-------|
| Boulder, CO | https://open-data.bouldercolorado.gov | ArcGIS Hub | Supported by OpenContext.
| California | https://data.ca.gov | CKAN | Statewide. Supported by OpenContext.
| Charlotte, NC | https://data.charlottenc.gov | ArcGIS Hub | Supported by OpenContext.
| Columbia, SC | https://coc-colacitygis.opendata.arcgis.com | ArcGIS Hub | Supported by OpenContext.
| Detroit, MI | https://data.detroitmi.gov | ArcGIS Hub | Supported by OpenContext.
| Hawaii | https://opendata.hawaii.gov | CKAN | Statewide. Supported by OpenContext.
| Indiana | https://hub.mph.in.gov | CKAN | Management Performance Hub (statewide). Supported by OpenContext.
| Lexington, KY | https://data.lexingtonky.gov | ArcGIS Hub | Supported by OpenContext.
| Los Angeles, CA | https://data.lacity.org | Socrata | Supported by OpenContext. Requires a Socrata app token.
| Philadelphia, PA | https://data-phl.opendata.arcgis.com | ArcGIS Hub | Geospatial portal. **Incomplete coverage** — carries a user-facing `warning`.
| San Francisco, CA | https://data.sfgov.org | Socrata | DataSF. Supported by OpenContext. Requires a Socrata app token.
| San Jose, CA | https://data.sanjoseca.gov | CKAN | Supported by OpenContext.
| St. Paul, MN | https://information.stpaul.gov | ArcGIS Hub | Supported by OpenContext.
| West Palm Beach, FL | https://gisportal-wpbgis.opendata.arcgis.com | ArcGIS Hub | Supported by OpenContext.

## Definition fields

Definitions live in `portal-wrapper/config/portal_definitions.yaml`. Required:
`city`, `url`, `type` (`arcgis` | `socrata` | `ckan`). Optional: `notes`
(internal only) and `warning` (appended to the MCP server description shown to
users — use it to flag incomplete or limited portals, as with Philadelphia).

## Unsupported / skipped sources

- Philadelphia, PA — the broader `opendataphilly.org` catalog uses JKAN
  (Jekyll-based) and is not supported by OpenContext. The separate ArcGIS Hub
  geospatial portal (`data-phl.opendata.arcgis.com`, listed above) is supported.
- Long Beach, CA — `data.longbeach.gov` uses OpenDataSoft and is not supported by OpenContext.
- "Cities by the Numbers" (California State Controller's Office), `cities.bythenumbers.sco.ca.gov` — runs on Tyler Technologies' "Socrata Perspectives" financial-transparency product (Tyler acquired Socrata in 2018; the UI still carries Socrata-branded CSS/template namespaces). It is not a standard Socrata Open Data Portal: it exposes its own bespoke `/api/*.json` and `.csv` endpoints rather than the SODA3 + Discovery API the `socrata` plugin talks to, so it is not supported by OpenContext without new plugin code.

## Usage

- The canonical portal definitions are stored in `portal-wrapper/config/portal_definitions.yaml`.
- Update that file when adding or modifying portals.
- Use the wrapper to generate deployment-ready configuration from these values.
