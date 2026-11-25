"""Profili per tipo di impianto: impostazioni (icone, colori, valori) e programmi realistici."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .const import DAYS, PALETTE, VT_NUMBER, VT_ONOFF, VT_OPTION, value_type

# ------------------------------------------------------------------ categorie
CAT_HVAC = "hvac"
CAT_LUCI = "luci"
CAT_TVCC = "tvcc"
CAT_ANTINTRUSIONE = "antintrusione"
CAT_TAPPARELLE = "tapparelle"
CAT_IRRIGAZIONE = "irrigazione"
CAT_VENTILAZIONE = "ventilazione"
CAT_ACS = "acs"
CAT_ALTRO = "altro"

CATEGORIES = [
    CAT_HVAC,
    CAT_LUCI,
    CAT_TVCC,
    CAT_ANTINTRUSIONE,
    CAT_TAPPARELLE,
    CAT_IRRIGAZIONE,
    CAT_VENTILAZIONE,
    CAT_ACS,
    CAT_ALTRO,
]

CATEGORY_ICONS = {
    CAT_HVAC: "mdi:thermostat",
    CAT_LUCI: "mdi:lightbulb-group",
    CAT_TVCC: "mdi:cctv",
    CAT_ANTINTRUSIONE: "mdi:shield-home",
    CAT_TAPPARELLE: "mdi:window-shutter",
    CAT_IRRIGAZIONE: "mdi:sprinkler-variant",
    CAT_VENTILAZIONE: "mdi:fan",
    CAT_ACS: "mdi:water-boiler",
    CAT_ALTRO: "mdi:calendar-clock",
}

# Domini proposti nel selettore entità per ogni categoria
CATEGORY_DOMAINS = {
    CAT_HVAC: ["climate", "water_heater", "input_number", "number", "switch", "input_boolean"],
    CAT_LUCI: ["light", "switch", "input_boolean"],
    CAT_TVCC: ["switch", "input_boolean", "camera", "select", "input_select"],
    CAT_ANTINTRUSIONE: ["switch", "input_boolean", "select", "input_select"],
    CAT_TAPPARELLE: ["cover", "input_number", "number", "switch", "input_boolean"],
    CAT_IRRIGAZIONE: ["switch", "input_boolean", "valve"],
    CAT_VENTILAZIONE: ["fan", "switch", "input_boolean", "select", "input_select"],
    CAT_ACS: ["water_heater", "climate", "input_number", "number", "switch", "input_boolean"],
}

# Sottomenu
SEASONS = ["riscaldamento", "raffrescamento", "caldo_freddo"]
TERMINALS = ["radiatori", "pavimento", "soffitto", "fancoil", "split"]
USAGES = ["abitazione", "ufficio", "negozio"]
SUBTYPES = {
    CAT_LUCI: ["interne", "esterne", "giardino", "vetrine"],
    CAT_TVCC: ["interne", "esterne"],
    CAT_ANTINTRUSIONE: ["totale", "perimetrale", "notte"],
    CAT_IRRIGAZIONE: ["prato", "orto", "goccia"],
}
USAGE_CATEGORIES = {
    CAT_HVAC,
    CAT_LUCI,
    CAT_TVCC,
    CAT_ANTINTRUSIONE,
    CAT_TAPPARELLE,
    CAT_VENTILAZIONE,
    CAT_ACS,
}

CONF_CATEGORY = "category"
CONF_SUBTYPE = "subtype"
CONF_SEASON = "season"
CONF_TERMINAL = "terminal"
CONF_USAGE = "usage"

GREY = "#455A64"
YELLOW = "#FFD166"
RED = "#E53935"
GREEN = "#43A047"
BLUE = "#1E88E5"

WEEKDAYS = DAYS[:5]
WEEKEND = DAYS[5:]


# --------------------------------------------------------------- utilità orari
def _m(value: str) -> int:
    if value == "24:00":
        return 1440
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


Ranges = list[tuple[int, int]]


def _r(*pairs: tuple[str, str]) -> Ranges:
    return [(_m(a), _m(b)) for a, b in pairs]


def _occupancy(usage: str) -> dict[str, Ranges]:
    """Fasce di presenza tipiche per utilizzo."""
    if usage == "ufficio":
        return {d: (_r(("08:00", "18:00")) if d in WEEKDAYS else []) for d in DAYS}
    if usage == "negozio":
        return {d: (_r(("09:00", "13:00"), ("15:30", "19:30")) if d != "sun" else []) for d in DAYS}
    # abitazione
    return {
        d: (_r(("06:30", "08:30"), ("17:30", "22:30")) if d in WEEKDAYS else _r(("08:00", "23:00")))
        for d in DAYS
    }


def _complement(ranges: Ranges) -> Ranges:
    out: Ranges = []
    cur = 0
    for start, end in sorted(ranges):
        if start > cur:
            out.append((cur, start))
        cur = max(cur, end)
    if cur < 1440:
        out.append((cur, 1440))
    return out


def _clip(start: int, end: int) -> tuple[int, int]:
    return max(0, start), min(1440, end)


def _slots(base: str, layers: list[tuple[Ranges, str]]) -> list[dict[str, str]]:
    """Costruisce le fasce di un giorno: base + strati sovrapposti nell'ordine dato."""
    arr = [base] * 1440
    for ranges, preset in layers:
        for start, end in ranges:
            start, end = _clip(start, end)
            for minute in range(start, end):
                arr[minute] = preset
    slots: list[dict[str, str]] = []
    for minute in range(1440):
        if minute == 0 or arr[minute] != arr[minute - 1]:
            slots.append({"start": _hhmm(minute), "preset": arr[minute]})
    return slots


