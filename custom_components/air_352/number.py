"""Number platform: air volume (风量) control in m3/h.

The G30 fan page in HA shows preset-mode chips (auto/sleep/turbo/manual), which
hides the fan's built-in percentage slider.  Air volume on this device is a
continuous 2-byte value (0x58 command), so it gets its own number entity.
Setting it while the device is in a preset mode (auto/sleep) may be ignored;
switch to manual first if so (a direct set is observed to move the device into
manual-wind state).
"""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import AIR_VOLUME_MAX, AIR_VOLUME_MIN, CMD_SPEED, DOMAIN
from .hub import Air352Hub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub: Air352Hub = hass.data[DOMAIN][entry.entry_id]["hub"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([Air352WindVolume(coordinator, hub, entry)])


class Air352WindVolume(CoordinatorEntity, NumberEntity):
    """Wind-volume (air flow) in m3/h."""

    _attr_has_entity_name = True
    _attr_name = "风量"
    _attr_native_min_value = AIR_VOLUME_MIN
    _attr_native_max_value = AIR_VOLUME_MAX
    _attr_native_step = 10
    _attr_native_unit_of_measurement = UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:fan"

    def __init__(self, coordinator, hub: Air352Hub, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._hub = hub
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_wind_volume"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}

    @property
    def available(self) -> bool:
        return self._hub.available

    @property
    def native_value(self) -> float | None:
        ws = self._hub.state.wind_speed
        return float(ws) if ws is not None else None

    async def async_set_native_value(self, value: float) -> None:
        await self._hub.async_send_command(CMD_SPEED, int(value), two_byte_value=True)
