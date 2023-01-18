"""The Presence Simulator integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

# TOD List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.SWITCH]


# async def async_setup(hass: HomeAssistant, config: dict[str, Any]):
#     """Import integration from config."""

#     if DOMAIN in config:
#         for entry in config[DOMAIN]:
#             hass.async_create_task(
#                 hass.config_entries.flow.async_init(
#                     DOMAIN, context={CONF_SOURCE: SOURCE_IMPORT}, data=entry
#                 )
#             )
#     return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Presence Simulator from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    # TOD 1. Create API instance
    # TOD 2. Validate the API connection (and authentication)
    # TOD 3. Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
