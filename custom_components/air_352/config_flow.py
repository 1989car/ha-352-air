"""Config flow for the 352 fresh-air integration."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (DEFAULT_AUTH_CODE, DEFAULT_COMPANY_CODE, DEVICE_TYPE_BY_MODEL, DOMAIN, MODELS)


def _mac_valid(mac: str) -> bool:
    return re.fullmatch(r"(?i)([0-9a-f]{2}:){5}[0-9a-f]{2}", mac.strip()) is not None


class Air352ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the 352 integration."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not _mac_valid(user_input[CONF_MAC]):
                errors[CONF_MAC] = "invalid_mac"
            else:
                model = user_input[CONF_MODEL]
                return self.async_create_entry(
                    title=f"352 {MODELS.get(model, model)} ({user_input[CONF_MAC]})",
                    data={
                        CONF_HOST: user_input.get(CONF_HOST) or None,
                        CONF_MAC: user_input[CONF_MAC].strip().upper(),
                        CONF_MODEL: model,
                        "device_type": user_input.get("device_type", DEVICE_TYPE_BY_MODEL.get(model, 0x04)),
                        "auth_code": user_input.get("auth_code", DEFAULT_AUTH_CODE),
                        "company_code": user_input.get("company_code", DEFAULT_COMPANY_CODE),
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_MAC): str,
                vol.Optional(CONF_HOST, description={"suggested_value": "10.1.3.23"}): str,
                vol.Required(CONF_MODEL, default="g30"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[{"value": k, "label": v} for k, v in MODELS.items()],
                    )
                ),
                vol.Optional("company_code", default=DEFAULT_COMPANY_CODE): int,
                vol.Optional("device_type", default=DEVICE_TYPE_BY_MODEL.get("g30")): int,
                vol.Optional("auth_code", default=DEFAULT_AUTH_CODE): int,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
