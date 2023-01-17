"""Constants for the Presence Simulator integration."""

# from homeassistant.helpers import selector
import voluptuous as vol

from homeassistant.components import light
import homeassistant.helpers.config_validation as cv

DOMAIN = "presence_simulator"
NONE_STR = "None"

CONF_LIGHTS, DEFAULT_LIGHTS = "lights", [light.LightEntity]
CONF_MAX_DAYS, DEFAULT_MAX_DAYS = "max_days", 100
CONF_MIN_DAYS, DEFAULT_MIN_DAYS = "min_days", 1
CONF_INTERVAL, DEFAULT_INTERVAL = "interval", 300


def int_between(min_int, max_int):
    """Return an integer between 'min_int' and 'max_int'."""
    return vol.All(vol.Coerce(int), vol.Range(min=min_int, max=max_int))


VALIDATION_TUPLES = [
    (CONF_LIGHTS, DEFAULT_LIGHTS, cv.entity_ids),
    (CONF_MIN_DAYS, CONF_MAX_DAYS, int_between(1, 100)),
    (CONF_INTERVAL, DEFAULT_INTERVAL, cv.positive_int),
]


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
