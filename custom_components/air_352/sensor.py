"""Sensor platform for the 352 fresh-air device (fields validated live)."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .hub import Air352Hub


@dataclass(frozen=True)
class Air352SensorDescription(SensorEntityDescription):
    key: str = ""
    accessor: str = ""


# Only fields that decode to sane live values (verified against a real G30).
SENSORS: tuple[Air352SensorDescription, ...] = (
    Air352SensorDescription(
        key="pm25",
        accessor="pm25",
        name="PM2.5",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    Air352SensorDescription(
        key="co2",
        accessor="co2",
        name="CO₂",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    Air352SensorDescription(
        key="temperature",
        accessor="temperature",
        name="温度",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    Air352SensorDescription(
        key="humidity",
        accessor="humidity",
        name="湿度",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    Air352SensorDescription(
        key="wind_speed",
        accessor="wind_speed",
        name="风量",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="m³/h",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub: Air352Hub = hass.data[DOMAIN][entry.entry_id]["hub"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        [Air352Sensor(coordinator, hub, entry, desc) for desc in SENSORS]
    )


class Air352Sensor(CoordinatorEntity, SensorEntity):
    """A sensor backed by the parsed 352 status frames."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, hub: Air352Hub, entry: ConfigEntry, desc: Air352SensorDescription) -> None:
        super().__init__(coordinator)
        self._hub = hub
        self._entry = entry
        self.entity_description = desc
        self._attr_unique_id = f"{entry.entry_id}_{desc.key}"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}

    @property
    def available(self) -> bool:
        return self._hub.available

    @property
    def native_value(self):
        return getattr(self._hub.state, self.entity_description.accessor, None)
