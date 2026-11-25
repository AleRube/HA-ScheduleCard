"""Test di Schedula."""

from datetime import datetime
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.schedula.const import DOMAIN
from custom_components.schedula.manager import normalize


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def no_frontend(hass: HomeAssistant):
    hass.config.components.add("http")
    hass.config.components.add("frontend")
    with patch("custom_components.schedula._register_card"):
        yield


async def _create(hass: HomeAssistant, target="climate.ufficio", category="altro", name="Ufficio", **details):
    hass.states.async_set(target, "heat", {"friendly_name": "Cucina", "min_temp": 7, "max_temp": 30, "temperature": 20})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"category": category})
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "details"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": name, "target_entity": target, **details}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return result["result"]


SW = "switch.ufficio_active"  # in italiano: switch.ufficio_attiva


async def test_setup_and_apply(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    tz = dt_util.get_default_time_zone()
    freezer.move_to(datetime(2026, 11, 23, 7, 0, 30, tzinfo=tz))  # lunedì
    calls = async_mock_service(hass, "climate", "set_temperature")

    entry = await _create(hass)
    await hass.async_start()
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.ufficio")
    assert sensor is not None, hass.states.async_entity_ids()
    assert hass.states.get(SW).state == "on"
    assert sensor.attributes["schedule_id"] == entry.entry_id
    assert sensor.state == "Comfort +"  # default: 06:30 comfort_plus
    assert calls and calls[-1].data["temperature"] == 22.0

    # salva un programma nuovo: lunedì 00:00 notte, 07:05 eco
    presets = sensor.attributes["presets"]
    week = {d: [{"start": "00:00", "preset": "notte"}] for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    week["mon"] = [{"start": "07:05", "preset": "eco"}, {"start": "00:00", "preset": "notte"}]
    await hass.services.async_call(DOMAIN, "save", {"schedule_id": entry.entry_id, "presets": presets, "week": week}, blocking=True)
    await hass.async_block_till_done()
    assert calls[-1].data["temperature"] == 16.0  # ora è notte
    n = len(calls)

    # tick ogni minuto senza cambio -> nessuna nuova chiamata
    freezer.move_to(datetime(2026, 11, 23, 7, 2, 0, tzinfo=tz))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == n

    # cambio fascia alle 07:05 -> eco
    freezer.move_to(datetime(2026, 11, 23, 7, 5, 0, tzinfo=tz))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert calls[-1].data["temperature"] == 18.0
    assert hass.states.get("sensor.ufficio").state == "Economico"

    # disattiva: nessuna applicazione
    await hass.services.async_call("switch", "turn_off", {"entity_id": SW}, blocking=True)
    n = len(calls)
    week["mon"].append({"start": "07:06", "preset": "comfort"})
    await hass.services.async_call(DOMAIN, "save", {"schedule_id": entry.entry_id, "presets": presets, "week": week}, blocking=True)
    freezer.move_to(datetime(2026, 11, 23, 7, 6, 0, tzinfo=tz))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == n

    # riattiva: applica subito comfort
    await hass.services.async_call(DOMAIN, "set_enabled", {"schedule_id": entry.entry_id, "enabled": True}, blocking=True)
    assert calls[-1].data["temperature"] == 21.0

    # next_change calcolato
    attrs = hass.states.get("sensor.ufficio").attributes
    assert attrs["next_preset"] == "notte"

    # persistenza: reload mantiene il programma
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    attrs = hass.states.get("sensor.ufficio").attributes
    assert attrs["week"]["mon"][-1] == {"start": "07:06", "preset": "comfort"}


async def test_switch_target(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    tz = dt_util.get_default_time_zone()
    freezer.move_to(datetime(2026, 11, 24, 12, 0, 0, tzinfo=tz))
    on_calls = async_mock_service(hass, "homeassistant", "turn_on")
    await _create(hass, target="switch.caldaia")
    await hass.async_start()
    await hass.async_block_till_done()
    assert on_calls and on_calls[-1].data["entity_id"] == "switch.caldaia"


async def test_bad_save(hass: HomeAssistant):
    entry = await _create(hass)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN, "save",
            {"schedule_id": entry.entry_id, "presets": [{"id": "a", "value": 20}], "week": {"mon": [{"start": "25:00", "preset": "a"}]}},
            blocking=True,
        )


def test_normalize_carry_over():
    presets = [{"id": "a", "value": 1}, {"id": "b", "value": 2}]
    week = {"mon": [{"start": "08:00", "preset": "a"}, {"start": "09:00", "preset": "a"}], "sun": [{"start": "22:00", "preset": "b"}]}
    _, out = normalize(presets, week)
    # lunedì parte con l'ultima di domenica (b), duplicati uniti
    assert out["mon"] == [{"start": "00:00", "preset": "b"}, {"start": "08:00", "preset": "a"}]
    assert out["tue"] == [{"start": "00:00", "preset": "a"}]


async def test_card_served(hass, hass_client):
    """La card JS viene servita e registrata nel frontend."""
    import importlib
    import custom_components.schedula as sch
    real = importlib.reload(sch)._register_card  # versione non patchata
    hass.config.components.remove("http")
    assert await async_setup_component(hass, "http", {})
    with patch("homeassistant.components.frontend.add_extra_js_url") as add:
        await real(hass)
    client = await hass_client()
    resp = await client.get("/schedula_static/schedula-card.js")
    assert resp.status == 200
    assert "schedula-card" in await resp.text()
    assert add.call_args[0][1].startswith("/schedula_static/schedula-card.js?v=")


async def test_hvac_mode_per_preset(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    """Modalità caldo/freddo/spento per singola impostazione."""
    tz = dt_util.get_default_time_zone()
    freezer.move_to(datetime(2026, 11, 24, 23, 30, 0, tzinfo=tz))  # martedì
    await hass.async_start()
    await hass.async_block_till_done()

    # termostato: impostazione con modalità freddo e una spenta
    cool = async_mock_service(hass, "climate", "set_temperature")
    off = async_mock_service(hass, "climate", "turn_off")
    entry = await _create(hass, target="climate.sala")
    sensor = hass.states.get("sensor.ufficio")
    presets = [
        {"id": "fresco", "name": "Fresco", "icon": "mdi:snowflake", "color": "#5AB8FF", "value": 24, "hvac_mode": "cool"},
        {"id": "spento", "name": "Spento", "icon": "mdi:power-off", "color": "#455A64", "value": 20, "hvac_mode": "off"},
    ]
    week = {d: [{"start": "00:00", "preset": "fresco"}] for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    await hass.services.async_call(DOMAIN, "save", {"schedule_id": entry.entry_id, "presets": presets, "week": week}, blocking=True)
    assert cool[-1].data == {"entity_id": "climate.sala", "temperature": 24.0, "hvac_mode": "cool"}
    week["tue"] = [{"start": "00:00", "preset": "spento"}]
    await hass.services.async_call(DOMAIN, "save", {"schedule_id": entry.entry_id, "presets": presets, "week": week}, blocking=True)
    assert off and off[-1].data["entity_id"] == "climate.sala"
    assert sensor is not None


async def test_profilo_hvac_radiatori(hass: HomeAssistant):
    """HVAC riscaldamento a radiatori in abitazione: impostazioni e programma tipici."""
    await _create(hass, target="climate.soggiorno", category="hvac", name="Riscaldamento",
                  season="riscaldamento", terminal="radiatori", usage="abitazione")
    attrs = hass.states.get("sensor.riscaldamento").attributes
    assert attrs["icon"] == "mdi:thermostat"
    presets = {p["id"]: p for p in attrs["presets"]}
    assert presets["comfort"]["value"] == 20.0 and presets["comfort"]["hvac_mode"] == "heat"
    assert presets["notte"]["value"] == 16.0
    assert attrs["week"]["mon"] == [
        {"start": "00:00", "preset": "notte"},
        {"start": "05:30", "preset": "comfort_plus"},
        {"start": "06:30", "preset": "comfort"},
        {"start": "08:30", "preset": "eco"},
        {"start": "16:30", "preset": "comfort_plus"},
        {"start": "17:30", "preset": "comfort"},
        {"start": "22:30", "preset": "notte"},
    ]


async def test_profilo_luci(hass: HomeAssistant):
    """Luci esterne: icone lampadina, giallo/grigio."""
    hass.states.async_set("light.giardino", "off", {"friendly_name": "Giardino"})
    await _create(hass, target="light.giardino", category="luci", name="Luci esterne", subtype="esterne", usage="abitazione")
    attrs = hass.states.get("sensor.luci_esterne").attributes
    on, off = attrs["presets"]
    assert (on["icon"], on["color"], on["value"]) == ("mdi:lightbulb-on", "#FFD166", "on")
    assert (off["icon"], off["color"], off["value"]) == ("mdi:lightbulb-off", "#455A64", "off")
    assert [s["start"] for s in attrs["week"]["sat"]] == ["00:00", "05:30", "07:30", "17:30"]
