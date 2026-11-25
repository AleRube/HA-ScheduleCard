"""Switch: attiva/disattiva la schedulazione."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SchedulaEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([SchedulaSwitch(hass.data[DOMAIN][entry.entry_id])])


class SchedulaSwitch(SchedulaEntity, SwitchEntity):
    _attr_translation_key = "enabled"
    _attr_icon = "mdi:calendar-check"

    def __init__(self, manager) -> None:
        super().__init__(manager, "enabled")

    @property
    def is_on(self) -> bool:
        return self.manager.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.manager.async_set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.manager.async_set_enabled(False)
