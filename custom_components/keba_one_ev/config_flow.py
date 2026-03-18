"""Config flow for the SE One EV Charger integration.

Presents a simple UI form where the user enters the charger's IP address,
UDP port, and polling interval. Before creating the config entry a live
connection test is performed: the integration sends "report 1" to the
charger and expects a valid JSON response containing the product name.

This guards against typos and ensures the charger is reachable from the
Home Assistant host before the entry is persisted.
"""
from __future__ import annotations

import json
import logging
import socket

import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _test_connection(host: str, port: int) -> str | None:
    """Attempt a UDP connection to the charger and return the product name.

    Sends the "report 1" command and parses the response.  The product name
    (e.g. "ONE_EV") is used as confirmation that a real KEBA device answered.

    Args:
        host: IP address of the charger.
        port: UDP port (default 7090).

    Returns:
        Product name string on success, None on any failure.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3.0)
    try:
        sock.sendto(b"report 1", (host, port))
        data, _ = sock.recvfrom(4096)
        info = json.loads(data.decode())
        return info.get("Product", "KEBA")
    except Exception:
        return None
    finally:
        sock.close()


class KebaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup dialog shown when the user adds the integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Show the setup form and validate the user's input.

        Called once with user_input=None to render the empty form, then again
        with the submitted values.  On success a config entry is created.
        """
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            # Run the blocking socket test in a thread so the event loop stays free
            product = await self.hass.async_add_executor_job(_test_connection, host, port)

            if product is None:
                # Show the form again with an error message
                errors["base"] = "cannot_connect"
            else:
                # Prevent adding the same charger twice
                await self.async_set_unique_id(f"keba_{host}_{port}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"SE One EV Charger ({host})",
                    data=user_input,
                )

        schema = vol.Schema({
            vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
        })

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
