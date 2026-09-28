"""352 新风 (fresh-air) integration for Home Assistant — local UDP status.

Milestone: live status reading over the LAN (validated against a real G30).
Cloud-based control is a follow-up milestone.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_AUTH_CODE, DEFAULT_COMPANY_CODE, DEVICE_TYPE_BY_MODEL, DOMAIN
from .hub import Air352Hub
from .protocol import DeviceState

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.FAN, Platform.NUMBER, Platform.SWITCH, Platform.SELECT, Platform.SENSOR]

SCAN_INTERVAL = timedelta(seconds=15)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the 352 integration from a config entry."""
    data = entry.data
    mac: str = data[CONF_MAC]
    host: str | None = data.get(CONF_HOST)
    model: str = data.get(CONF_MODEL, "g30")
    device_type: int = data.get("device_type", DEVICE_TYPE_BY_MODEL.get(model, 0x04))
    auth_code: int = data.get("auth_code", DEFAULT_AUTH_CODE)
    company_code: int = data.get("company_code", DEFAULT_COMPANY_CODE)

    hub = Air352Hub(mac=mac, host=host, model=model,
                    device_type=device_type, auth_code=auth_code,
                    company_code=company_code)

    async def _async_update_data() -> DeviceState:
        await hub.async_nudge()  # encourage a status push (harmless)
        return hub.state

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"352 {mac}",
        update_method=_async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    # Status frames arrive asynchronously: fan out immediately to entities.
    hub.register_callback(coordinator.async_update_listeners)

    await hub.start_listener()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "hub": hub,
        "coordinator": coordinator,
    }

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        store = hass.data[DOMAIN].pop(entry.entry_id, None)
        if store and store.get("hub") is not None:
            await store["hub"].close()
    return unload_ok
