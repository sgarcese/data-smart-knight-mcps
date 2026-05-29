# Data Portal Definitions

These portal definitions cover the supported MCP portal sources for the current project.

| City | Portal URL | Portal Type | Notes |
|------|------------|-------------|-------|
| Boulder, CO | https://open-data.bouldercolorado.gov | ArcGIS Hub | Supported by OpenContext.
| Charlotte, NC | https://data.charlottenc.gov | ArcGIS Hub | Supported by OpenContext.
| Columbia, SC | https://coc-colacitygis.opendata.arcgis.com | ArcGIS Hub | Supported by OpenContext.
| Detroit, MI | https://data.detroitmi.gov | Socrata | Supported by OpenContext.
| Lexington, KY | https://data.lexingtonky.gov | CKAN | Supported by OpenContext.
| San Jose, CA | https://data.sanjoseca.gov | CKAN | Supported by OpenContext.
| St. Paul, MN | https://information.stpaul.gov | ArcGIS Hub | Supported by OpenContext.
| West Palm Beach, FL | https://gisportal-wpbgis.opendata.arcgis.com | ArcGIS Hub | Supported by OpenContext.

## Unsupported / skipped sources

- Philadelphia, PA — `opendataphilly.org` uses JKAN (Jekyll-based) and is not supported by OpenContext.
- Long Beach, CA — `data.longbeach.gov` uses OpenDataSoft and is not supported by OpenContext.

## Usage

- The canonical portal definitions are stored in `portal-wrapper/config/portal_definitions.yaml`.
- Update that file when adding or modifying portals.
- Use the wrapper to generate deployment-ready configuration from these values.
