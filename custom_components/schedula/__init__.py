"""Schedula: programmatore settimanale per Home Assistant."""

from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_ENABLED,
    ATTR_PRESETS,
    ATTR_SCHEDULE_ID,
    ATTR_WEEK,
    CARD_URL,
    DOMAIN,
    PLATFORMS,
    SERVICE_APPLY_NOW,
    SERVICE_SAVE,
    SERVICE_SET_ENABLED,
    SERVICE_SET_TARGET,
    VERSION,
)
from .manager import ScheduleManager

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SAVE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_SCHEDULE_ID): cv.string,
        vol.Required(ATTR_PRESETS): list,
        vol.Required(ATTR_WEEK): dict,
    }
)
SET_ENABLED_SCHEMA = vol.Schema(
    {vol.Required(ATTR_SCHEDULE_ID): cv.string, vol.Required(ATTR_ENABLED): cv.boolean}
)
APPLY_SCHEMA = vol.Schema({vol.Required(ATTR_SCHEDULE_ID): cv.string})
SET_TARGET_SCHEMA = vol.Schema(
    {vol.Required(ATTR_SCHEDULE_ID): cv.string, vol.Required("entity_id"): cv.entity_id}
)


def _manager(hass: HomeAssistant, schedule_id: str) -> ScheduleManager:
    manager = hass.data.get(DOMAIN, {}).get(schedule_id)
    if manager is None:
        raise HomeAssistantError(f"Schedulazione '{schedule_id}' non trovata")
    return manager


async def _register_card(hass: HomeAssistant) -> None:
    """Serve la card Lovelace e la carica automaticamente nel frontend."""
    path = Path(__file__).parent / "www" / "schedula-card.js"
    try:
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(path), False)])
    except ImportError:  # HA < 2024.7
        hass.http.register_static_path(CARD_URL, str(path), False)

    from homeassistant.components.frontend import add_extra_js_url

    add_extra_js_url(hass, f"{CARD_URL}?v={VERSION}")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.data.setdefault(DOMAIN, {})

    if hass.http is not None:
        await _register_card(hass)

    async def handle_save(call: ServiceCall) -> None:
        manager = _manager(hass, call.data[ATTR_SCHEDULE_ID])
        await manager.async_save_schedule(call.data[ATTR_PRESETS], call.data[ATTR_WEEK])

    async def handle_set_enabled(call: ServiceCall) -> None:
        manager = _manager(hass, call.data[ATTR_SCHEDULE_ID])
        await manager.async_set_enabled(call.data[ATTR_ENABLED])

    async def handle_apply(call: ServiceCall) -> None:
        manager = _manager(hass, call.data[ATTR_SCHEDULE_ID])
        await manager.async_apply_now()

    async def handle_set_target(call: ServiceCall) -> None:
        manager = _manager(hass, call.data[ATTR_SCHEDULE_ID])
        await manager.async_set_target(call.data["entity_id"])

    hass.services.async_register(DOMAIN, SERVICE_SET_TARGET, handle_set_target, schema=SET_TARGET_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SAVE, handle_save, schema=SAVE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SET_ENABLED, handle_set_enabled, schema=SET_ENABLED_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_APPLY_NOW, handle_apply, schema=APPLY_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    manager = ScheduleManager(hass, entry)
    await manager.async_load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await manager.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    manager: ScheduleManager = hass.data[DOMAIN][entry.entry_id]
    await manager.async_stop()
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    from homeassistant.helpers.storage import Store

    from .const import STORAGE_VERSION

    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()
