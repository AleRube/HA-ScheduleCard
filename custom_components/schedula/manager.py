"""Logica della schedulazione settimanale."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time, timedelta
import json
import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    ALARM_SERVICES,
    CONF_ALARM_CODE,
    CONF_APPLY_ON_START,
    CONF_HVAC_MODE,
    CONF_TARGET,
    DAYS,
    DOMAIN,
    HVAC_MODE_NONE,
    HVAC_MODES_ALLOWED,
    LOCK_SERVICES,
    OPTION_DOMAINS,
    PALETTE,
    STORAGE_VERSION,
    VT_NUMBER,
    VT_ONOFF,
    VT_OPTION,
    value_type,
)

_LOGGER = logging.getLogger(__name__)

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def to_min(value: str) -> int:
    """'HH:MM' -> minuti dalla mezzanotte."""
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def _week(slots: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    return {day: [dict(s) for s in slots] for day in DAYS}


def build_default(hass: HomeAssistant, target: str) -> dict[str, Any]:
    """Crea impostazioni e programma di default in base all'entità target."""
    vtype = value_type(target)
    domain = target.split(".", 1)[0]
    state = hass.states.get(target)
    attrs = state.attributes if state else {}

    if vtype == VT_NUMBER and domain in ("climate", "water_heater"):
        if domain == "water_heater":
            values = (55, 60, 45, 40)
        else:
            values = (21, 22, 18, 16)
        presets = [
            {"id": "comfort", "name": "Comfort", "icon": "mdi:home", "color": PALETTE[0], "value": values[0]},
            {"id": "comfort_plus", "name": "Comfort +", "icon": "mdi:fire", "color": PALETTE[1], "value": values[1]},
            {"id": "eco", "name": "Economico", "icon": "mdi:leaf", "color": PALETTE[2], "value": values[2]},
            {"id": "notte", "name": "Notte", "icon": "mdi:weather-night", "color": PALETTE[3], "value": values[3]},
        ]
        week = _week(
            [
                {"start": "00:00", "preset": "notte"},
                {"start": "06:30", "preset": "comfort_plus"},
                {"start": "08:30", "preset": "eco"},
                {"start": "17:00", "preset": "comfort"},
                {"start": "22:30", "preset": "notte"},
            ]
        )
    elif vtype == VT_NUMBER:
        if domain == "cover":
            vmin, vmax = 0, 100
        else:
            vmin = float(attrs.get("min", 0))
            vmax = float(attrs.get("max", 100))
        mid = round((vmin + vmax) / 2, 2)
        presets = [
            {"id": "alto", "name": "Alto" if domain != "cover" else "Aperta", "icon": "mdi:arrow-up-bold", "color": PALETTE[1], "value": vmax},
            {"id": "medio", "name": "Medio" if domain != "cover" else "Metà", "icon": "mdi:minus", "color": PALETTE[0], "value": mid},
            {"id": "basso", "name": "Basso" if domain != "cover" else "Chiusa", "icon": "mdi:arrow-down-bold", "color": PALETTE[3], "value": vmin},
        ]
        week = _week(
            [
                {"start": "00:00", "preset": "basso"},
                {"start": "07:00", "preset": "alto"},
                {"start": "22:00", "preset": "basso"},
            ]
        )
    elif domain == "alarm_control_panel":
        presets = [
            {"id": "inserito", "name": "Inserito", "icon": "mdi:shield-lock", "color": "#E53935", "value": "armed_away"},
            {"id": "notte", "name": "Inserito notte", "icon": "mdi:shield-moon", "color": PALETTE[3], "value": "armed_night"},
            {"id": "disinserito", "name": "Disinserito", "icon": "mdi:shield-off", "color": "#43A047", "value": "disarmed"},
        ]
        week = _week(
            [
                {"start": "00:00", "preset": "notte"},
                {"start": "07:00", "preset": "disinserito"},
                {"start": "23:00", "preset": "notte"},
            ]
        )
    elif domain == "lock":
        presets = [
            {"id": "chiusa", "name": "Chiusa", "icon": "mdi:lock", "color": "#E53935", "value": "locked"},
            {"id": "aperta", "name": "Aperta", "icon": "mdi:lock-open-variant", "color": "#43A047", "value": "unlocked"},
        ]
        week = _week(
            [
                {"start": "00:00", "preset": "chiusa"},
                {"start": "08:00", "preset": "aperta"},
                {"start": "20:00", "preset": "chiusa"},
            ]
        )
    elif vtype == VT_OPTION:
        options = list(attrs.get("options") or [])[:4] or ["opzione"]
        icons = ["mdi:numeric-1-circle", "mdi:numeric-2-circle", "mdi:numeric-3-circle", "mdi:numeric-4-circle"]
        presets = [
            {"id": f"opt{i}", "name": str(opt), "icon": icons[i], "color": PALETTE[i], "value": str(opt)}
            for i, opt in enumerate(options)
        ]
        week = _week([{"start": "00:00", "preset": "opt0"}])
    else:
        light = domain == "light"
        presets = [
            {"id": "acceso", "name": "Acceso", "icon": "mdi:lightbulb-on" if light else "mdi:power", "color": "#FFD166", "value": "on"},
            {"id": "spento", "name": "Spento", "icon": "mdi:lightbulb-off" if light else "mdi:power-off", "color": "#455A64", "value": "off"},
        ]
        week = _week(
            [
                {"start": "00:00", "preset": "spento"},
                {"start": "07:00", "preset": "acceso"},
                {"start": "22:00", "preset": "spento"},
            ]
        )

    return {"enabled": True, "value_type": vtype, "presets": presets, "week": week}