def _onoff_week(active: dict[str, Ranges], on_id: str, off_id: str) -> dict[str, list]:
    return {d: _slots(off_id, [(active[d], on_id)]) for d in DAYS}


def _p(pid: str, name: str, icon: str, color: str, value: Any, hvac_mode: str | None = None) -> dict:
    preset = {"id": pid, "name": name, "icon": icon, "color": color, "value": value}
    if hvac_mode:
        preset["hvac_mode"] = hvac_mode
    return preset


def _onoff_values(hass: HomeAssistant, target: str) -> tuple[Any, Any]:
    """Valori 'acceso' e 'spento' adatti al tipo di entità."""
    vtype = value_type(target)
    if vtype == VT_NUMBER:
        domain = target.split(".", 1)[0]
        if domain == "cover":
            return 100, 0
        state = hass.states.get(target)
        attrs = state.attributes if state else {}
        return float(attrs.get("max", 100)), float(attrs.get("min", 0))
    return "on", "off"


def _option_presets(hass: HomeAssistant, target: str, icons: list[str], colors: list[str]) -> list[dict]:
    state = hass.states.get(target)
    options = list((state.attributes.get("options") if state else None) or [])[:6] or ["opzione"]
    return [
        _p(f"opt{i}", str(opt), icons[i % len(icons)], colors[i % len(colors)], str(opt))
        for i, opt in enumerate(options)
    ]


def _simple_onoff(
    hass: HomeAssistant,
    target: str,
    on: tuple[str, str, str, str],
    off: tuple[str, str, str, str],
    active: dict[str, Ranges],
) -> tuple[list, dict]:
    """Profilo a due stati (acceso/spento) con icone e colori della categoria."""
    if value_type(target) == VT_OPTION:
        presets = _option_presets(hass, target, [on[2], off[2]], [on[3], off[3]])
        week = _onoff_week(active, presets[0]["id"], presets[-1]["id"])
        return presets, week
    v_on, v_off = _onoff_values(hass, target)
    presets = [_p(on[0], on[1], on[2], on[3], v_on), _p(off[0], off[1], off[2], off[3], v_off)]
    return presets, _onoff_week(active, on[0], off[0])


