"""Constants for the Presence Simulator integration."""

from typing import Final

# from homeassistant.helpers import selector
import voluptuous as vol

# from homeassistant.components import automation, light
import homeassistant.helpers.config_validation as cv

DOMAIN: Final = "presence_simulator"
ICON = "mdi:theme-light-dark"
NONE_STR = "None"

CONF_LIGHTS, DEFAULT_LIGHTS = "lights", [str]
CONF_AUTOMATIONS, DEFAULT_AUTOMATIONS = "automations", [str]
CONF_INTERVAL, DEFAULT_INTERVAL = "interval", 10
CONF_PLAYBACK_AUTOMATIONS, DEFAULT_PLAYBACK_AUTOMATIONS = "playback_automation", True
CONF_PLAYBACK_DAYS, DEFAULT_PLAYBACK_DAYS = "playback_days", 7
CONF_AUTOMATIONS_FILTER, DEFAULT_AUTOMATIONS_FILTER = (
    "automation_filter",
    "%zigbee2mqtt/Feller%",
)
CONF_LIGHTS_FILTER, DEFAULT_LIGHTS_FILTER = "lights_filter", ""  # "automation_filter"


def int_between(min_int, max_int):
    """Return an integer between 'min_int' and 'max_int'."""
    return vol.All(vol.Coerce(int), vol.Range(min=min_int, max=max_int))


VALIDATION_TUPLES = [
    #    (CONF_PLAYBACK_AUTOMATIONS, CONF_PLAYBACK_AUTOMATIONS, cv.boolean),
    (CONF_AUTOMATIONS, DEFAULT_AUTOMATIONS, cv.entity_ids),
    (CONF_AUTOMATIONS_FILTER, DEFAULT_AUTOMATIONS_FILTER, cv.string),
    (CONF_LIGHTS, DEFAULT_LIGHTS, cv.entity_ids),
    (CONF_LIGHTS_FILTER, DEFAULT_LIGHTS_FILTER, cv.string),
    (CONF_PLAYBACK_DAYS, DEFAULT_PLAYBACK_DAYS, int_between(1, 14)),
    (CONF_INTERVAL, DEFAULT_INTERVAL, cv.positive_int),
]

ATTR_TURN_ON_OFF_LISTENER = "turn_on_off_listener"
SERVICE_APPLY = "apply"
UNDO_UPDATE_LISTENER = "update_listener"


def replace_none_str(value, replace_with=None):
    """Replace "None" -> replace_with."""
    return value if value != NONE_STR else replace_with


def timedelta_as_int(value):
    """Convert a `datetime.timedelta` object to an integer. This integer can be serialized to json but a timedelta cannot."""
    return value.total_seconds()


# these validators cannot be serialized but can be serialized when coerced by coerce.
EXTRA_VALIDATION = {
    CONF_INTERVAL: (cv.time_period, timedelta_as_int),
    # CONF_SUNRISE_OFFSET: (cv.time_period, timedelta_as_int),
    # CONF_SUNRISE_TIME: (cv.time, str),
    # CONF_MAX_SUNRISE_TIME: (cv.time, str),
    # CONF_SUNSET_OFFSET: (cv.time_period, timedelta_as_int),
    # CONF_SUNSET_TIME: (cv.time, str),
    # CONF_MIN_SUNSET_TIME: (cv.time, str),
}