def normalize(presets: Any, week: Any) -> tuple[list[dict], dict[str, list[dict]]]:
    """Valida e normalizza impostazioni e programma. Solleva HomeAssistantError."""
    if not isinstance(presets, list) or not presets:
        raise HomeAssistantError("Serve almeno un'impostazione")

    clean_presets: list[dict] = []
    ids: set[str] = set()
    for raw in presets:
        if not isinstance(raw, dict):
            raise HomeAssistantError("Impostazione non valida")
        pid = str(raw.get("id") or "").strip()
        if not pid or pid in ids:
            raise HomeAssistantError(f"ID impostazione non valido o duplicato: '{pid}'")
        ids.add(pid)
        value = raw.get("value")
        if isinstance(value, bool):
            value = "on" if value else "off"
        if not isinstance(value, (int, float, str)):
            raise HomeAssistantError(f"Valore non valido per '{pid}'")
        clean = {
            "id": pid,
            "name": str(raw.get("name") or pid)[:40],
            "icon": str(raw.get("icon") or "mdi:circle"),
            "color": str(raw.get("color") or PALETTE[0]),
            "value": value,
        }
        hvac_mode = raw.get("hvac_mode")
        if hvac_mode:
            if hvac_mode not in HVAC_MODES_ALLOWED:
                raise HomeAssistantError(f"Modalità non valida: '{hvac_mode}'")
            clean["hvac_mode"] = hvac_mode
        clean_presets.append(clean)

    if not isinstance(week, dict):
        raise HomeAssistantError("Programma settimanale non valido")

    first_preset = clean_presets[0]["id"]
    days: dict[str, list[dict]] = {}
    for day in DAYS:
        raw_slots = week.get(day) or []
        if not isinstance(raw_slots, list):
            raise HomeAssistantError(f"Programma del giorno {day} non valido")
        by_start: dict[int, str] = {}
        for slot in raw_slots:
            start = str(slot.get("start", "")) if isinstance(slot, dict) else ""
            if not _TIME_RE.match(start):
                raise HomeAssistantError(f"Orario non valido: '{start}' ({day})")
            pid = str(slot.get("preset", ""))
            if pid not in ids:
                raise HomeAssistantError(f"Impostazione sconosciuta: '{pid}' ({day})")
            by_start[to_min(start)] = pid
        days[day] = [
            {"start": f"{m // 60:02d}:{m % 60:02d}", "preset": by_start[m]}
            for m in sorted(by_start)
        ]

    # Ogni giorno deve iniziare alle 00:00: se manca, prosegue l'ultima
    # impostazione del giorno precedente.
    result: dict[str, list[dict]] = {}
    for idx, day in enumerate(DAYS):
        slots = days[day]
        if not slots:
            slots = [{"start": "00:00", "preset": first_preset}]
        elif slots[0]["start"] != "00:00":
            prev = days[DAYS[idx - 1]]
            carry = prev[-1]["preset"] if prev else slots[0]["preset"]
            slots.insert(0, {"start": "00:00", "preset": carry})
        merged: list[dict] = []
        for slot in slots:
            if merged and merged[-1]["preset"] == slot["preset"]:
                continue
            merged.append(slot)
        result[day] = merged

    return clean_presets, result


