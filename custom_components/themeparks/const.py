"""Constants for the Theme Park Wait Times integration."""

DOMAIN = "themeparks"

PARKSLUG = "parkslug"
PARKNAME = "parkname"

BASE_URL = "https://api.themeparks.wiki/v1"
DESTINATIONS_URL = "%s/destinations" % BASE_URL
ENTITY_BASE_URL = "%s/entity" % BASE_URL

LIVE_DATA = "liveData"
ENTITY_TYPE = "entityType"

TYPE_SHOW = "SHOW"
TYPE_ATTRACTION = "ATTRACTION"

NAME = "name"
TIME = "time"
ID = "id"
PARKID = "parkId"
ATTR_PARK_NAME = "park_name"
SLUG = "slug"
DESTINATIONS = "destinations"
QUEUE = "queue"
STANDBY = "STANDBY"
WAIT_TIME = "waitTime"
LIVE = "live"

# Schedule constants
SCHEDULE = "schedule"
SCHEDULE_DATA = "schedule"
OPENING_TIME = "openingTime"
CLOSING_TIME = "closingTime"
SCHEDULE_TYPE = "type"
DATE = "date"
DESCRIPTION = "description"

# Schedule types
TYPE_OPERATING = "OPERATING"
TYPE_TICKETED_EVENT = "TICKETED_EVENT"
TYPE_PRIVATE_EVENT = "PRIVATE_EVENT"
TYPE_EXTRA_HOURS = "EXTRA_HOURS"
TYPE_INFO = "INFO"

# Park status attributes
ATTR_PARK_STATUS = "park_status"
ATTR_OPENING_TIME = "opening_time"
ATTR_CLOSING_TIME = "closing_time"
ATTR_SCHEDULE_TYPE = "schedule_type"
ATTR_ALL_SCHEDULES = "all_schedules"

ATTR_7D_AVERAGE = "7d_average_wait"
ATTR_7D_MINIMUM = "7d_minimum_wait"
ATTR_7D_MAXIMUM = "7d_maximum_wait"

STORAGE_KEY = "themeparks_wait_history"
STORAGE_VERSION = 1
HISTORY_DAYS = 7

STEP_USER = "user"
METHOD_GET = "GET"
