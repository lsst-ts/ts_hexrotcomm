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

__all__ = ["BaseMockController"]

import abc
import asyncio
import ctypes
import logging
import math
import typing
from enum import IntEnum

from lsst.ts import tcpip, utils
from lsst.ts.xml.enums.MTHexapod import ControllerState, EnabledSubstate

from . import enums, structs


class CommandError(Exception):
    """Low-level command failed."""

    pass


class BaseMockController(tcpip.OneClientReadLoopServer, abc.ABC):
    """Base class for a mock Moog TCP/IP controller with states.

    The controller uses two TCP/IP server sockets,
    one to read commands and the other to write telemetry.

    Parameters
    ----------
    log : `logging.Logger`
        Logger.
    extra_commands : dict of command key: method
        Device-specific commands, as a dict of command key (as returned by
        `get_command_key`): method to call for that command.
        Note: BaseMockController already supports the standard state
        transition commands, including CLEAR_ERROR.
        If the command is not done when the method returns,
        the method should return the predicted duration, in seconds.
    CommandCode : `enum`
        Command codes.
    config : `ctypes.Structure`
        Configuration data that must contain the "drives_enabled" field as
        boolean. May be modified.
    telemetry : `ctypes.Structure`
        Telemetry data. Modified by `update_telemetry`.
    port : `int`
        TCP/IP port.
        Specify 0 to choose a random free port; this is recommended
        for unit tests, to avoid collision with other tests.
        Do not specify 0 with host=None (see `lsst.ts.tcpip.OneClientServer`).
    host : `str` or `None`, optional
        IP address for this server. Typically "127.0.0.1" (the default)
        for an IPV4 server and "::" for an IPV6 server.
        If `None` then bind to all network interfaces and run both
        IPV4 and IPV6 servers.
        Do not specify `None` with port=0 (see
        `lsst.ts.tcpip.OneClientServer` for details).
    initial_state : `lsst.ts.xml.enums.MTHexapod.ControllerState` (optional)
        Initial state of mock controller.

    Notes
    -----
    To start a mock controller:

        ctrl = MockController(...)
        await ctrl.connect_task

    To stop the server:

        await ctrl.stop()
    """

    # Interval between telemetry messages (seconds)
    telemetry_interval = 0.1

    def __init__(
        self,
        log: logging.Logger,
        CommandCode: typing.Callable[[IntEnum], IntEnum],
        extra_commands: dict[typing.Any, typing.Callable],
        config: ctypes.Structure,
        telemetry: ctypes.Structure,
        port: int,
        host: str | None = tcpip.LOCALHOST_IPV4,
        initial_state: IntEnum = ControllerState.STANDBY,
    ) -> None:
        self.CommandCode = CommandCode
        self.config = config
        self.telemetry = telemetry

        # Dict of command key: command
        self.command_table = {
            (CommandCode.SET_STATE, enums.SetStateParam.ENABLE): self.do_enable,  # type: ignore[attr-defined]
            (
                CommandCode.SET_STATE,  # type: ignore[attr-defined]
                enums.SetStateParam.STANDBY,
            ): self.do_standby,
            (
                CommandCode.SET_STATE,  # type: ignore[attr-defined]
                enums.SetStateParam.CLEAR_ERROR,
            ): self.do_clear_error,
            CommandCode.ENABLE_DRIVES: self.do_enable_drives,  # type: ignore[attr-defined]
        }
        self.command_table.update(extra_commands)

        # A dictionary of frame ID: header for command status,
        # telemetry and config data. Keeping separate headers for each
        # allows updating just the relevant fields, rather than creating a new
        # header insteance for each telemetry and config message.
        self.headers = dict()
        for frame_id in enums.FrameId:
            header = structs.Header()
            header.frame_id = frame_id
            self.headers[frame_id] = header

        super().__init__(
            name="MockController",
            host=host,
            port=port,
            log=log,
            connect_callback=self.connect_callback,
        )
        self.set_state(initial_state)

        self.telemetry_loop_task = utils.make_done_future()

    @property
    def state(self) -> int:
        return self.telemetry.state

    @property
    def enabled_substate(self) -> int:
        return self.telemetry.enabled_substate

    def assert_stationary(self) -> None:
        self.assert_state(
            ControllerState.ENABLED,
            enabled_substate=EnabledSubstate.STATIONARY,
        )

    def get_command_key(self, command: structs.Command) -> typing.Any:
        """Return the key to command_table."""
        if command.code in (
            self.CommandCode.SET_STATE,  # type: ignore[attr-defined]
            self.CommandCode.SET_ENABLED_SUBSTATE,  # type: ignore[attr-defined]
        ):
            return (command.code, int(command.param1))  # type: ignore[attr-defined]
        return command.code

    def assert_state(
        self,
        state: int,
        enabled_substate: int | None = None,
    ) -> None:
        """Check the state and, optionally, the substate.

        Parameters
        ----------
        state : int
            Required state.
        enabled_substate : int or None, optional
            Required enabled substate, or None to not check.

        Raises
        ------
        CommandError
            If the state is not as expected.
        """
        if self.state != state:
            raise CommandError(f"state={self.state!r}; must be {state!r} for this command.")
        if enabled_substate is not None and self.enabled_substate != enabled_substate:
            raise CommandError(
                f"enabled_substate={self.enabled_substate!r}; must be {enabled_substate!r} for this command."
            )

    async def do_enable_drives(self, command: structs.Command) -> None:
        self.config.drives_enabled = bool(command.param1)
        await self.write_config()

    async def do_enable(self, command: structs.Command) -> None:
        self.assert_state(ControllerState.STANDBY)
        self.set_state(ControllerState.ENABLED)

    async def do_standby(self, command: structs.Command) -> None:
        self.assert_state(ControllerState.ENABLED)
        self.set_state(ControllerState.STANDBY)

    async def do_clear_error(self, command: structs.Command) -> None:
        # The real low-level controller accepts this command if the
        # initial state is FAULT or STANDBY. Think of the command as
        # "clear error if there is one, and if it can be cleared".
        if self.state not in (
            ControllerState.FAULT,
            ControllerState.STANDBY,
        ):
            raise CommandError(f"state={self.state!r}; must be FAULT or STANDBY for this command.")
        self.set_state(ControllerState.STANDBY)

    async def run_command(self, command: structs.Command) -> float | None:
        """Run a command and wait for the reply.

        Parameters
        ----------
        command : `Command`
            The command to run.
            This method sets the commander and counter fields.

        Returns
        -------
        duration : `float` or None
            Estimated duration (seconds) until the command is finished.
            0 if the command is already done or almost already done.

        Raises
        ------
        CommandError
            If the command fails.
        """
        self.log.debug(
            "run_command: "
            f"counter={command.counter}; "
            f"command={self.CommandCode(command.code)!r}; "
            f"param1={command.param1}; "
            f"param2={command.param2}; "
            f"param3={command.param3}; "
            f"param4={command.param4}; "
            f"param5={command.param5}; "
            f"param6={command.param6}"
        )
        key = self.get_command_key(command)
        cmd_method = self.command_table.get(key, None)
        if cmd_method is None:
            raise CommandError(f"Unrecognized command code {command.code}; param1={command.param1}...")
            return

        duration = await cmd_method(command)  # type: ignore[arg-type, func-returns-value]
        await self.end_run_command(command=command, cmd_method=cmd_method)  # type: ignore[arg-type]

        return duration

    @abc.abstractmethod
    async def end_run_command(self, command: structs.Command, cmd_method: typing.Coroutine) -> None:
        """Called when run_command is done.

        Can be used to clear the set position.
        """
        raise NotImplementedError()

    def set_state(self, state: IntEnum) -> None:
        """Set the current state and substates.

        Parameters
        ----------
        state : `lsst.ts.xml.enums.MTHexapod.ControllerState` or `int`
            New state.

        Notes
        -----
        Sets the substates as follows:

        * `lsst.ts.xml.enums.MTHexapod.EnabledSubstate.STATIONARY`
          if state == `lsst.ts.xml.enums.MTHexapod.ControllerState.ENABLED`
        """
        self.telemetry.state = ControllerState(state)
        self.telemetry.enabled_substate = (
            EnabledSubstate.STATIONARY if self.telemetry.state == ControllerState.ENABLED else 0
        )
        self.log.debug(
            f"set_state: state={ControllerState(self.telemetry.state)!r}; "
            f"enabled_substate={EnabledSubstate(self.telemetry.enabled_substate)}"
        )

    @abc.abstractmethod
    async def update_telemetry(self, curr_tai: float) -> None:
        """Update self.client.telemetry.

        Parameters
        ----------
        curr_tai : `float`
            Time at which to compute telemetry (TAI, unix seconds).
            This is the time in the header, which is (approximately)
            the current time.
        """
        raise NotImplementedError()

    async def connect_callback(self, server: tcpip.OneClientReadLoopServer) -> None:
        """Called when the server connection state changes.

        If connected: start the command and telemetry loops.
        If not connected: stop the command and telemetry loops.
        """
        self.telemetry_loop_task.cancel()
        if self.connected:
            self.telemetry_loop_task = asyncio.create_task(self.telemetry_loop())

    async def read_and_dispatch(self) -> None:
        """Read and execute one command."""
        command = structs.Command()
        await self.read_into(command)
        try:
            duration = await self.run_command(command)
        except CommandError as e:
            await self.write_command_status(
                counter=command.counter,
                status=enums.CommandStatusCode.NO_ACK,
                reason=e.args[0],
            )
        except Exception as e:
            self.log.exception("Command failed (without raising CommandError)")
            await self.write_command_status(
                counter=command.counter,
                status=enums.CommandStatusCode.NO_ACK,
                reason=str(e),
            )
        else:
            if duration is None:
                duration = 0
            await self.write_command_status(
                counter=command.counter,
                status=enums.CommandStatusCode.ACK,
                duration=duration,
            )

    async def close_client(self, **kwargs: dict[str, typing.Any]) -> None:
        """Close the connected client (if any) and stop background tasks."""
        self.telemetry_loop_task.cancel()
        await super().close_client(**kwargs)

    async def telemetry_loop(self) -> None:
        """Write configuration once, then telemetry at regular intervals."""
        self.log.info("telemetry_loop begins")
        try:
            if self.connected:
                await self.write_config()
            while self.connected:
                header, curr_tai = self.update_and_get_header(enums.FrameId.TELEMETRY)
                await self.update_telemetry(curr_tai=curr_tai)
                await self.write_from(header, self.telemetry)
                await asyncio.sleep(self.telemetry_interval)
            self.log.info("Socket disconnected")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.log.exception("telemetry_loop failed")

    def update_and_get_header(self, frame_id: enums.FrameId) -> tuple[structs.Header, float]:
        """Update the config or telemetry header and return it and the time.

        Call this prior to writing configuration or telemetry.

        Parameters
        ----------
        frame_id : `FrameId`
            Frame ID of header to write.

        Returns
        -------
        header : `structs.Header`
            The header.
        curr_tai : `float`
            Current time in header timestamp (TAI, unix seconds).
        """
        header = self.headers[frame_id]
        curr_tai = utils.current_tai()
        tai_frac, tai_sec = math.modf(curr_tai)
        header.tai_sec = int(tai_sec)
        header.tai_nsec = int(tai_frac * 1e9)
        return header, curr_tai

    async def write_config(self) -> None:
        """Write the current configuration.

        Raises
        ------
        RuntimeError
            If not connected.
        """
        header, curr_tai = self.update_and_get_header(enums.FrameId.CONFIG)
        await self.write_from(header, self.config)

    async def write_command_status(
        self,
        counter: int,
        status: enums.CommandStatusCode,
        duration: float | None = 0.0,
        reason: str = "",
    ) -> None:
        """Write a command status.

        Parameters
        ----------
        counter : `int`
            counter field of command being acknowledged.
        status : `CommandStatusCode`
            Command status code.
        duration : `float` or `None`, optional
            Estimated duration. None is treated as 0.
        reason : `str`, optional
            Reason for failure. Should be non-blank if and only if the
            command failed.

        Raises
        ------
        ConnectionError
            If not connected.
        """
        if duration is None:
            duration = 0
        header, curr_tai = self.update_and_get_header(enums.FrameId.COMMAND_STATUS)
        header.counter = counter
        command_status = structs.CommandStatus(
            status=status,
            duration=duration,
            reason=reason.encode()[0 : structs.COMMAND_STATUS_REASON_LEN],
        )
        await self.write_from(header, command_status)
