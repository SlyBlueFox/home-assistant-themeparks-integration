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

STEP_USER = "user"
METHOD_GET = "GET"
