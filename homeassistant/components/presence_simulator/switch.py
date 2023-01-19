"""Switch for the Presence Simulator integration."""
from __future__ import annotations

import asyncio
import base64
from copy import deepcopy
from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
    LightEntityFeature,
)
from homeassistant.components.switch import SwitchEntity  # , DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (  # EVENT_STATE_CHANGED,
    ATTR_AREA_ID,
    ATTR_DOMAIN,
    ATTR_ENTITY_ID,
    ATTR_SERVICE,
    ATTR_SERVICE_DATA,
    ATTR_SUPPORTED_FEATURES,
    CONF_NAME,
    EVENT_CALL_SERVICE,
    EVENT_HOMEASSISTANT_STARTED,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import Context, Event, HomeAssistant, ServiceCall
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.template import area_entities
from homeassistant.util import slugify

from .const import (
    ATTR_TURN_ON_OFF_LISTENER,
    DOMAIN,
    EXTRA_VALIDATION,
    ICON,
    SERVICE_APPLY,
    VALIDATION_TUPLES,
    replace_none_str,
)

# from collections import defaultdict


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


async def handle_apply(switch: PresenceSimulator, service_call: ServiceCall):
    """Handle the entity service apply."""
    # hass = switch.hass
    data = service_call.data
    # all_lights = data[CONF_LIGHTS]
    # if not all_lights:
    #     all_lights = switch._lights
    # all_lights = _expand_light_groups(hass, all_lights)
    # switch.turn_on_off_listener.lights.update(all_lights)
    _LOGGER.debug("Called 'presence_simulation.apply' service with '%s'", data)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Presence Simulation switch."""
    data = hass.data[DOMAIN]
    assert config_entry.entry_id in data

    if ATTR_TURN_ON_OFF_LISTENER not in data:
        data[ATTR_TURN_ON_OFF_LISTENER] = TurnOnOffListener(hass)
    turn_on_off_listener = data[ATTR_TURN_ON_OFF_LISTENER]

    # sleep_mode_switch = SimpleSwitch("Sleep Mode", False, hass, entry)

    switch = PresenceSimulator(
        hass, config_entry, turn_on_off_listener
    )  # , sleep_mode_switch)

    # data[entry.entry_id][SLEEP_MODE_SWITCH] = sleep_mode_switch
    # data[entry.entry_id][ADAPT_COLOR_SWITCH] = adapt_color_switch
    # data[entry.entry_id][ADAPT_BRIGHTNESS_SWITCH] = adapt_brightness_switch
    # data[entry.entry_id][SWITCH_DOMAIN] = switch

    async_add_entities(
        [switch],  # [switch, sleep_mode_switch],
        update_before_add=True,
    )

    # Register `apply` service
    platform = entity_platform.current_platform.get()
    if platform is not None:
        platform.async_register_entity_service(
            SERVICE_APPLY,
            {
                vol.Optional("ATTR_ADAPT_BRIGHTNESS", default=True): cv.boolean,
            },
            handle_apply,
        )

    # platform.async_register_entity_service(
    #     SERVICE_SET_MANUAL_CONTROL,
    #     {
    #         vol.Optional(CONF_LIGHTS, default=[]): cv.entity_ids,
    #         vol.Optional(CONF_MANUAL_CONTROL, default=True): cv.boolean,
    #     },
    #     handle_set_manual_control,
    # )


def validate(entry: ConfigEntry):
    """Get the options and data from the entry and add defaults."""
    defaults = {key: default for key, default, _ in VALIDATION_TUPLES}
    data = deepcopy(defaults)
    data.update(entry.options)  # come from options flow
    data.update(entry.data)  # all yaml settings come from data
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


class PresenceSimulator(SwitchEntity, RestoreEntity):
    """Representation of a Presence Simulator switch."""

    def __init__(
        self,
        hass,
        entry: ConfigEntry,
        turn_on_off_listener: TurnOnOffListener,
        # sleep_mode_switch: SimpleSwitch,
    ):
        """Initialize the Presence Simulator switch."""
        self.hass = hass
        self.turn_on_off_listener = turn_on_off_listener
        # self.sleep_mode_switch = sleep_mode_switch

        data = validate(entry)
        self._name = data[CONF_NAME]

        # Set other attributes
        self._icon = ICON
        self._state: bool | None = None

        # Tracks 'off' → 'on' state changes
        self._on_to_off_event: dict[str, Event] = {}
        # Tracks 'on' → 'off' state changes
        self._off_to_on_event: dict[str, Event] = {}
        # Locks that prevent light adjusting when waiting for a light to 'turn_off'
        self._locks: dict[str, asyncio.Lock] = {}
        # To count the number of `Context` instances
        self._context_cnt: int = 0

        # Set in self._update_attrs_and_maybe_adapt_lights
        self._settings: dict[str, Any] = {}

        # Set and unset tracker in async_turn_on and async_turn_off
        self.remove_listeners = [str]
        _LOGGER.debug(
            "%s: entry.data: '%s', entry.options: '%s', converted to '%s'",
            self._name,
            entry.data,
            entry.options,
            data,
        )

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return f"Presence Simulator: {self._name}"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of entity."""
        return self._name

    @property
    def is_on(self) -> bool | None:
        """Return true if Presence Simulator is active."""
        return bool(self._state)

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        if self.hass.is_running:
            await self._setup_listeners()
        else:
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, self._setup_listeners
            )
        last_state = await self.async_get_last_state()

        if last_state is None:
            await self.async_turn_on()  # newly added to HA
        else:
            if last_state.state == STATE_ON:
                await self.async_turn_on()
            else:
                self._state = False
                assert not self.remove_listeners

    async def async_will_remove_from_hass(self) -> None:
        """Remove the listeners upon removing the component."""
        self._remove_listeners()

    async def _setup_listeners(self, _=None) -> None:
        _LOGGER.debug("%s: Called '_setup_listeners'", self._name)
        if not self.is_on or not self.hass.is_running:
            _LOGGER.debug("%s: Cancelled '_setup_listeners'", self._name)
            return

        assert not self.remove_listeners

        # remove_interval = async_track_time_interval(
        #     self.hass, self._async_update_at_interval, self._interval
        # )

        # self.remove_listeners.extend([remove_interval, remove_sleep])

    def _remove_listeners(self) -> None:
        while self.remove_listeners:
            remove_listener = self.remove_listeners.pop()
            remove_listener()

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the attributes of the switch."""
        if not self.is_on:
            return {key: None for key in self._settings}
        manual_control = [str]
        # manual_control = [
        #     light
        #     for light in self._lights
        #     if self.turn_on_off_listener.manual_control.get(light)
        # ]
        return dict(self._settings, manual_control=manual_control)

    def create_context(
        self, which: str = "default", parent: Context | None = None
    ) -> Context:
        """Create a context that identifies this Adaptive Lighting instance."""
        # Right now the highest number of each context_id it can create is
        # 'adapt_lgt:XXXX:turn_on:*************'
        # 'adapt_lgt:XXXX:interval:************'
        # 'adapt_lgt:XXXX:adapt_lights:********'
        # 'adapt_lgt:XXXX:sleep:***************'
        # 'adapt_lgt:XXXX:light_event:*********'
        # 'adapt_lgt:XXXX:service:*************'
        # The smallest space we have is for adapt_lights, which has
        # 8 characters. In base85 encoding, that's enough space to hold values
        # up to 2**48 - 1, which should give us plenty of calls before we wrap.
        context = create_context(self._name, which, self._context_cnt, parent=parent)
        self._context_cnt += 1
        return context

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on Presence Simulator."""
        _LOGGER.debug(
            "%s: Called 'async_turn_on', current state is '%s'", self._name, self._state
        )
        if self.is_on:
            return
        self._state = True
        # self.turn_on_off_listener.reset(*self._lights)
        await self._setup_listeners()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off Presence Simulator."""
        if not self.is_on:
            return
        self._state = False
        self._remove_listeners()
        # self.turn_on_off_listener.reset(*self._lights)

    async def _async_update_at_interval(self, now=None) -> None:
        return
        # await self._update_attrs_and_maybe_adapt_lights(
        #     transition=self._transition,
        #     force=False,
        #     context=self.create_context("interval"),
        # )

    async def _sleep_mode_switch_state_event(self, event: Event) -> None:
        if not match_switch_state_event(event, [STATE_ON, STATE_OFF]):
            _LOGGER.debug("%s: Ignoring sleep event %s", self._name, event)
            return
        _LOGGER.debug(
            "%s: _sleep_mode_switch_state_event, event: '%s'", self._name, event
        )
        # Reset the manually controlled status when the "sleep mode" changes
        # self.turn_on_off_listener.reset(*self._lights)
        # await self._update_attrs_and_maybe_adapt_lights(
        #     transition=self._sleep_transition,
        #     force=True,
        #     context=self.create_context("sleep", parent=event.context),
        # )


class SimpleSwitch(SwitchEntity, RestoreEntity):
    """Representation of a switch."""

    def __init__(self, which: str, initial_state: bool, hass: HomeAssistant, entry):
        """Initialize the switch."""
        self.hass = hass
        data = validate(entry)
        self._icon = ICON
        self._state: bool | None = None
        self._which = which
        name = data[CONF_NAME]
        self._unique_id = f"{name}_{slugify(self._which)}"
        self._name = f"Presence Simulator {which}: {name}"
        self._initial_state = initial_state

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of entity."""
        return self._unique_id

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self._state

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        last_state = await self.async_get_last_state()
        _LOGGER.debug("%s: last state is %s", self._name, last_state)
        if (last_state is None and self._initial_state) or (
            last_state is not None and last_state.state == STATE_ON
        ):
            await self.async_turn_on()
        else:
            await self.async_turn_off()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on Presence Simulator sleep mode."""
        _LOGGER.debug("%s: Turning on", self._name)
        self._state = True

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off Presence Simulator sleep mode."""
        _LOGGER.debug("%s: Turning off", self._name)
        self._state = False


