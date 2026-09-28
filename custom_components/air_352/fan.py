"""Fan platform for the 352 fresh-air device (status via local UDP)."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (AIR_VOLUME_MAX, AIR_VOLUME_MIN, CMD_MODE, CMD_POWER, CMD_SPEED, DOMAIN, PRESET_MODES, VALUE_OFF, VALUE_ON)
from .hub import Air352Hub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub: Air352Hub = hass.data[DOMAIN][entry.entry_id]["hub"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([Air352Fan(coordinator, hub, entry)])


class Air352Fan(CoordinatorEntity, FanEntity):
    """Representation of the 352 fresh-air fan (read status, control TBD-cloud)."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator, hub: Air352Hub, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._hub = hub
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_fan"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._entry.title,
            "manufacturer": "352",
            "model": self._hub.model,
        }

    @property
    def available(self) -> bool:
        return self._hub.available

    @property
    def supported_features(self) -> int:
        return (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )

    @property
    def is_on(self) -> bool:
        # power byte only: on=0x00/off=0x11 (verified live). wind_speed keeps a
        # stale value after shutdown, so it must not gate is_on.
        return self._hub.state.power is True

    @property
    def preset_modes(self) -> list[str] | None:
        return list(PRESET_MODES.values())

    @property
    def preset_mode(self) -> str | None:
        return PRESET_MODES.get(self._hub.state.mode)

    @property
    def percentage(self) -> int | None:
        speed = self._hub.state.wind_speed
        if speed is None or speed == 0:
            return None
        span = AIR_VOLUME_MAX - AIR_VOLUME_MIN
        return max(0, min(100, round((speed - AIR_VOLUME_MIN) / span * 100)))

    @property
    def speed_count(self) -> int:
        return 100

    async def async_turn_on(self, percentage=None, preset_mode=None, **kwargs: Any) -> None:
        self._hub.optimistic_power(True)
        await self._hub.async_send_command(CMD_POWER, VALUE_ON)
        if percentage is not None:
            await self.async_set_percentage(percentage)
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._hub.optimistic_power(False)
        await self._hub.async_send_command(CMD_POWER, VALUE_OFF)

    async def async_set_percentage(self, percentage: int) -> None:
        span = AIR_VOLUME_MAX - AIR_VOLUME_MIN
        volume = AIR_VOLUME_MIN + round(percentage / 100.0 * span)
        await self._hub.async_send_command(CMD_SPEED, volume, two_byte_value=True)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        for mode_value, name in PRESET_MODES.items():
            if name == preset_mode:
                await self._hub.async_send_command(CMD_MODE, mode_value)
                return
