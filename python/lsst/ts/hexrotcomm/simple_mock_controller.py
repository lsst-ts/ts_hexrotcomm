# This file is part of ts_hexrotcomm.
#
# Developed for the Rubin Observatory Telescope and Site System.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License

__all__ = [
    "SIMPLE_TELEMETRY_PORT",
    "SimpleCommandCode",
    "SimpleConfig",
    "SimpleTelemetry",
    "SimpleMockController",
]

import ctypes
import enum
import logging
import typing

from lsst.ts import tcpip
from lsst.ts.xml.enums.MTHexapod import ApplicationStatus, ControllerState

from . import structs
from .base_mock_controller import BaseMockController, CommandError

# Default port for the mock controller.
# This is an arbitrary value chosen to be well away from the telemetry ports
# for the MT camera rotator and two MT hexapods.
SIMPLE_TELEMETRY_PORT = 6210

# Set False to disable output of configuration.
# Use this to test no config at connect time.
ENABLE_CONFIG = True


class SimpleCommandCode(enum.IntEnum):
    SET_STATE = 1
    ENABLE_DRIVES = 2
    SET_ENABLED_SUBSTATE = enum.auto()
    MOVE = enum.auto()


class SimpleConfig(ctypes.Structure):
    """Configuration of SimpleMockController."""

    _pack_ = 1
    _fields_ = [
        ("drives_enabled", ctypes.c_bool),
        ("min_position", ctypes.c_double),
        ("max_position", ctypes.c_double),
        ("max_velocity", ctypes.c_double),
    ]


class SimpleTelemetry(ctypes.Structure):
    """Telemetry from SimpleMockController."""

    _pack_ = 1
    _fields_ = [
        ("application_status", ctypes.c_uint),
        ("state", ctypes.c_double),
        ("enabled_substate", ctypes.c_double),
        ("curr_position", ctypes.c_double),
        ("cmd_position", ctypes.c_double),
    ]


class SimpleMockController(BaseMockController):
    """Simple mock controller for unit testing BaseMockController.

    The MOVE command sets cmd_position and curr_position,
    then the controller slowly increments curr_position.

    Parameters
    ----------
    log : `logging.Logger`
        Logger.
    port : `int`
        Port for the TCP/IP server.
        Specify 0 to choose random values for both ports;
        this is recommended for unit tests, to avoid collision
        with other tests.
    initial_state : `lsst.ts.xml.enums.MTHexapod.ControllerState` (optional)
        Initial state of mock controller.
    host : `str` or `None`, optional
        IP address for the TCP/IP server. Typically "127.0.0.1" (the default)
        for an IPV4 server and "::" for an IPV6 server.
        If `None` then bind to all network interfaces and run both
        IPV4 and IPV6 servers.
        Do not specify `None` with port=0 (see
        `lsst.ts.tcpip.OneClientServer` for details).

    Notes
    -----
    The ``MOVE`` command is rejected if the new position is
    not within the configured limits.
    """

    def __init__(
        self,
        log: logging.Logger,
        port: int = SIMPLE_TELEMETRY_PORT,
        host: str = tcpip.LOCAL_HOST,
        initial_state: enum.IntEnum = ControllerState.STANDBY,
    ) -> None:
        config = SimpleConfig()
        config.drives_enabled = False
        config.min_position = -25
        config.max_position = 25
        config.max_velocity = 47
        telemetry = SimpleTelemetry()
        extra_commands = {SimpleCommandCode.MOVE: self.do_position_set}
        super().__init__(
            log=log,
            CommandCode=SimpleCommandCode,
            extra_commands=extra_commands,
            config=config,
            telemetry=telemetry,
            port=port,
            host=host,
            initial_state=initial_state,
        )
        self.telemetry.application_status = ApplicationStatus.DDS_COMMAND_SOURCE

    async def do_position_set(self, command: structs.Command) -> None:
        self.assert_state(ControllerState.ENABLED)
        position = command.param1
        if position < self.config.min_position or position > self.config.max_position:
            raise CommandError(
                f"Position {position} out of range [{self.config.min_position}, {self.config.max_position}]."
            )
        self.telemetry.cmd_position = position
        self.telemetry.curr_position = position

    async def update_telemetry(self, curr_tai: float) -> None:
        self.telemetry.curr_position += 0.001

    async def end_run_command(self, command: structs.Command, cmd_method: typing.Coroutine) -> None:
        pass

    async def write_config(self) -> None:
        if ENABLE_CONFIG:
            await super().write_config()
        else:
            self.log.warning("Not writing config because ENABLE_CONFIG false")