# ---------------------------------------------------------------------- HVAC
_HEAT = {
    #            comfort, comfort+, eco, notte, preriscaldo (min)
    "radiatori": (20.0, 21.0, 17.0, 16.0, 60),
    "pavimento": (20.0, 20.5, 18.5, 18.0, 120),
    "soffitto": (20.0, 20.5, 18.0, 17.5, 90),
    "fancoil": (20.0, 21.0, 17.0, 16.0, 30),
    "split": (20.0, 21.0, 17.0, None, 20),  # notte: spento
}
_COOL = {
    "radiatori": (26.0, 25.0, 28.0, None, 30),
    "pavimento": (26.0, 25.5, 27.0, 28.0, 120),
    "soffitto": (26.0, 25.5, 27.0, 28.0, 90),
    "fancoil": (26.0, 25.0, 28.0, None, 30),
    "split": (26.0, 25.0, 28.0, None, 20),
}


def _hvac(hass: HomeAssistant, target: str, season: str, terminal: str, usage: str) -> tuple[list, dict]:
    domain = target.split(".", 1)[0]
    cooling = season == "raffrescamento"
    comfort, plus, eco, night, pre = (_COOL if cooling else _HEAT).get(terminal, _HEAT["radiatori"])
    occ = _occupancy(usage)

    active = {
        d: [(s - pre, e) for s, e in occ[d]]
        for d in DAYS
    }
    vtype = value_type(target)
    if vtype == VT_ONOFF:
        on = ("comfort", "Comfort", "mdi:snowflake" if cooling else "mdi:fire", "#5AB8FF" if cooling else "#FF7A75")
        return _simple_onoff(hass, target, on, ("spento", "Spento", "mdi:power-off", GREY), active)
    if vtype == VT_OPTION:
        icons = ["mdi:home", "mdi:leaf", "mdi:weather-night", "mdi:power-off"]
        presets = _option_presets(hass, target, icons, PALETTE)
        return presets, _onoff_week(active, presets[0]["id"], presets[-1]["id"])

    is_climate = domain == "climate"
    mode = None
    if is_climate and season != "caldo_freddo":
        mode = "cool" if cooling else "heat"

    if cooling:
        presets = [
            _p("comfort", "Comfort", "mdi:snowflake", "#5AB8FF", comfort, mode),
            _p("comfort_plus", "Comfort +", "mdi:snowflake-alert", BLUE, plus, mode),
            _p("eco", "Economico", "mdi:leaf", "#8FD8C0", eco, mode),
        ]
    else:
        presets = [
            _p("comfort", "Comfort", "mdi:home", "#FDB48A", comfort, mode),
            _p("comfort_plus", "Comfort +", "mdi:fire", "#FF7A75", plus, mode),
            _p("eco", "Economico", "mdi:leaf", "#8FD8C0", eco, mode),
        ]
    if night is None:
        if is_climate:
            presets.append(_p("notte", "Spento", "mdi:power-off", GREY, eco, "off"))
        elif domain == "water_heater":
            presets.append(_p("notte", "Spento", "mdi:power-off", GREY, "off"))
        else:
            presets.append(_p("notte", "Notte", "mdi:weather-night", "#8E8CF8", 29.0 if cooling else 15.0))
    else:
        presets.append(
            _p("notte", "Notte", "mdi:weather-night", "#8E8CF8" if cooling else "#5AB8FF", night, mode)
        )

    week = {}
    for d in DAYS:
        blocks = occ[d]
        layers: list[tuple[Ranges, str]] = []
        if blocks:
            layers.append(([(blocks[0][0], blocks[-1][1])], "eco"))  # pause diurne
            layers.append(([(s - pre, s) for s, _ in blocks], "comfort_plus"))  # preriscaldo / preraffrescamento
            layers.append((blocks, "comfort"))
        week[d] = _slots("notte", layers)
    return presets, week


