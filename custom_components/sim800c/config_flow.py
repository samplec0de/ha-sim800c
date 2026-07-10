"""Config flow for SIM800C."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE

from .const import CONF_BAUD_RATE, DEFAULT_BAUD_RATE, DOMAIN, LOGGER
from .hub import ModemHub
from .modem import ModemError

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


class SIM800CConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SIM800C."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial user setup step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            device = user_input[CONF_DEVICE]
            baud = user_input[CONF_BAUD_RATE]
            await self.async_set_unique_id(device)
            self._abort_if_unique_id_configured()

            hub = ModemHub(device, baud)
            try:
                await hub.async_start()
                await hub.async_update_diagnostics()
            except ModemError as err:
                LOGGER.error("SIM800C validation failed: %s", err)
                errors["base"] = "cannot_connect"
            except OSError as err:
                LOGGER.error("SIM800C serial error: %s", err)
                errors["base"] = "cannot_connect"
            else:
                if not hub.registered:
                    errors["base"] = "not_registered"
            finally:
                await hub.async_stop()

            if not errors:
                return self.async_create_entry(
                    title=f"SIM800C ({device})", data=user_input
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE, default="/dev/ttyUSB0"): str,
                vol.Optional(CONF_BAUD_RATE, default=DEFAULT_BAUD_RATE): int,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