def get_entities_from_event(hass: HomeAssistant, domain, service_data):
    """Return ist of entity_ids related to event."""

    if ATTR_ENTITY_ID in service_data:
        entity_ids = cv.ensure_list_csv(service_data[ATTR_ENTITY_ID])
    elif ATTR_AREA_ID in service_data:
        area_ids = cv.ensure_list_csv(service_data[ATTR_AREA_ID])
        entity_ids = []
        for area_id in area_ids:
            area_entity_ids = area_entities(hass, area_id)
            for entity_id in area_entity_ids:
                if entity_id.startswith(domain):
                    entity_ids.append(entity_id)
            _LOGGER.debug("Found entity_ids '%s' for area_id '%s'", entity_ids, area_id)
    else:
        _LOGGER.debug(
            "No entity_ids or area_ids found in service_data: %s", service_data
        )
        return []


class TurnOnOffListener:
    """Track 'light.turn_off' and 'light.turn_on' service calls."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the TurnOnOffListener that is shared among all switches."""
        self.hass = hass
        # self.lights = set()

        # Tracks 'light.turn_off' service calls
        self.turn_off_event: dict[str, Event] = {}
        # Tracks 'light.turn_on' service calls
        self.turn_on_event: dict[str, Event] = {}

        self.remove_listener = self.hass.bus.async_listen(
            EVENT_CALL_SERVICE, self.turn_on_off_event_listener
        )

    async def turn_on_off_event_listener(self, event: Event) -> None:
        """Track 'light.turn_off' and 'light.turn_on' service calls."""
        domain = event.data.get(ATTR_DOMAIN)
        if domain != LIGHT_DOMAIN:
            return

        service = event.data[ATTR_SERVICE]
        service_data = event.data[ATTR_SERVICE_DATA]
        entity_ids = get_entities_from_event(self.hass, LIGHT_DOMAIN, service_data)

        if service == SERVICE_TURN_OFF:
            _LOGGER.debug(
                "Detected an 'light.turn_off event with context.id='%s'",
                event.context.id,
            )

        elif service == SERVICE_TURN_ON:
            _LOGGER.debug(
                "Detected an 'light.turn_on('%s')' event with context.id='%s'",
                entity_ids,
                event.context.id,
            )


