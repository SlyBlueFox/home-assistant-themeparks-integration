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

STEP_USER = "user"
METHOD_GET = "GET"
