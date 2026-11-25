"""Costanti per Schedula."""

DOMAIN = "schedula"
VERSION = "1.3.0"

PLATFORMS = ["sensor", "switch"]

CONF_TARGET = "target_entity"
CONF_HVAC_MODE = "hvac_mode"
CONF_APPLY_ON_START = "apply_on_start"

HVAC_MODE_NONE = "none"

STORAGE_VERSION = 1

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# Tipo di valore gestito da un'impostazione (preset) in base al dominio dell'entità
VT_NUMBER = "number"
VT_ONOFF = "onoff"
VT_OPTION = "option"

NUMBER_DOMAINS = {"climate", "water_heater", "input_number", "number", "cover"}
OPTION_DOMAINS = {"input_select", "select"}
ONOFF_DOMAINS = {
    "switch",
    "light",
    "fan",
    "input_boolean",
    "automation",
    "siren",
    "humidifier",
    "script",
    "group",
    "camera",
    "valve",
}

TARGET_DOMAINS = sorted(NUMBER_DOMAINS | OPTION_DOMAINS | ONOFF_DOMAINS)

CARD_URL = "/schedula_static/schedula-card.js"

SERVICE_SAVE = "save"
SERVICE_SET_ENABLED = "set_enabled"
SERVICE_APPLY_NOW = "apply_now"
SERVICE_SET_TARGET = "set_target"

ATTR_SCHEDULE_ID = "schedule_id"
ATTR_PRESETS = "presets"
ATTR_WEEK = "week"
ATTR_ENABLED = "enabled"

HVAC_MODES_ALLOWED = {"heat", "cool", "heat_cool", "auto", "dry", "fan_only", "off"}

PALETTE = [
    "#FDB48A",  # arancio chiaro (Comfort)
    "#FF7A75",  # rosso (Comfort +)
    "#8FD8C0",  # verde (Economico)
    "#5AB8FF",  # azzurro (Notte)
    "#8E8CF8",  # viola
    "#FFD166",  # giallo
    "#C792EA",  # lilla
    "#9E9E9E",  # grigio
]


def value_type(entity_id: str) -> str:
    """Restituisce il tipo di valore per l'entità target."""
    domain = entity_id.split(".", 1)[0]
    if domain in NUMBER_DOMAINS:
        return VT_NUMBER
    if domain in OPTION_DOMAINS:
        return VT_OPTION
    return VT_ONOFF
