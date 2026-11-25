"""Sensore: impostazione corrente della schedulazione (usato dalla card)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .profiles import CATEGORY_ICONS
from .entity import SchedulaEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([SchedulaSensor(hass.data[DOMAIN][entry.entry_id])])


class SchedulaSensor(SchedulaEntity, SensorEntity):
    _attr_name = None
    _unrecorded_attributes = frozenset(
        {
            "schedule_id",
            "target_entity",
            "value_type",
            "next_change",
            "next_preset",
            "last_error",
            "presets",
            "week",
        }
    )

    def __init__(self, manager) -> None:
        super().__init__(manager, "schedule")
        self._attr_icon = CATEGORY_ICONS.get(manager.entry.data.get("category", "altro"), "mdi:calendar-clock")

    @property
    def native_value(self) -> str | None:
        preset = self.manager.current_preset()
        return preset["name"] if preset else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.manager.state_attributes()
