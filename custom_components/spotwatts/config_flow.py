"""Config flow: a price area per entry; VAT on or off as an option."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectSelectorMode
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .api import SpotwattsClient, SpotwattsError
from .const import CONF_VAT, CONF_ZONE, DOMAIN, ZONES


class SpotwattsConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            zone = user_input[CONF_ZONE].upper()
            await self.async_set_unique_id(zone)
            self._abort_if_unique_id_configured()
            today = dt_util.utcnow().astimezone(dt_util.get_time_zone(ZONES[zone])).date()
            try:
                day = await SpotwattsClient(async_get_clientsession(self.hass)).day(zone, today)
            except SpotwattsError:
                errors["base"] = "cannot_connect"
            else:
                if day is None:
                    errors["base"] = "no_prices"
                else:
                    return self.async_create_entry(
                        title=f"Spotwatts {zone}", data={CONF_ZONE: zone}, options={CONF_VAT: user_input[CONF_VAT]}
                    )

        # Selector option keys must be lower case to be translatable
        schema = vol.Schema(
            {
                vol.Required(CONF_ZONE): SelectSelector(
                    SelectSelectorConfig(
                        options=[zone.lower() for zone in ZONES],
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="zone",
                    )
                ),
                vol.Required(CONF_VAT, default=True): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SpotwattsOptionsFlow()


class SpotwattsOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        schema = vol.Schema({vol.Required(CONF_VAT, default=self.config_entry.options.get(CONF_VAT, True)): bool})
        return self.async_show_form(step_id="init", data_schema=schema)
