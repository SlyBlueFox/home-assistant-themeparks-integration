"""The Theme Park Wait Times integration."""
from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.httpx_client import get_async_client

from .const import (
    ATTR_PARK_NAME,
    ATTR_PARK_STATUS,
    ATTR_OPENING_TIME,
    ATTR_CLOSING_TIME,
    ATTR_SCHEDULE_TYPE,
    ATTR_ALL_SCHEDULES,
    CLOSING_TIME,
    DATE,
    DESCRIPTION,
    DESTINATIONS,
    DESTINATIONS_URL,
    DOMAIN,
    ENTITY_BASE_URL,
    ENTITY_TYPE,
    ID,
    LIVE,
    LIVE_DATA,
    METHOD_GET,
    NAME,
    OPENING_TIME,
    PARKID,
    PARKNAME,
    PARKSLUG,
    QUEUE,
    SCHEDULE,
    SCHEDULE_DATA,
    SCHEDULE_TYPE,
    SLUG,
    STANDBY,
    TIME,
    TYPE_ATTRACTION,
    TYPE_OPERATING,
    TYPE_SHOW,
    TYPE_TICKETED_EVENT,
    TYPE_PRIVATE_EVENT,
    WAIT_TIME,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


class ThemeParksAPIError(Exception):
    """Raised when the themeparks.wiki API returns an unexpected response."""


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Theme Park Wait Times from a config entry."""
    data = hass.data.setdefault(DOMAIN, {})

    api = ThemeParkAPI(hass, entry)
    await api.async_initialize()

    data[entry.entry_id] = api

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        connections=None,
        name=entry.title,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class ThemeParkAPI:
    """Wrapper for theme parks API."""

    # -- Set in async_initialize --
    ha_device_registry: dr.DeviceRegistry
    ha_entity_registry: er.EntityRegistry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the gateway."""
        self._hass = hass
        self._config_entry = config_entry
        self._parkslug = config_entry.data[PARKSLUG]
        self._parkname = config_entry.data[PARKNAME]
        self._park_cache = {}  # Cache park names by parkId

    async def async_initialize(self) -> None:
        """Initialize controller and connect radio."""
        self.ha_device_registry = dr.async_get(self._hass)
        self.ha_entity_registry = er.async_get(self._hass)

    async def do_live_lookup(self):
        """Do API lookup of the 'live' page of this park."""
        _LOGGER.debug("Running do_live_lookup in ThemeParkAPI")

        items_data = await self.do_api_lookup()

        # Build park name cache from PARK entities
        for item in items_data:
            if item[ENTITY_TYPE] == "PARK":
                self._park_cache[item[ID]] = item[NAME]

        # Some destinations (e.g. Universal Orlando Resort) do not include
        # PARK entities in their /live response. Backfill the cache from the
        # destinations list so attraction park_name attributes are populated.
        if any(
            item.get(PARKID) and item[PARKID] not in self._park_cache
            for item in items_data
            if item.get(ENTITY_TYPE) in (TYPE_SHOW, TYPE_ATTRACTION)
        ):
            for park in await self._get_destination_parks():
                self._park_cache.setdefault(park[ID], park[NAME])

        # Filter to attractions and shows only
        items = filter(
            lambda item: item[ENTITY_TYPE] in [TYPE_SHOW, TYPE_ATTRACTION],
            items_data
        )

        def parse_live(item):
            """Parse live data from API."""

            _LOGGER.debug("Parsed API item for: %s", item[NAME])

            park_id = item.get(PARKID)
            park_name = self._park_cache.get(park_id, self._parkname)
            name = item[NAME]

            wait_time = None
            if "queue" in item and "STANDBY" in item[QUEUE]:
                wait_time = item[QUEUE][STANDBY][WAIT_TIME]
                _LOGGER.debug("Time found")
            else:
                _LOGGER.debug("No queue/STANDBY in item")

            return (
                item[ID],
                {
                    ID: item[ID],
                    NAME: name,
                    TIME: wait_time,
                    PARKID: park_id,
                    ATTR_PARK_NAME: park_name,
                },
            )

        return dict(map(parse_live, items))

    async def do_api_lookup(self):
        """Lookup the subpage and subfield in the API."""
        items_data = await self._fetch_live(self._parkslug)

        if items_data is None or LIVE_DATA not in items_data:
            # Stored slug is no longer valid (themeparks.wiki occasionally
            # renames destination slugs, e.g. universalorlando ->
            # universalresort_orlando). Try to recover by looking up the
            # current slug by park name.
            _LOGGER.warning(
                "Live data not found for slug '%s'; attempting to resolve "
                "current slug for park '%s'",
                self._parkslug,
                self._parkname,
            )
            new_slug = await self._resolve_current_slug()
            if new_slug and new_slug != self._parkslug:
                _LOGGER.info(
                    "Updating park slug for '%s' from '%s' to '%s'",
                    self._parkname,
                    self._parkslug,
                    new_slug,
                )
                self._parkslug = new_slug
                self._hass.config_entries.async_update_entry(
                    self._config_entry,
                    data={**self._config_entry.data, PARKSLUG: new_slug},
                )
                items_data = await self._fetch_live(new_slug)

        if items_data is None or LIVE_DATA not in items_data:
            raise ThemeParksAPIError(
                f"API response for '{self._parkslug}' did not contain "
                f"'{LIVE_DATA}'. The destination slug may be invalid or the "
                "themeparks.wiki API is unavailable."
            )

        return items_data[LIVE_DATA]

    async def _fetch_live(self, slug: str):
        """Fetch the /live endpoint for a slug, returning None on HTTP error."""
        url = f"{ENTITY_BASE_URL}/{slug}/{LIVE}"
        client = get_async_client(self._hass)
        try:
            response = await client.request(
                METHOD_GET,
                url,
                timeout=30,
                follow_redirects=True,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error requesting %s: %s", url, err)
            return None

        if response.status_code != 200:
            _LOGGER.error(
                "Unexpected status %s fetching %s",
                response.status_code,
                url,
            )
            return None

        try:
            return response.json()
        except ValueError as err:
            _LOGGER.error("Invalid JSON from %s: %s", url, err)
            return None

    async def _resolve_current_slug(self) -> str | None:
        """Look up the current slug for the configured park name."""
        destination = await self._get_destination()
        if destination and destination.get(SLUG):
            return destination[SLUG]
        return None

    async def _get_destination_parks(self) -> list[dict]:
        """Return parks (id + name) for the configured destination."""
        destination = await self._get_destination()
        if not destination:
            return []
        return [
            {ID: park[ID], NAME: park[NAME]}
            for park in destination.get("parks", [])
            if park.get(ID) and park.get(NAME)
        ]

    async def _get_destination(self) -> dict | None:
        """Return the destinations-list entry matching this config entry."""
        client = get_async_client(self._hass)
        try:
            response = await client.request(
                METHOD_GET,
                DESTINATIONS_URL,
                timeout=10,
                follow_redirects=True,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error fetching destinations list: %s", err)
            return None

        if response.status_code != 200:
            _LOGGER.error(
                "Unexpected status %s fetching destinations list",
                response.status_code,
            )
            return None

        try:
            payload = response.json()
        except ValueError as err:
            _LOGGER.error("Invalid JSON from destinations list: %s", err)
            return None

        # Prefer a slug match (resilient to destination renames); fall back
        # to a name match so slug migrations still work.
        by_slug = None
        by_name = None
        for dest in payload.get(DESTINATIONS, []):
            if dest.get(SLUG) == self._parkslug:
                by_slug = dest
                break
            if dest.get(NAME) == self._parkname:
                by_name = dest

        return by_slug or by_name

    async def do_schedule_lookup(self):
        """Fetch schedule data for parks."""
        _LOGGER.debug("Running do_schedule_lookup in ThemeParkAPI")

        items_data = await self.do_api_lookup()
        park_schedules = {}

        # Get all park entities
        parks = [
            {ID: item[ID], NAME: item[NAME]}
            for item in items_data
            if item.get(ENTITY_TYPE) == "PARK"
        ]

        # Fall back to the destinations list when /live has no PARK entries
        # (e.g. Universal Orlando Resort).
        if not parks:
            parks = await self._get_destination_parks()

        for park in parks:
            park_id = park[ID]
            park_name = park[NAME]

            try:
                schedule_data = await self.fetch_schedule(park_id)
                park_status = self.parse_schedule(schedule_data)

                park_schedules[park_id] = {
                    ID: park_id,
                    NAME: park_name,
                    ATTR_PARK_STATUS: park_status["status"],
                    ATTR_OPENING_TIME: park_status.get("opening_time"),
                    ATTR_CLOSING_TIME: park_status.get("closing_time"),
                    ATTR_SCHEDULE_TYPE: park_status.get("schedule_type"),
                    ATTR_ALL_SCHEDULES: park_status.get("all_schedules", []),
                }
                _LOGGER.debug("Park %s status: %s", park_name, park_status["status"])
            except Exception as err:
                _LOGGER.error("Error fetching schedule for park %s: %s", park_name, err)

        return park_schedules

    async def fetch_schedule(self, entity_id: str):
        """Fetch schedule data for a specific entity."""
        url = f"{ENTITY_BASE_URL}/{entity_id}/{SCHEDULE}"

        client = get_async_client(self._hass)
        response = await client.request(
            METHOD_GET,
            url,
            timeout=30,
            follow_redirects=True,
        )

        return response.json()

    def parse_schedule(self, schedule_data):
        """Parse schedule data to determine current park status."""
        if SCHEDULE_DATA not in schedule_data:
            return {"status": "Unknown"}

        schedule_entries = schedule_data[SCHEDULE_DATA]
        if not schedule_entries:
            return {"status": "Unknown"}

        # Get timezone from schedule data
        try:
            # Parse timezone from first entry's time
            first_entry = schedule_entries[0]
            if OPENING_TIME in first_entry:
                sample_time = datetime.fromisoformat(first_entry[OPENING_TIME])
                now = datetime.now(sample_time.tzinfo)
            else:
                # Fallback to UTC if no time available
                from datetime import timezone
                now = datetime.now(timezone.utc)
        except (ValueError, KeyError, IndexError):
            from datetime import timezone
            now = datetime.now(timezone.utc)

        today_str = now.strftime("%Y-%m-%d")

        # Collect ALL schedule entries for today
        all_schedules = []
        for entry in schedule_entries:
            if entry.get(DATE) == today_str and OPENING_TIME in entry and CLOSING_TIME in entry:
                schedule_dict = {
                    "type": entry.get(SCHEDULE_TYPE, "UNKNOWN"),
                    "name": entry.get(DESCRIPTION),  # Event name (e.g., "Early Entry", "Jollywood Nights")
                    "opening_time": entry.get(OPENING_TIME),
                    "closing_time": entry.get(CLOSING_TIME),
                }
                all_schedules.append(schedule_dict)

        # Sort schedules by opening time (chronological order)
        all_schedules.sort(key=lambda x: x["opening_time"])

        # Find today's OPERATING schedule (main park hours) for primary attributes
        operating_schedule = None
        for entry in schedule_entries:
            if entry.get(DATE) == today_str and entry.get(SCHEDULE_TYPE) == TYPE_OPERATING:
                operating_schedule = entry
                break

        # If no OPERATING schedule, look for any other type for today
        if not operating_schedule:
            for entry in schedule_entries:
                if entry.get(DATE) == today_str and OPENING_TIME in entry and CLOSING_TIME in entry:
                    operating_schedule = entry
                    break

        if not operating_schedule:
            return {
                "status": "Closed",
                "all_schedules": all_schedules,
            }

        opening_time_str = operating_schedule.get(OPENING_TIME)
        closing_time_str = operating_schedule.get(CLOSING_TIME)
        schedule_type = operating_schedule.get(SCHEDULE_TYPE, TYPE_OPERATING)

        if not opening_time_str or not closing_time_str:
            return {
                "status": "Closed",
                "all_schedules": all_schedules,
            }

        # Parse times (format: "2024-12-16T09:00:00-05:00")
        try:
            opening_time = datetime.fromisoformat(opening_time_str)
            closing_time = datetime.fromisoformat(closing_time_str)
        except (ValueError, TypeError) as err:
            _LOGGER.error("Error parsing times: %s, %s - %s", opening_time_str, closing_time_str, err)
            return {
                "status": "Unknown",
                "all_schedules": all_schedules,
            }

        # Determine status based on current time
        try:
            if now < opening_time:
                status = "Closed"
            elif now > closing_time:
                status = "Closed"
            else:
                # Park is currently open - check for special events
                if schedule_type == TYPE_TICKETED_EVENT:
                    status = "Special Ticketed Event"
                elif schedule_type == TYPE_PRIVATE_EVENT:
                    status = "Private Event"
                elif schedule_type == TYPE_OPERATING:
                    status = "Open"
                else:
                    status = "Open"
        except TypeError as err:
            _LOGGER.error("Error comparing times: %s", err)
            return {
                "status": "Unknown",
                "all_schedules": all_schedules,
            }

        return {
            "status": status,
            "opening_time": opening_time_str,
            "closing_time": closing_time_str,
            "schedule_type": schedule_type,
            "all_schedules": all_schedules,
        }