# -------------------------------------------------------------- altre categorie
def _luci(hass: HomeAssistant, target: str, subtype: str, usage: str) -> tuple[list, dict]:
    if subtype == "esterne":
        if usage == "ufficio":
            active = {d: (_r(("06:30", "08:30"), ("17:00", "20:00")) if d in WEEKDAYS else []) for d in DAYS}
        elif usage == "negozio":
            active = {d: (_r(("17:00", "22:00")) if d != "sun" else []) for d in DAYS}
        else:
            active = {d: _r(("05:30", "07:30"), ("17:30", "24:00")) for d in DAYS}
    elif subtype == "giardino":
        active = {d: _r(("18:30", "23:00")) for d in DAYS}
    elif subtype == "vetrine":
        active = {d: _r(("17:00", "24:00")) for d in DAYS}
    else:  # interne
        if usage == "ufficio":
            active = {d: (_r(("07:45", "18:15")) if d in WEEKDAYS else []) for d in DAYS}
        elif usage == "negozio":
            active = {d: (_r(("08:45", "13:15"), ("15:15", "19:45")) if d != "sun" else []) for d in DAYS}
        else:
            active = {
                d: (_r(("06:30", "08:00"), ("17:30", "23:30")) if d in WEEKDAYS else _r(("08:00", "09:30"), ("17:30", "24:00")))
                for d in DAYS
            }
    return _simple_onoff(
        hass,
        target,
        ("accese", "Accese", "mdi:lightbulb-on", YELLOW),
        ("spente", "Spente", "mdi:lightbulb-off", GREY),
        active,
    )


def _away(usage: str) -> dict[str, Ranges]:
    """Fasce di assenza durante il giorno (esclusa la notte per le abitazioni)."""
    occ = _occupancy(usage)
    if usage == "abitazione":
        return {d: (_r(("08:30", "17:30")) if d in WEEKDAYS else []) for d in DAYS}
    return {d: _complement(occ[d]) for d in DAYS}


def _tvcc(hass: HomeAssistant, target: str, subtype: str, usage: str) -> tuple[list, dict]:
    away = _away(usage)
    if subtype == "esterne":
        active = {d: away[d] + _r(("00:00", "07:00"), ("19:00", "24:00")) for d in DAYS}
    else:
        active = away
    return _simple_onoff(
        hass,
        target,
        ("attiva", "Registrazione attiva", "mdi:cctv", RED),
        ("non_attiva", "Non attiva", "mdi:cctv-off", GREY),
        active,
    )


def _antintrusione(hass: HomeAssistant, target: str, subtype: str, usage: str) -> tuple[list, dict]:
    away = _away(usage)
    night = _r(("00:00", "06:30"), ("23:00", "24:00"))
    if subtype == "notte":
        active = {d: (night if usage == "abitazione" else away[d]) for d in DAYS}
    elif subtype == "perimetrale":
        active = {d: away[d] + (night if usage == "abitazione" else []) for d in DAYS}
    else:  # totale: inserito quando non c'è nessuno
        active = away
    name_on = "Inserito notte" if subtype == "notte" else "Inserito"
    icon_on = "mdi:shield-moon" if subtype == "notte" else "mdi:shield-lock"
    return _simple_onoff(
        hass,
        target,
        ("inserito", name_on, icon_on, RED),
        ("disinserito", "Disinserito", "mdi:shield-off", GREEN),
        active,
    )


