"""Platform for Theme Park sensor integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import ATTR_PARK_NAME, DOMAIN, NAME, PARKID, TIME, ID

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""

    my_api = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = ThemeParksCoordinator(hass, my_api, config_entry.entry_id)

    await coordinator.async_config_entry_first_refresh()

    _LOGGER.info("Config entry first refresh completed, adding entities")
    entities = [AttractionSensor(coordinator, idx) for idx in coordinator.data.keys()]

    _LOGGER.info(
        "Entities to add (count: %s): %s", str(entities.__len__), str(entities)
    )
    async_add_entities(entities)


class AttractionSensor(SensorEntity, CoordinatorEntity):
    """An entity using CoordinatorEntity."""

    def __init__(self, coordinator, idx):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.idx = idx
        attraction_data = coordinator.data[idx]

        self._attr_name = attraction_data[NAME]
        self._attr_native_unit_of_measurement = UnitOfTime.MINUTES
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = attraction_data[TIME]
        self._attr_unique_id = f"{coordinator.entry_id}_{attraction_data[ID]}"

        # Use parkId for device association
        park_id = attraction_data.get(PARKID)
        self._park_name = attraction_data.get(ATTR_PARK_NAME, "Unknown Park")

        if park_id:
            self._attr_device_info = {
                "identifiers": {(DOMAIN, park_id)},
                "name": self._park_name,
                "manufacturer": "Theme Parks",
                "model": "Theme Park",
            }
        else:
            # Fallback to entry_id if parkId not available
            self._attr_device_info = {
                "identifiers": {(DOMAIN, self.coordinator.entry_id)},
                "name": self.coordinator.api._parkname,
                "manufacturer": "Theme Parks",
                "model": "Wait Times",
            }

        _LOGGER.debug("Adding AttractionSensor called %s to park %s", self._attr_name, self._park_name)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_PARK_NAME: self._park_name,
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        newtime = self.coordinator.data[self.idx][TIME]
        _LOGGER.debug(
            "Setting updated time from coordinator for %s to %s",
            str(self._attr_name),
            str(newtime),
        )
        self._attr_native_value = newtime
        self.async_write_ha_state()


class ThemeParksCoordinator(DataUpdateCoordinator):
    """Theme parks coordinator."""

    def __init__(self, hass, api, entry_id):
        """Initialize theme parks coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Theme Park Wait Time Sensor",
            update_interval=timedelta(minutes=5),
        )
        self.api = api
        self.entry_id = entry_id

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        _LOGGER.debug("Calling do_live_lookup in ThemeParksCoordinator")
        return await self.api.do_live_lookup()
