"""Entità base per Schedula."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, VERSION
from .manager import ScheduleManager


class SchedulaEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: ScheduleManager, key: str) -> None:
        self.manager = manager
        self._attr_unique_id = f"{manager.schedule_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, manager.schedule_id)},
            name=manager.name,
            manufacturer="Schedula",
            model="Programmatore settimanale",
            sw_version=VERSION,
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.manager.add_listener(self.async_write_ha_state))
