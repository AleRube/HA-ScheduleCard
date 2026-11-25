"""Config flow per Schedula."""

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

HVAC_MODES = [HVAC_MODE_NONE, "heat", "cool", "heat_cool", "auto"]


def _options_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_TARGET, default=defaults.get(CONF_TARGET)): EntitySelector(
                EntitySelectorConfig(domain=TARGET_DOMAINS)
            ),
            vol.Required(
                CONF_HVAC_MODE, default=defaults.get(CONF_HVAC_MODE, HVAC_MODE_NONE)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=HVAC_MODES,
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_HVAC_MODE,
                )
            ),
            vol.Required(
                CONF_APPLY_ON_START, default=defaults.get(CONF_APPLY_ON_START, True)
            ): BooleanSelector(),
        }
    )


class SchedulaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Crea una nuova schedulazione."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={CONF_TARGET: user_input[CONF_TARGET]},
                options={
                    CONF_TARGET: user_input[CONF_TARGET],
                    CONF_HVAC_MODE: user_input.get(CONF_HVAC_MODE, HVAC_MODE_NONE),
                    CONF_APPLY_ON_START: user_input.get(CONF_APPLY_ON_START, True),
                },
            )

        schema = vol.Schema(
            {vol.Required(CONF_NAME, default="Schedulazione di default"): TextSelector()}
        ).extend(_options_schema({}).schema)
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SchedulaOptionsFlow()


class SchedulaOptionsFlow(OptionsFlow):
    """Modifica entità target e opzioni."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        defaults = {
            CONF_TARGET: self.config_entry.options.get(
                CONF_TARGET, self.config_entry.data.get(CONF_TARGET)
            ),
            CONF_HVAC_MODE: self.config_entry.options.get(CONF_HVAC_MODE, HVAC_MODE_NONE),
            CONF_APPLY_ON_START: self.config_entry.options.get(CONF_APPLY_ON_START, True),
        }
        return self.async_show_form(step_id="init", data_schema=_options_schema(defaults))
