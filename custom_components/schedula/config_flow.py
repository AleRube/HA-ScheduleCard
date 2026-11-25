"""Config flow per Schedula: tipo di impianto → dettagli → entità."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CONF_APPLY_ON_START,
    CONF_HVAC_MODE,
    CONF_TARGET,
    DOMAIN,
    HVAC_MODE_NONE,
    TARGET_DOMAINS,
)
from .profiles import (
    CAT_ALTRO,
    CAT_HVAC,
    CATEGORIES,
    CATEGORY_DOMAINS,
    CONF_CATEGORY,
    CONF_SEASON,
    CONF_SUBTYPE,
    CONF_TERMINAL,
    CONF_USAGE,
    SEASONS,
    SUBTYPES,
    TERMINALS,
    USAGE_CATEGORIES,
    USAGES,
)

HVAC_MODES = [HVAC_MODE_NONE, "heat", "cool", "heat_cool", "auto"]

# Nome proposto per la schedulazione
DEFAULT_NAMES = {
    "hvac": "Clima",
    "luci": "Luci",
    "tvcc": "TVCC",
    "antintrusione": "Antintrusione",
    "tapparelle": "Tapparelle",
    "irrigazione": "Irrigazione",
    "ventilazione": "Ventilazione",
    "acs": "Acqua calda sanitaria",
    "altro": "Schedulazione",
}


def _select(options: list[str], key: str, mode: SelectSelectorMode = SelectSelectorMode.LIST) -> SelectSelector:
    return SelectSelector(SelectSelectorConfig(options=options, mode=mode, translation_key=key))


def _options_schema(defaults: dict[str, Any], domains: list[str]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_TARGET, default=defaults.get(CONF_TARGET)): EntitySelector(
                EntitySelectorConfig(domain=domains)
            ),
            vol.Required(
                CONF_HVAC_MODE, default=defaults.get(CONF_HVAC_MODE, HVAC_MODE_NONE)
            ): _select(HVAC_MODES, CONF_HVAC_MODE, SelectSelectorMode.DROPDOWN),
            vol.Required(
                CONF_APPLY_ON_START, default=defaults.get(CONF_APPLY_ON_START, True)
            ): BooleanSelector(),
        }
    )


class SchedulaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Crea una nuova schedulazione."""

    VERSION = 1

    def __init__(self) -> None:
        self._category: str = CAT_ALTRO

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Primo passo: tipo di impianto."""
        if user_input is not None:
            self._category = user_input[CONF_CATEGORY]
            return await self.async_step_details()
        schema = vol.Schema(
            {vol.Required(CONF_CATEGORY, default=CAT_HVAC): _select(CATEGORIES, CONF_CATEGORY)}
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_details(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Secondo passo: dettagli del tipo scelto, nome ed entità."""
        cat = self._category
        if user_input is not None:
            data = {CONF_TARGET: user_input[CONF_TARGET], CONF_CATEGORY: cat}
            for key in (CONF_SEASON, CONF_TERMINAL, CONF_SUBTYPE, CONF_USAGE):
                if key in user_input:
                    data[key] = user_input[key]
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=data,
                options={
                    CONF_TARGET: user_input[CONF_TARGET],
                    CONF_HVAC_MODE: HVAC_MODE_NONE,
                    CONF_APPLY_ON_START: True,
                },
            )

        fields: dict[Any, Any] = {
            vol.Required(CONF_NAME, default=DEFAULT_NAMES.get(cat, "Schedulazione")): TextSelector()
        }
        if cat == CAT_HVAC:
            fields[vol.Required(CONF_SEASON, default="riscaldamento")] = _select(SEASONS, CONF_SEASON)
            fields[vol.Required(CONF_TERMINAL, default="radiatori")] = _select(TERMINALS, CONF_TERMINAL)
        if cat in SUBTYPES:
            fields[vol.Required(CONF_SUBTYPE, default=SUBTYPES[cat][0])] = _select(SUBTYPES[cat], f"subtype_{cat}")
        if cat in USAGE_CATEGORIES:
            fields[vol.Required(CONF_USAGE, default="abitazione")] = _select(USAGES, CONF_USAGE)
        fields[vol.Required(CONF_TARGET)] = EntitySelector(
            EntitySelectorConfig(domain=CATEGORY_DOMAINS.get(cat, TARGET_DOMAINS))
        )
        return self.async_show_form(step_id="details", data_schema=vol.Schema(fields))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SchedulaOptionsFlow()


class SchedulaOptionsFlow(OptionsFlow):
    """Modifica entità target e opzioni."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        entry = self.config_entry
        defaults = {
            CONF_TARGET: entry.options.get(CONF_TARGET, entry.data.get(CONF_TARGET)),
            CONF_HVAC_MODE: entry.options.get(CONF_HVAC_MODE, HVAC_MODE_NONE),
            CONF_APPLY_ON_START: entry.options.get(CONF_APPLY_ON_START, True),
        }
        domains = CATEGORY_DOMAINS.get(entry.data.get(CONF_CATEGORY, CAT_ALTRO), TARGET_DOMAINS)
        return self.async_show_form(step_id="init", data_schema=_options_schema(defaults, domains))
