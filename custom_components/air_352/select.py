"""Select platform for the 352 fresh-air device (PTC / auxiliary heat)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CMD_PTC, DOMAIN, PTC_LEVELS
from .hub import Air352Hub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub: Air352Hub = hass.data[DOMAIN][entry.entry_id]["hub"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([Air352PtcSelect(coordinator, hub, entry)])


class Air352PtcSelect(CoordinatorEntity, SelectEntity):
    """PTC / auxiliary-heat level select."""

    _attr_has_entity_name = True
    _attr_name = "辅热"
    _attr_options = list(PTC_LEVELS.values())

    def __init__(self, coordinator, hub: Air352Hub, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._hub = hub
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_ptc"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}

    @property
    def available(self) -> bool:
        return self._hub.available

    @property
    def current_option(self) -> str | None:
        return PTC_LEVELS.get(self._hub.state.ptc)

    async def async_select_option(self, option: str) -> None:
        for level, name in PTC_LEVELS.items():
            if name == option:
                await self._hub.async_send_command(CMD_PTC, level)
                return