def _tapparelle(hass: HomeAssistant, target: str, usage: str) -> tuple[list, dict]:
    if usage == "ufficio":
        open_ = {d: (_r(("07:45", "18:15")) if d in WEEKDAYS else []) for d in DAYS}
    elif usage == "negozio":
        open_ = {d: (_r(("08:30", "20:00")) if d != "sun" else []) for d in DAYS}
    else:
        open_ = {d: (_r(("07:00", "21:00")) if d in WEEKDAYS else _r(("08:30", "21:30"))) for d in DAYS}
    presets, week = _simple_onoff(
        hass,
        target,
        ("aperte", "Aperte", "mdi:window-shutter-open", "#5AB8FF"),
        ("chiuse", "Chiuse", "mdi:window-shutter", GREY),
        open_,
    )
    if value_type(target) == VT_NUMBER:
        presets.insert(1, _p("meta", "A metà", "mdi:window-shutter", "#FDB48A", 50))
    return presets, week


def _irrigazione(hass: HomeAssistant, target: str, subtype: str) -> tuple[list, dict]:
    if subtype == "orto":
        active = {d: _r(("06:00", "06:20"), ("20:30", "20:50")) for d in DAYS}
    elif subtype == "goccia":
        active = {d: _r(("07:00", "07:15")) for d in DAYS}
    else:  # prato: a giorni alterni, all'alba
        active = {d: (_r(("05:30", "06:00")) if d in ("mon", "wed", "fri", "sun") else []) for d in DAYS}
    return _simple_onoff(
        hass,
        target,
        ("attiva", "Irrigazione", "mdi:sprinkler-variant", BLUE),
        ("ferma", "Ferma", "mdi:water-off", GREY),
        active,
    )


def _ventilazione(hass: HomeAssistant, target: str, usage: str) -> tuple[list, dict]:
    occ = _occupancy(usage)
    active = {d: [(s - 30, e + 30) for s, e in occ[d]] for d in DAYS}
    return _simple_onoff(
        hass,
        target,
        ("attiva", "Attiva", "mdi:fan", "#8FD8C0"),
        ("spenta", "Spenta", "mdi:fan-off", GREY),
        active,
    )


def _acs(hass: HomeAssistant, target: str, usage: str) -> tuple[list, dict]:
    occ = _occupancy(usage)
    active = {d: [(s - 60, e) for s, e in occ[d]] for d in DAYS}
    if value_type(target) == VT_NUMBER:
        presets = [
            _p("comfort", "Comfort", "mdi:water-boiler", "#FF7A75", 50.0),
            _p("eco", "Economico", "mdi:leaf", "#8FD8C0", 40.0),
        ]
        return presets, _onoff_week(active, "comfort", "eco")
    return _simple_onoff(
        hass,
        target,
        ("acceso", "Acceso", "mdi:water-boiler", "#FF7A75"),
        ("spento", "Spento", "mdi:water-boiler-off", GREY),
        active,
    )


# ---------------------------------------------------------------- entry point
def build_profile(hass: HomeAssistant, target: str, info: dict[str, Any]) -> tuple[list, dict] | None:
    """Impostazioni e programma per la categoria scelta. None = profilo generico."""
    category = info.get(CONF_CATEGORY) or CAT_ALTRO
    usage = info.get(CONF_USAGE) or "abitazione"
    subtype = info.get(CONF_SUBTYPE) or ""
    if category == CAT_HVAC:
        return _hvac(hass, target, info.get(CONF_SEASON) or "riscaldamento", info.get(CONF_TERMINAL) or "radiatori", usage)
    if category == CAT_LUCI:
        return _luci(hass, target, subtype or "interne", usage)
    if category == CAT_TVCC:
        return _tvcc(hass, target, subtype or "interne", usage)
    if category == CAT_ANTINTRUSIONE:
        return _antintrusione(hass, target, subtype or "totale", usage)
    if category == CAT_TAPPARELLE:
        return _tapparelle(hass, target, usage)
    if category == CAT_IRRIGAZIONE:
        return _irrigazione(hass, target, subtype or "prato")
    if category == CAT_VENTILAZIONE:
        return _ventilazione(hass, target, usage)
    if category == CAT_ACS:
        return _acs(hass, target, usage)
    return None
