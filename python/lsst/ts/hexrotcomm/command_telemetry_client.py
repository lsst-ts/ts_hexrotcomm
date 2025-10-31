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

__all__ = ["CommandTelemetryClient"]

import asyncio
import ctypes
import inspect
import logging
import typing

from lsst.ts import salobj, tcpip, utils

from . import enums, structs

# Time limit waiting for a command status (second).
COMMAND_STATUS_TIMEOUT = 5


class CommandTelemetryClient(tcpip.Client):
    """TCP/IP Client for a Moog CSC.

    This client cannot be reconnected; once closed, you must create a new one.

    Parameters
    ----------
    log : `logging.Logger`
        Logger.
    ConfigClass : `ctypes.Structure`
        Class for configuration.
    TelemetryClass : `ctypes.Structure`
        Class for telemetry
    host : `str`
        IP address of CSC server.
    port : `int`
        Server port.
    connect_callback : coroutine
        Coroutine to call when a connection is made or dropped.
        The function receives one argument: this client.
    config_callback : coroutine
        Coroutine to call when configuration is read.
        The function receives one argument: this client.
    telemetry_callback : coroutine
        Coroutine to call when telemetry is read.
        The function receives one argument: this client.
    connect_timeout : `float`, optional
        Time limit for a connection to be made (seconds).

    Attributes
    ----------
    header : ``Header``
        The most recently read header
        (which may be for config, telemetry, or unrecognized).
    config : ``ConfigClass``
        The most recently read configuration.
        A null-constructed instance before configuration is read.
    configured_task : `asyncio.Future`
        A Future that is set to None when configuration is first read and
        processed, or to the exception if ``config_callback`` raises.
    telemetry : ``TelemetryClass``
        The most recently read telemetry.
        A null-constructed instance before telemetry is read.
    config_callback : coroutine
        The ``config_callback`` constructor argument.
    telemetry_callback : coroutine
        The ``telemetry_callback`` constructor argument.

    Plus the standard attributes of `lsst.ts.tcpip.Client`.

    Raises
    ------
    TypeError
        If any of the callbacks is not a coroutine.

    Notes
    -----
    To start a client::

        client = Client(...)
        await client.start_task

    To stop the client:

        await client.stop()
    """

    def __init__(
        self,
        *,
        log: logging.Logger,
        ConfigClass: typing.Callable[[], ctypes.Structure],
        TelemetryClass: typing.Callable[[], ctypes.Structure],
        host: str,
        port: int,
        connect_callback: tcpip.ConnectCallbackType,
        config_callback: typing.Callable[[typing.Self], typing.Coroutine],
        telemetry_callback: typing.Callable[[typing.Self], typing.Coroutine],
        connect_timeout: float = 10.0,
    ) -> None:
        for arg_name in ("connect_callback", "config_callback", "telemetry_callback"):
            arg_value = locals()[arg_name]
            if not inspect.iscoroutinefunction(arg_value):
                raise TypeError(f"{arg_name} must be a coroutine")

        self.header = structs.Header()
        self.config = ConfigClass()
        self.telemetry = TelemetryClass()
        self.config_callback = config_callback
        self.telemetry_callback = telemetry_callback
        self.connect_timeout = connect_timeout
        # Resource lock for writing a command and waiting for acknowledgement.
        self._command_lock = asyncio.Lock()

        # Hold on to the last command, in order to increment the command
        # counter with correct wraparound.
        # An index generator would also work, but this avoids duplicating
        # information about the type of the command counter field.
        # Start from -1 so that the first command has counter=0.
        self._last_command = structs.Command()
        self._last_command.commander = structs.Command.COMMANDER
        self._last_command.counter -= 1

        # Task set to None when config is first seen and handled by
        # config_callback, or the exception if config_callback raises.
        self.configured_task: asyncio.Future = asyncio.Future()

        # Task used by next_telemetry to detect when the next telemetry
        # is read.
        self._telemetry_task: asyncio.Future = asyncio.Future()

        # Task used to wait for a command acknowledgement
        self._read_command_status_task = utils.make_done_future()

        self._read_loop_task = utils.make_done_future()

        super().__init__(
            host=host,
            port=port,
            connect_callback=connect_callback,
            # No background monitoring needed, because the mock controller
            # is almost always reading, and that detects disconnection.
            monitor_connection_interval=0,
            log=log,
        )

    async def close(self) -> None:
        """Close the socket connection and cancel all tasks.

        Always safe to call.
        """
        self._read_command_status_task.cancel()
        self._read_loop_task.cancel()
        self.configured_task.cancel()
        self._telemetry_task.cancel()
        await super().close()

    async def start(self) -> None:
        """Connect to the low-level controller."""
        await super().start()
        self._read_loop_task = asyncio.create_task(self.read_loop())

    async def read_loop(self) -> None:
        """Read from the Moog controller."""
        try:
            # Number of bytes to flush if a header is not recognized.
            # The size of the largest non-header struct.
            max_flush_bytes = max(
                ctypes.sizeof(self.telemetry),
                ctypes.sizeof(self.config),
                ctypes.sizeof(structs.CommandStatus),
            )

            while self.connected:
                await self.read_into(self.header)
                if self.header.frame_id == enums.FrameId.COMMAND_STATUS:
                    command_status = structs.CommandStatus()
                    await self.read_into(command_status)
                    if self._read_command_status_task.done():
                        continue
                    if self.header.counter == self._last_command.counter:
                        self._read_command_status_task.set_result(command_status)
                    else:
                        self.log.warning(
                            "Ignoring command status for wrong command; "
                            f"read counter={self.header.counter} "
                            f"!= expected value {self._last_command.counter}"
                        )
                elif self.header.frame_id == enums.FrameId.CONFIG:
                    await self.read_into(self.config)
                    try:
                        await self.config_callback(self)
                        if not self.configured_task.done():
                            self.configured_task.set_result(None)
                    except Exception as e:
                        self.log.exception("config_callback failed.")
                        if not self.configured_task.done():
                            self.configured_task.set_exception(e)
                elif self.header.frame_id == enums.FrameId.TELEMETRY:
                    await self.read_into(self.telemetry)
                    if not self._telemetry_task.done():
                        self._telemetry_task.set_result(None)
                    try:
                        await self.telemetry_callback(self)
                    except Exception:
                        self.log.exception("telemetry_callback failed.")
                else:
                    self.log.error(
                        f"Invalid header read: unknown frame_id={self.header.frame_id}; "
                        f"flushing and continuing. Bytes: {bytes(self.header)!r}"
                    )
                    data = await self.read(max_flush_bytes)
                    self.log.info(f"Flushed {len(data)} bytes")
        except asyncio.CancelledError:
            # No need to close the connection, because the code that cancelled
            # this task is expected to do that.
            pass
        except (ConnectionError, asyncio.IncompleteReadError):
            self.log.exception("Reader unexpectedly closed.")
        except Exception:
            self.log.exception("Unexpected error in read loop.")
        await self.basic_close()

    async def next_telemetry(self) -> ctypes.Structure:
        """Wait for next telemetry."""
        if self._telemetry_task.done():
            self._telemetry_task = asyncio.Future()
        await self._telemetry_task
        return self.telemetry

    async def run_command(self, command: structs.Command, interrupt: bool = False) -> float:
        """Run a command and wait for acknowledgement.

        Parameters
        ----------
        command : `Command`
            Command to write. Its counter field will be set.
        interrupt : `bool`, optional
            Interrupt the current command, if any?
            Only use this for the stop command and similar.

        Returns
        -------
        duration : `float`
            The expected duration of the command (seconds).

        Raises
        ------
        ValueError
            If ``command`` is not an instance of `structs.Command`.
        ConnectionError
            If not connected.
        asyncio.TimeoutError
            If no acknowledgement is seen in time.
        lsst.ts.salobj.ExpectedError
            If the command fails.

        Notes
        -----
        Holds the command lock until the reply for this command is seen
        (or the time limit is exceeded).
        """
        if not isinstance(command, structs.Command):
            raise ValueError(f"command={command!r} must be an instance of structs.Command")

        async with self._command_lock:
            # Cancel the task just to be sure; it's hard to see how it
            # could be running at this point.
            self._read_command_status_task.cancel()
            self._read_command_status_task = asyncio.Future()

            command.commander = command.COMMANDER
            command.counter = self._last_command.counter + 1
            self._last_command = command
            await self.write_from(command)

            command_status = await asyncio.wait_for(
                self._read_command_status_task,
                timeout=COMMAND_STATUS_TIMEOUT,
            )
            if command_status.status == enums.CommandStatusCode.ACK:
                return command_status.duration
            elif command_status.status == enums.CommandStatusCode.NO_ACK:
                reason = command_status.reason.decode()
                raise salobj.ExpectedError(reason)
            else:
                raise salobj.ExpectedError(
                    f"Unknown command status {command_status.status}; "
                    "low-level command assumed to have failed"
                )