class ScheduleManager:
    """Gestisce una schedulazione (una config entry)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self.data: dict[str, Any] = {}
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[Callable[[], None]] = []
        self._active_key: tuple | None = None
        self.last_applied: dict[str, Any] | None = None
        self.last_error: str | None = None

    # ------------------------------------------------------------------ props
    @property
    def schedule_id(self) -> str:
        return self.entry.entry_id

    @property
    def name(self) -> str:
        return self.entry.title

    @property
    def target(self) -> str:
        return self.entry.options.get(CONF_TARGET, self.entry.data[CONF_TARGET])

    @property
    def enabled(self) -> bool:
        return bool(self.data.get("enabled", True))

    @property
    def presets(self) -> list[dict]:
        return self.data.get("presets", [])

    @property
    def week(self) -> dict[str, list[dict]]:
        return self.data.get("week", {})

    def get_preset(self, preset_id: str | None) -> dict | None:
        return next((p for p in self.presets if p["id"] == preset_id), None)

    # -------------------------------------------------------------- lifecycle
    async def async_load(self) -> None:
        stored = await self.store.async_load()
        vtype = value_type(self.target)
        if not stored or stored.get("value_type") != vtype:
            enabled = stored.get("enabled", True) if stored else True
            stored = build_default(self.hass, self.target)
            stored["enabled"] = enabled
            await self.store.async_save(stored)
        try:
            presets, week = normalize(stored.get("presets"), stored.get("week"))
        except HomeAssistantError as err:
            _LOGGER.warning("Dati salvati non validi (%s): ripristino i default", err)
            stored = build_default(self.hass, self.target)
            presets, week = stored["presets"], stored["week"]
        self.data = {
            "enabled": stored.get("enabled", True),
            "value_type": vtype,
            "presets": presets,
            "week": week,
        }

    async def async_start(self) -> None:
        self._unsubs.append(async_track_time_change(self.hass, self._async_tick, second=0))
        apply_on_start = self.entry.options.get(CONF_APPLY_ON_START, True)

        async def _started(_hass: HomeAssistant) -> None:
            await self.async_evaluate(force=apply_on_start)

        self._unsubs.append(async_at_started(self.hass, _started))

    async def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    async def async_remove(self) -> None:
        await self.store.async_remove()

    # -------------------------------------------------------------- listeners
    @callback
    def add_listener(self, update: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(update)

        @callback
        def _remove() -> None:
            if update in self._listeners:
                self._listeners.remove(update)

        return _remove

    @callback
    def _notify(self) -> None:
        for update in list(self._listeners):
            update()

    # ------------------------------------------------------------ calcolo
    def current_slot(self, now: datetime | None = None) -> dict | None:
        now = now or dt_util.now()
        minutes = now.hour * 60 + now.minute
        slots = self.week.get(DAYS[now.weekday()], [])
        current = None
        for slot in slots:
            if to_min(slot["start"]) <= minutes:
                current = slot
            else:
                break
        return current

    def current_preset(self, now: datetime | None = None) -> dict | None:
        slot = self.current_slot(now)
        return self.get_preset(slot["preset"]) if slot else None

    def next_change(self, now: datetime | None = None) -> tuple[datetime | None, dict | None]:
        now = now or dt_util.now()
        current = self.current_slot(now)
        if current is None:
            return None, None
        cur_min = now.hour * 60 + now.minute
        for offset in range(8):
            day = now.date() + timedelta(days=offset)
            for slot in self.week.get(DAYS[day.weekday()], []):
                start = to_min(slot["start"])
                if offset == 0 and start <= cur_min:
                    continue
                if slot["preset"] != current["preset"]:
                    when = datetime.combine(day, time(start // 60, start % 60), tzinfo=now.tzinfo)
                    return when, self.get_preset(slot["preset"])
        return None, None

    # -------------------------------------------------------------- azioni
    async def _async_tick(self, _now: datetime) -> None:
        await self.async_evaluate()

    async def async_evaluate(self, force: bool = False) -> None:
        """Applica l'impostazione corrente se è cambiata (o se forzato)."""
        if not self.enabled:
            self._active_key = None
            self._notify()
            return
        preset = self.current_preset()
        if preset is None:
            self._notify()
            return
        key = (preset["id"], json.dumps(preset["value"]), preset.get("hvac_mode"), self.target)
        if force or key != self._active_key:
            self._active_key = key
            await self._async_apply(preset)
        self._notify()

    async def _async_apply(self, preset: dict) -> None:
        entity_id = self.target
        domain = entity_id.split(".", 1)[0]
        value = preset["value"]
        try:
            if domain in ("climate", "water_heater"):
                hvac_mode = preset.get("hvac_mode") or self.entry.options.get(CONF_HVAC_MODE, HVAC_MODE_NONE)
                if str(value).lower() == "off" or hvac_mode == "off":
                    await self._call(domain, "turn_off", {"entity_id": entity_id})
                else:
                    data: dict[str, Any] = {"entity_id": entity_id, "temperature": float(value)}
                    if domain == "climate" and hvac_mode and hvac_mode != HVAC_MODE_NONE:
                        data["hvac_mode"] = hvac_mode
                    await self._call(domain, "set_temperature", data)
            elif domain == "alarm_control_panel":
                service = ALARM_SERVICES.get(str(value))
                if service is None:
                    raise HomeAssistantError(f"Stato allarme non valido: {value}")
                data = {"entity_id": entity_id}
                code = self.entry.options.get(CONF_ALARM_CODE)
                if code:
                    data["code"] = code
                await self._call(domain, service, data)
            elif domain == "lock":
                service = LOCK_SERVICES.get(str(value))
                if service is None:
                    raise HomeAssistantError(f"Stato serratura non valido: {value}")
                await self._call(domain, service, {"entity_id": entity_id})
            elif domain in ("input_number", "number"):
                await self._call(domain, "set_value", {"entity_id": entity_id, "value": float(value)})
            elif domain == "cover":
                await self._call(domain, "set_cover_position", {"entity_id": entity_id, "position": int(float(value))})
            elif domain in OPTION_DOMAINS:
                await self._call(domain, "select_option", {"entity_id": entity_id, "option": str(value)})
            else:
                service = "turn_on" if str(value).lower() in ("on", "true", "1") else "turn_off"
                await self._call("homeassistant", service, {"entity_id": entity_id})
            self.last_error = None
            self.last_applied = {
                "preset": preset["id"],
                "value": value,
                "at": dt_util.now().isoformat(timespec="seconds"),
            }
            _LOGGER.debug("%s: applicato '%s' (%s) a %s", self.name, preset["name"], value, entity_id)
        except Exception as err:  # noqa: BLE001
            self.last_error = str(err)
            _LOGGER.error("%s: impossibile applicare '%s' a %s: %s", self.name, preset["name"], entity_id, err)

    async def _call(self, domain: str, service: str, data: dict) -> None:
        await self.hass.services.async_call(domain, service, data, blocking=True)

    async def async_save_schedule(self, presets: Any, week: Any) -> None:
        clean_presets, clean_week = normalize(presets, week)
        self.data["presets"] = clean_presets
        self.data["week"] = clean_week
        await self.store.async_save(self.data)
        await self.async_evaluate()

    async def async_set_enabled(self, enabled: bool) -> None:
        self.data["enabled"] = enabled
        await self.store.async_save(self.data)
        await self.async_evaluate(force=enabled)

    async def async_apply_now(self) -> None:
        await self.async_evaluate(force=True)

    def state_attributes(self) -> dict[str, Any]:
        preset = self.current_preset()
        when, nxt = self.next_change()
        return {
            "schedule_id": self.schedule_id,
            "enabled": self.enabled,
            "target_entity": self.target,
            "value_type": self.data.get("value_type"),
            "current_preset": preset["id"] if preset else None,
            "current_value": preset["value"] if preset else None,
            "next_change": when.isoformat() if when else None,
            "next_preset": nxt["id"] if nxt else None,
            "last_error": self.last_error,
            "presets": self.presets,
            "week": self.week,
        }