# class SwitchActionListener:
#     """Track 'switch.action' events."""

#     def __init__(self, hass: HomeAssistant) -> None:
#         """Initialize the SwitchActionListener that is shared among all switches."""
#         self.hass = hass
#         self.lights = set()

#         # Tracks 'light.turn_off' service calls
#         self.turn_off_event: dict[str, Event] = {}
#         # Tracks 'light.turn_on' service calls
#         self.turn_on_event: dict[str, Event] = {}

#         self.remove_listener = self.hass.bus.async_listen(
#             EVENT_CALL_SERVICE, self.switch_pressed_event_listener
#         )

#     async def switch_pressed_event_listener(self, event: Event) -> None:
#         """Track 'switch.action' service calls."""
#         domain = event.data.get(ATTR_DOMAIN)
#         if domain != SWITCH_DOMAIN:
#             return

#         service = event.data[ATTR_SERVICE]
#         service_data = event.data[ATTR_SERVICE_DATA]
#         if ATTR_ENTITY_ID in service_data:
#             entity_ids = cv.ensure_list_csv(service_data[ATTR_ENTITY_ID])
#         elif ATTR_AREA_ID in service_data:
#             area_ids = cv.ensure_list_csv(service_data[ATTR_AREA_ID])
#             entity_ids = []
#             for area_id in area_ids:
#                 area_entity_ids = area_entities(self.hass, area_id)
#                 for entity_id in area_entity_ids:
#                     if entity_id.startswith(SWITCH_DOMAIN):
#                         entity_ids.append(entity_id)
#                 _LOGGER.debug(
#                     "Found entity_ids '%s' for area_id '%s'", entity_ids, area_id
#                 )
#         else:
#             _LOGGER.debug(
#                 "No entity_ids or area_ids found in service_data: %s", service_data
#             )
#             return

#         if service == SERVICE_TURN_OFF:
#             _LOGGER.debug(
#                 "Detected an 'light.turn_off event with context.id='%s'",
#                 event.context.id,
#             )

#         elif service == SERVICE_TURN_ON:
#             _LOGGER.debug(
#                 "Detected an 'light.turn_on('%s')' event with context.id='%s'",
#                 entity_ids,
#                 event.context.id,
#             )
