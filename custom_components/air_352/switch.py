"""Switch platform for the 352 fresh-air device (display light)."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CMD_LIGHT, DOMAIN, VALUE_OFF, VALUE_ON
from .hub import Air352Hub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub: Air352Hub = hass.data[DOMAIN][entry.entry_id]["hub"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([Air352LightSwitch(coordinator, hub, entry)])


class Air352LightSwitch(CoordinatorEntity, SwitchEntity):
    """Display-light (on/off confirmed working via local UDP)."""

    _attr_has_entity_name = True
    _attr_name = "显示灯"

    def __init__(self, coordinator, hub: Air352Hub, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._hub = hub
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_light"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}

    @property
    def available(self) -> bool:
        return self._hub.available

    @property
    def is_on(self) -> bool:
        return self._hub.state.light is True

    async def async_turn_on(self, **kwargs) -> None:
        await self._hub.async_send_command(CMD_LIGHT, VALUE_ON)

    async def async_turn_off(self, **kwargs) -> None:
        await self._hub.async_send_command(CMD_LIGHT, VALUE_OFF)
