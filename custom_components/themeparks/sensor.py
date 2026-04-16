"""Platform for Theme Park sensor integration."""
from __future__ import annotations

from datetime import timedelta
import logging
import time

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    ATTR_7D_AVERAGE,
    ATTR_7D_MAXIMUM,
    ATTR_7D_MINIMUM,
    ATTR_PARK_NAME,
    ATTR_PARK_STATUS,
    ATTR_OPENING_TIME,
    ATTR_CLOSING_TIME,
    ATTR_SCHEDULE_TYPE,
    ATTR_ALL_SCHEDULES,
    DOMAIN,
    HISTORY_DAYS,
    NAME,
    PARKID,
    STORAGE_KEY,
    STORAGE_VERSION,
    TIME,
    ID,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""

    my_api = hass.data[DOMAIN][config_entry.entry_id]

    # Set up wait time coordinator
    wait_time_coordinator = ThemeParksCoordinator(hass, my_api, config_entry.entry_id)
    await wait_time_coordinator.async_config_entry_first_refresh()

    # Set up park schedule coordinator
    park_schedule_coordinator = ParkScheduleCoordinator(hass, my_api, config_entry.entry_id)
    await park_schedule_coordinator.async_config_entry_first_refresh()

    _LOGGER.info("Config entry first refresh completed, adding entities")

    # Create attraction sensors
    attraction_entities = [
        AttractionSensor(wait_time_coordinator, idx)
        for idx in wait_time_coordinator.data.keys()
    ]

    # Create park status sensors
    park_entities = [
        ParkSensor(park_schedule_coordinator, idx)
        for idx in park_schedule_coordinator.data.keys()
    ]

    all_entities = attraction_entities + park_entities

    _LOGGER.info(
        "Entities to add (count: %s): %s", str(all_entities.__len__), str(all_entities)
    )
    async_add_entities(all_entities)


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
        attraction_data = self.coordinator.data.get(self.idx, {})
        return {
            ATTR_PARK_NAME: self._park_name,
            ATTR_7D_AVERAGE: attraction_data.get(ATTR_7D_AVERAGE),
            ATTR_7D_MINIMUM: attraction_data.get(ATTR_7D_MINIMUM),
            ATTR_7D_MAXIMUM: attraction_data.get(ATTR_7D_MAXIMUM),
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
        self._store = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry_id}"
        )
        self._history: dict[str, list[list]] = {}
        self._stats: dict[str, dict] = {}

    async def _async_load_history(self):
        """Load wait time history from persistent storage."""
        stored = await self._store.async_load()
        if stored and isinstance(stored, dict):
            self._history = stored
        _LOGGER.debug(
            "Loaded wait history for %s attractions", len(self._history)
        )

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        _LOGGER.debug("Calling do_live_lookup in ThemeParksCoordinator")

        if not self._history:
            await self._async_load_history()

        data = await self.api.do_live_lookup()

        now = time.time()
        cutoff = now - (HISTORY_DAYS * 86400)

        for attraction_id, attraction_data in data.items():
            wait = attraction_data[TIME]
            if wait is None:
                continue

            history = self._history.setdefault(attraction_id, [])
            history.append([now, wait])

        for attraction_id in list(self._history):
            self._history[attraction_id] = [
                entry for entry in self._history[attraction_id]
                if entry[0] >= cutoff
            ]
            if not self._history[attraction_id]:
                del self._history[attraction_id]

        self._compute_stats()

        self.hass.async_create_task(self._store.async_save(self._history))

        for attraction_id, attraction_data in data.items():
            stats = self._stats.get(attraction_id, {})
            attraction_data[ATTR_7D_AVERAGE] = stats.get(ATTR_7D_AVERAGE)
            attraction_data[ATTR_7D_MINIMUM] = stats.get(ATTR_7D_MINIMUM)
            attraction_data[ATTR_7D_MAXIMUM] = stats.get(ATTR_7D_MAXIMUM)

        return data

    def _compute_stats(self):
        """Compute 7-day average, min, and max for all attractions."""
        self._stats = {}
        for attraction_id, history in self._history.items():
            waits = [entry[1] for entry in history]
            if not waits:
                continue
            self._stats[attraction_id] = {
                ATTR_7D_AVERAGE: round(sum(waits) / len(waits), 1),
                ATTR_7D_MINIMUM: min(waits),
                ATTR_7D_MAXIMUM: max(waits),
            }


class ParkSensor(SensorEntity, CoordinatorEntity):
    """Sensor for park status."""

    def __init__(self, coordinator, idx):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.idx = idx
        park_data = coordinator.data[idx]

        self._attr_name = f"{park_data[NAME]} Status"
        self._attr_native_value = park_data[ATTR_PARK_STATUS]
        self._attr_unique_id = f"{coordinator.entry_id}_{park_data[ID]}_status"

        # Device info for park
        self._attr_device_info = {
            "identifiers": {(DOMAIN, park_data[ID])},
            "name": park_data[NAME],
            "manufacturer": "Theme Parks",
            "model": "Theme Park",
        }

        self._park_id = park_data[ID]
        self._park_name = park_data[NAME]

        _LOGGER.debug("Adding ParkSensor for %s", self._park_name)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        park_data = self.coordinator.data.get(self.idx, {})
        return {
            ATTR_OPENING_TIME: park_data.get(ATTR_OPENING_TIME),
            ATTR_CLOSING_TIME: park_data.get(ATTR_CLOSING_TIME),
            ATTR_SCHEDULE_TYPE: park_data.get(ATTR_SCHEDULE_TYPE),
            ATTR_ALL_SCHEDULES: park_data.get(ATTR_ALL_SCHEDULES, []),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        park_data = self.coordinator.data.get(self.idx, {})
        new_status = park_data.get(ATTR_PARK_STATUS)
        _LOGGER.debug(
            "Setting updated status from coordinator for %s to %s",
            str(self._attr_name),
            str(new_status),
        )
        self._attr_native_value = new_status
        self.async_write_ha_state()


class ParkScheduleCoordinator(DataUpdateCoordinator):
    """Park schedule coordinator."""

    def __init__(self, hass, api, entry_id):
        """Initialize park schedule coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Theme Park Schedule Sensor",
            update_interval=timedelta(minutes=15),
        )
        self.api = api
        self.entry_id = entry_id

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        _LOGGER.debug("Calling do_schedule_lookup in ParkScheduleCoordinator")
        return await self.api.do_schedule_lookup()
