"""Portal wrapper for generating MCP Data Portals from an OpenContext snapshot."""

import pathlib
import yaml

ROOT = pathlib.Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "config" / "portal_definitions.yaml"


class PortalManager:
    """Manage portal definitions and wrapper instantiation."""

    def __init__(self, config_path: pathlib.Path | None = None):
        self.config_path = config_path or CONFIG_FILE
        self.portals = self._load_portal_definitions()

    def _load_portal_definitions(self) -> list[dict]:
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Portal definitions file not found: {self.config_path}"
            )

        with self.config_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)

        return data.get("portals", [])

    def list_portals(self) -> list[dict]:
        """Return the loaded portal definitions."""
        return self.portals

    def instantiate_portal(self, portal_definition: dict) -> None:
        """Instantiate or configure a portal from a single definition."""
        supported_types = {"arcgis", "socrata", "ckan"}
        city = portal_definition.get("city")
        url = portal_definition.get("url")
        portal_type = portal_definition.get("type")

        if portal_type not in supported_types:
            raise ValueError(
                f"Unsupported portal type '{portal_type}' for {city}. "
                "Supported types are: arcgis, socrata, ckan."
            )

        print(f"Instantiating portal for {city}: {url} ({portal_type})")

    def instantiate_all(self) -> None:
        """Instantiate all portals loaded from configuration."""
        for portal_def in self.portals:
            self.instantiate_portal(portal_def)


if __name__ == "__main__":
    manager = PortalManager()
    manager.instantiate_all()
