"""Config flow for Tecnosistemi integration."""

from __future__ import annotations

import json
from pathlib import Path
import socket
import threading
import time
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from tecnosystemi_unofficial import IDPManager

from .const import (
    COMMON_SUBNETS,
    CONF_DEVICE_TYPE,
    CONF_IP,
    CONF_PIN,
    CONF_SERIAL,
    DEVICE_TYPE_PICO,
    DEVICE_TYPE_POLARIS5X,
    DOMAIN,
)

SEND_PORT = 40070
RECV_PORT = 40069


# ---------------------------------------------------------------------------
# Sync helpers — all run in executor
# ---------------------------------------------------------------------------


def _do_discovery(
    subnets: list[str] = COMMON_SUBNETS, timeout: float = 15.0
) -> list[str]:
    """Broadcast UDP probe and return responding device IPs."""
    from tecnosystemi_unofficial.shared_listener import SharedUDPListener

    found: list[str] = []
    lock = threading.Lock()
    probe = json.dumps(
        {"cmd": "pico_info", "pin": "-1", "idp": 1, "frm": "app"}
    ).encode()

    def on_packet(packet: dict, addr: tuple) -> None:
        if packet.get("res") in (1, 99):
            with lock:
                if addr[0] not in found:
                    found.append(addr[0])

    listener = SharedUDPListener.get(RECV_PORT)
    listener.register_raw(on_packet)

    send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    send_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        for subnet in subnets:
            send_sock.sendto(probe, (f"{subnet}.255", SEND_PORT))
        if "192.168.4" in subnets:
            send_sock.sendto(probe, ("192.168.4.1", SEND_PORT))
    finally:
        send_sock.close()

    time.sleep(timeout)
    listener.unregister_raw(on_packet)
    return found


async def _validate_and_fetch_info(ip: str, pin: str) -> dict | None:
    """
    Validate PIN against a Pico device and return device info on success.
    Returns None if PIN is wrong or device unreachable.
    """
    from tecnosystemi_unofficial import TecnoClient
    from tecnosystemi_unofficial.devices import PicoDevice

    async with TecnoClient(
        ip=ip, idp_manager=IDPManager(backend="file", path=Path(".idp.store"))
    ) as client:
        pico = PicoDevice(client, pin=pin)
        try:
            if not await pico.check_pin():
                return None
            return await pico.get_info()
        except Exception:
            return None


async def _validate_polaris_and_fetch_info(ip: str, pin: str) -> dict | None:
    """
    Validate PIN against a Polaris 5X device and return device info on success.
    Returns None if PIN is wrong or device unreachable.
    """
    from tecnosystemi_unofficial import PolarisClient
    from tecnosystemi_unofficial.devices import Polaris5XDevice

    client = PolarisClient(ip=ip, pin=pin, timeout=10.0)
    polaris = Polaris5XDevice(client)
    try:
        if not await polaris.check_pin():
            return None
        state = await polaris.get_state()
        if state is None:
            return None
        return {"name": state.get("name"), "fw_ver": state.get("fw_ver")}
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Config flow
# ---------------------------------------------------------------------------


class TecnosistemiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Tecnosistemi config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._ip: str | None = None
        self._device_type: str = DEVICE_TYPE_PICO
        self._name: str = ""
        self._discovered: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        return self.async_show_menu(
            step_id="user",
            menu_options=["discover", "manual"],
        )

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None and "ip" in user_input:
            self._ip = user_input["ip"]
            return await self.async_step_pin()

        # Run discovery (first visit or retry after "no devices found")
        discovered: list[str] = await self.hass.async_add_executor_job(_do_discovery)

        if not discovered:
            errors["base"] = "no_devices_found"
            return self.async_show_form(
                step_id="discover",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        self._discovered = discovered
        return self.async_show_form(
            step_id="discover",
            data_schema=vol.Schema({vol.Required(CONF_IP): vol.In(self._discovered)}),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            ip = user_input[CONF_IP].strip()
            try:
                socket.inet_aton(ip)
            except OSError:
                errors[CONF_IP] = "invalid_ip"
            else:
                self._ip = ip
                self._device_type = user_input.get(CONF_DEVICE_TYPE, DEVICE_TYPE_PICO)
                self._name = user_input.get(CONF_NAME, "").strip()
                return await self.async_step_pin()

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IP): str,
                    vol.Required(CONF_DEVICE_TYPE, default=DEVICE_TYPE_PICO): vol.In(
                        {
                            DEVICE_TYPE_PICO: "Pico / Pico Pro (VMC)",
                            DEVICE_TYPE_POLARIS5X: "Polaris 5X (multi-zone HVAC)",
                        }
                    ),
                    vol.Optional(CONF_NAME): str,
                }
            ),
            errors=errors,
        )

    async def async_step_pin(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            pin = user_input[CONF_PIN].strip()

            if self._device_type == DEVICE_TYPE_POLARIS5X:
                info: dict | None = await _validate_polaris_and_fetch_info(
                    self._ip, pin
                )
                serial: str = self._ip  # Polaris 5X has no serial field
            else:
                info = await _validate_and_fetch_info(self._ip, pin)
                serial = (info.get("ser") or self._ip) if info else self._ip

            if info is None:
                errors[CONF_PIN] = "invalid_pin"
            else:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured(updates={CONF_IP: self._ip})

                title = self._name or info.get("name") or self._ip
                data = {
                    CONF_IP: self._ip,
                    CONF_PIN: pin,
                    CONF_SERIAL: serial,
                    CONF_DEVICE_TYPE: self._device_type,
                }
                if self._name:
                    data[CONF_NAME] = self._name

                return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="pin",
            data_schema=vol.Schema({vol.Required(CONF_PIN, default="1234"): str}),
            errors=errors,
            description_placeholders={"ip": self._ip},
        )
