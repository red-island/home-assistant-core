"""Switch for the Adaptive Lighting integration."""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import timedelta
import logging

from homeassistant.components.light import ColorMode, LightEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_SUPPORTED_FEATURES
from homeassistant.core import Context, Event, HomeAssistant

from .const import EXTRA_VALIDATION, VALIDATION_TUPLES, replace_none_str

_SUPPORT_OPTS = {
    "brightness": ColorMode.BRIGHTNESS,
    "color_temp": ColorMode.COLOR_TEMP,
    "transition": LightEntityFeature.TRANSITION,
}

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)


# Keep a short domain version for the context instances (which can only be 36 chars)
_DOMAIN_SHORT = "adapt_lgt"


def _int_to_bytes(i: int, signed: bool = False) -> bytes:
    bits = i.bit_length()
    if signed:
        # Make room for the sign bit.
        bits += 1
    return i.to_bytes((bits + 7) // 8, "little", signed=signed)


def _short_hash(string: str, length: int = 4) -> str:
    """Create a hash of 'string' with length 'length'."""
    str_hash_bytes = _int_to_bytes(hash(string), signed=True)
    return base64.b85encode(str_hash_bytes)[:length].decode("utf-8")


def create_context(
    name: str, which: str, index: int, parent: Context | None = None
) -> Context:
    """Create a context that can identify this integration."""
    # Use a hash for the name because otherwise the context might become
    # too long (max len == 36) to fit in the database.
    name_hash = _short_hash(name)
    # Pack index with base85 to maximize the number of contexts we can create
    # before we exceed the 36-character limit and are forced to wrap.
    index_packed = base64.b85encode(_int_to_bytes(index, signed=False)).decode("utf-8")
    context_id = f"{_DOMAIN_SHORT}:{name_hash}:{which}:{index_packed}"[:36]
    parent_id = parent.id if parent else None
    return Context(id=context_id, parent_id=parent_id)


def is_our_context(context: Context | None) -> bool:
    """Check whether this integration created 'context'."""
    if context is None:
        return False
    return context.id.startswith(_DOMAIN_SHORT)


def validate(config_entry: ConfigEntry):
    """Get the options and data from the config_entry and add defaults."""
    defaults = {key: default for key, default, _ in VALIDATION_TUPLES}
    data = deepcopy(defaults)
    data.update(config_entry.options)  # come from options flow
    data.update(config_entry.data)  # all yaml settings come from data
    data = {key: replace_none_str(value) for key, value in data.items()}
    for key, (validate_value, _) in EXTRA_VALIDATION.items():
        value = data.get(key)
        if value is not None:
            data[key] = validate_value(value)  # Fix the types of the inputs
    return data


def match_switch_state_event(event: Event, from_or_to_state: list[str]):
    """Match state event when either 'from_state' or 'to_state' matches."""
    old_state = event.data.get("old_state")
    from_state_match = old_state is not None and old_state.state in from_or_to_state

    new_state = event.data.get("new_state")
    to_state_match = new_state is not None and new_state.state in from_or_to_state

    match = from_state_match or to_state_match
    return match


def _supported_features(hass: HomeAssistant, light: str):
    state = hass.states.get(light)
    if not state:
        _LOGGER.error("Entity does not exists")
        return
    supported_features = state.attributes[ATTR_SUPPORTED_FEATURES]
    supported = {
        key for key, value in _SUPPORT_OPTS.items() if supported_features & value
    }
    return supported
