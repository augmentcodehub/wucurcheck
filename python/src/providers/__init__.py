"""Provider auto-discovery."""
from providers._registry import provider_registry
from providers.wucur import WucurProvider  # noqa: F401


def get_provider(name: str):
    """Get a registered provider by name."""
    return provider_registry.get(name)
