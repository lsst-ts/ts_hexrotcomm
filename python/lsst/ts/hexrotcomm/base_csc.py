# This file is part of ts_hexapod.
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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

__all__ = ["BaseCsc"]

import abc
import asyncio
import ctypes
import traceback
import types
import typing
import warnings
from enum import IntEnum
from pathlib import Path

from lsst.ts import salobj, tcpip
from lsst.ts.xml.enums.MTHexapod import ControllerState, EnabledSubstate, ErrorCode

from . import structs
from .base_mock_controller import BaseMockController
from .command_telemetry_client import CommandTelemetryClient
from .enums import SetStateParam

# Maximum number of telemetry messages to read, before deciding that
# a commanded state change failed.
MAX_STATE_CHANGE_TELEMETRY_MESSAGES = 5

# Timeout (seconds) for the first config message to arrive,
# after connecting to the low-level controller.
CONFIG_TIMEOUT = 10


def make_connect_error_info(
    prefix: str, connected: bool, connect_descr: str
) -> tuple[ErrorCode, str]:
    """Make an error code and error message for a connect error.

    Parameters
    ----------
    prefix : `str`
        Prefix for error message.
    connected : `bool`
        Was the connection safely made?
    connect_descr : `str`
        A brief description of the host and port.
    """
    if connected:
        error_code = ErrorCode.NO_CONFIG
        err_msg = f"Timed out waiting for config from {connect_descr}"
    else:
        error_code = ErrorCode.CONNECTION_LOST
        err_msg = f"Timed out connecting to {connect_descr}"
    return error_code, err_msg


class BaseCsc(salobj.ConfigurableCsc):
    """Base CSC for talking to Moog hexpod or rotator controllers.

    Parameters
    ----------
    name : `str`
        Name of SAL component.
    index : `int` or `None` (optional)
        SAL component index, or 0 or None if the component is not indexed.
        A value is required if the component is indexed.
    CommandCode : `enum`
        Command codes supported by the low-level controller.
        Must include ``SET_STATE`` and ``ENABLE_DRIVES``, the two command codes
        used by this class.
    ConfigClass : `ctypes.Structure`
        Configuration structure.
    TelemetryClass : `ctypes.Structure`
        Telemetry structure.
    config_schema : `dict` or None, optional
        Configuration schema, as a dict in jsonschema format.
    config_dir : `str`, optional
        Directory of configuration files, or None for the standard
        configuration directory (obtained from `_get_default_config_dir`).
        This is provided for unit testing.
    initial_state : `lsst.ts.salobj.State` or `int` (optional)
        The initial state of the CSC.
    override : `str`, optional
        Configuration override file to apply if ``initial_state`` is
        `State.DISABLED` or `State.ENABLED`.
    simulation_mode : `int` (optional)
        Simulation mode. Allowed values:

        * 0: regular operation.
        * 1: simulation: use a mock low level controller.

    extra_commands : `set` [`str`]
        List of commands that can be defined in the CSC but be missing
        from the interface.

    Notes
    -----
    **Error Codes**

    * `ErrorCode.CONTROLLER_FAULT`:
      The low-level controller went to fault state.
    * `ErrorCode.CONNECTION_LOST`:
      Lost connection to the low-level controller.

    Subclasses may add additional error codes.

    **Configuration**

    The configuration for subclasses must include the following fields,
    or, for ``host`` and ``port``, the subclass may override the
    `host` and `port` properties (needed for MTHexapod):

    * host (string):
        TCP/IP host address of low-level controller.
    * port (integer):
        TCP/IP port of low-level controller.
    * connection_timeout (number):
        Time limit for connection to the low-level controller

    Both host and port are ignored in simulation mode; the host is
    `lsst.ts.tcpip.LOCALHOST_IPV4` and the ports are automatically assigned.
    """

    def __init__(
        self,
        *,
        name: str,
        index: int | None,
        CommandCode: typing.Callable[[IntEnum], IntEnum],
        ConfigClass: typing.Callable[[], ctypes.Structure],
        TelemetryClass: typing.Callable[[], ctypes.Structure],
        config_schema: dict[str, typing.Any] | None = None,
        config_dir: str | Path | None = None,
        initial_state: salobj.State = salobj.State.STANDBY,
        override: str = "",
        simulation_mode: int = 0,
        extra_commands: set[str] = set(),
    ) -> None:
        if initial_state == salobj.State.OFFLINE:
            raise ValueError("initial_state = OFFLINE is no longer supported")
        self.client: CommandTelemetryClient | None = None
        self.CommandCode = CommandCode
        self.ConfigClass = ConfigClass
        self.TelemetryClass = TelemetryClass
        self.mock_ctrl: BaseMockController | None = None

        # Set this False to simulate failing a connection to the low-level
        # controller, by not starting the mock controller.
        # Ignored unless in simulation mode.
        self.allow_mock_controller = True

        self.config: types.SimpleNamespace | None = None

        # Lock when writing a message to the low-level controller.
        # You must acquire this lock before cancelling any task
        # that may be writing to the low-level controller,
        # in order to avoid writing an incomplete message
        # and leaving data in the write buffer.
        self.write_lock = asyncio.Lock()

        # Lock when writing one command or sequences of commands to the
        # low-level controller. The low-level controllers require sequences
        # to do several things, such as move point to point (first set
        # the new position, then command the move), and this prevents
        # new commands from being issued during the sequence.
        # To avoid deadlocks: if acquiring both _command_lock and write_lock
        # then always acquire _command_lock first.
        self._command_lock = asyncio.Lock()
        super().__init__(
            name=name,
            index=index,
            config_dir=config_dir,
            config_schema=config_schema,
            initial_state=initial_state,
            override=override,
            simulation_mode=simulation_mode,
            extra_commands=extra_commands,
        )

    @staticmethod
    def get_config_pkg() -> str:
        return "ts_config_mttcs"

    @property
    def connected(self) -> bool:
        return self.client is not None and self.client.connected

    @property
    def host(self) -> str:
        """Get the TCP/IP address of the low-level controller.

        The default implementation returns ``self.config.host``.
        This is not sufficient for the hexapods, which have a different
        host for each of the two hexapods.
        """

        # Workaround the mypy check
        assert self.config is not None

        return self.config.host

    @property
    def port(self) -> int:
        """Get the port of the low-level controller.

        The default implementation returns ``self.config.port``.
        This is not sufficient for the hexapods, which have a different
        port for each of the two hexapods.
        """

        # Workaround the mypy check
        assert self.config is not None

        return self.config.port

    async def close_tasks(self) -> None:
        await super().close_tasks()
        if self.mock_ctrl is not None:
            await self.mock_ctrl.close()
        if self.client is not None:
            await self.client.close()

    async def configure(self, config: types.SimpleNamespace) -> None:
        self.config = config

    @abc.abstractmethod
    def make_mock_controller(self) -> None:
        """Construct and return a mock controller."""
        raise NotImplementedError()

    def assert_commandable(self) -> None:
        """Assert that CSC is connected to the low-level controller
        and can command it.
        """
        self.assert_connected()
        if not self.evt_commandableByDDS.data.state:
            raise salobj.ExpectedError(
                "Controller has CSC commands disabled; "
                "use the EUI to enable CSC commands"
            )

    def assert_connected(self) -> None:
        """Assert that the CSC is connected to the low-level controller.

        Raises
        ------
        lsst.ts.salobj.ExpectedError
            If one or both streams is disconnected.
        """
        if not self.connected:
            raise salobj.ExpectedError("Not connected to the low-level controller.")

    def assert_enabled(self) -> None:
        """Assert that the CSC is enabled.

        First check that CSC can command the low-level controller.
        """
        self.assert_summary_state(salobj.State.ENABLED)

    def assert_enabled_substate(self, substate: IntEnum) -> None:
        """Assert that the CSC is enabled and that the low-level controller
        is in the specified enabled substate.

        First check that CSC can command the low-level controller.

        Parameters
        ----------
        substate : `EnabledSubstate`
            Substate of low-level controller.
        """
        substate = EnabledSubstate(substate)
        self.assert_summary_state(salobj.State.ENABLED)

        # Workaround the mypy check
        assert self.client is not None

        if self.client.telemetry.enabled_substate != substate:
            raise salobj.ExpectedError(
                "Low-level controller in substate "
                f"{self.client.telemetry.enabled_substate} "
                f"instead of {substate!r}"
            )

    def assert_summary_state(
        self, state: salobj.State, isbefore: bool | None = None
    ) -> None:
        """Assert that the current summary state is as specified.

        First check that CSC can command the low-level controller.

        Used in do_xxx methods to check that a command is allowed.

        Parameters
        ----------
        state : `lsst.ts.salobj.State`
            Expected summary state.
        isbefore : `bool`, optional
            Deprecated. The only allowed values are False
            (which raises a deprecation warning) and None.
        """
        if isbefore:
            raise ValueError(
                f"isbefore={isbefore}; this deprecated argument must be None or False"
            )
        elif isbefore is False:
            warnings.warn(f"isbefore={isbefore} is deprecated", DeprecationWarning)
        state = salobj.State(state)
        self.assert_connected()
        if self.summary_state != state:
            raise salobj.ExpectedError(
                f"Rejected: initial state is {self.summary_state!r} instead of {state!r}"
            )

    async def wait_controller_state(
        self, state: IntEnum, max_telem: int = MAX_STATE_CHANGE_TELEMETRY_MESSAGES
    ) -> None:
        """Wait for the controller state to be as specified.

        Fails if the CSC cannot command the low-level controller.

        Parameters
        ----------
        state : `ControllerState`
            Desired controller state.
        max_telem : `int`
            Maximum number of low-level telemetry messages to wait for.
        """

        # Workaround the mypy check
        assert self.client is not None

        state = ControllerState(state)
        for i in range(max_telem):
            self.assert_connected()
            await self.client.next_telemetry()
            if self.client.telemetry.state == state:
                return
        raise salobj.ExpectedError(
            f"Failed: controller state is {self.client.telemetry.state} instead of {state!r}"
        )

    def make_command(
        self,
        code: IntEnum,
        param1: float = 0.0,
        param2: float = 0.0,
        param3: float = 0.0,
        param4: float = 0.0,
        param5: float = 0.0,
        param6: float = 0.0,
    ) -> structs.Command:
        """Make a command from the command identifier and keyword arguments.

        Used to make commands for `run_multiple_commands`.

        Parameters
        ----------
        code : ``CommandCode``
            Command to run.
        param1, param2, param3, param4, param5, param6 : `double`
            Command parameters. The meaning of these parameters
            depends on the command code.

        Returns
        -------
        command : `Command`
            The command. Note that the ``counter`` field is 0;
            it is set by `CommandTelemetryClient.run_command`.
        """
        command = structs.Command()
        command.code = self.CommandCode(code)
        command.param1 = param1
        command.param2 = param2
        command.param3 = param3
        command.param4 = param4
        command.param5 = param5
        command.param6 = param6
        return command

    async def run_command(
        self,
        code: IntEnum,
        param1: float = 0.0,
        param2: float = 0.0,
        param3: float = 0.0,
        param4: float = 0.0,
        param5: float = 0.0,
        param6: float = 0.0,
    ) -> None:
        """Run one command.

        Parameters
        ----------
        code : ``CommandCode``
            Command to run.
        param1, param2, param3, param4, param5, param6 : `double`
            Command parameters. The meaning of these parameters
            depends on the command code.
        """
        async with self._command_lock:
            command = self.make_command(
                code,
                param1=param1,
                param2=param2,
                param3=param3,
                param4=param4,
                param5=param5,
                param6=param6,
            )
            await self.basic_run_command(command)

    async def run_multiple_commands(
        self, *commands: list[structs.Command], delay: float | None = None
    ) -> None:
        """Run multiple commands, without allowing other commands to run
        between them.

        Parameters
        ----------
        commands : `List` [`Command`]
            Commands to run, as constructed by `make_command`.
        delay : `float` (optional)
            Delay between commands (sec); or no delay if `None`.
            Only intended for unit testing.
        """
        async with self._command_lock:
            for command in commands:
                await self.basic_run_command(command)  # type: ignore[arg-type]
                if delay is not None:
                    await asyncio.sleep(delay)

    async def basic_run_command(self, command: structs.Command) -> None:
        """Acquire the write_lock and run the command.

        Parameters
        ----------
        command : `Command`
            Command to run, as constructed by `make_command`.
        """

        # Workaround the mypy check
        assert self.client is not None

        async with self.write_lock:
            await self.client.run_command(command)

    async def connect_callback(self, client: CommandTelemetryClient) -> None:
        """Called when the client socket connects or disconnects.

        Parameters
        ----------
        client : `CommandTelemetryClient`
            TCP/IP client.
        """
        await self.evt_connected.set_write(connected=client.connected)
        if client.should_be_connected and not client.connected:
            await self.fault(
                code=ErrorCode.CONNECTION_LOST,
                report="Lost connection to the low-level controller",
            )

    async def begin_enable(self, data: salobj.BaseMsgType) -> None:
        # Do this before reporting that the CSC is in the enabled state,
        # to prevent basic_telemetry_callback from thinking the low-level
        # controller has gone out of ENABLED state and getting upset.
        await self.enable_controller()

    async def handle_summary_state(self) -> None:
        if self.disabled_or_enabled:
            if not self.connected:
                await self.connect()
        elif self.summary_state != salobj.State.FAULT:
            # Stay connected in FAULT if possible,
            # so users can see what's going on.
            await self.disconnect()

    async def connect(self) -> None:
        """Connect to the low-level controller.

        After starting the mock controller, if using one.
        """
        await self.disconnect()
        # Use a local variable to avoid any possibility of
        # the wrong error message due to a race condition.
        connected = False
        try:
            if self.simulation_mode != 0:
                host = tcpip.LOCALHOST_IPV4
                if self.allow_mock_controller:
                    self.mock_ctrl = self.make_mock_controller()

                    # Workaround the mypy check
                    assert self.mock_ctrl is not None

                    await self.mock_ctrl.start_task
                    port = self.mock_ctrl.port
                else:
                    self.log.warning(
                        "Not starting the mock controller because allow_mock_controller is False. "
                        "The CSC should fail to connect to the low-level controller and go to FAULT state."
                    )
                    port = self.port
            else:
                host = self.host
                port = self.port
            connect_descr = f"host={host}, port={port}"
            self.log.info(f"connect to {connect_descr}")
            self.client = CommandTelemetryClient(
                log=self.log,
                ConfigClass=self.ConfigClass,
                TelemetryClass=self.TelemetryClass,
                host=host,
                port=port,
                connect_callback=self.connect_callback,
                config_callback=self.config_callback,
                telemetry_callback=self.basic_telemetry_callback,
            )

            # Workaround the mypy check
            assert self.client is not None
            assert self.config is not None

            await asyncio.wait_for(
                self.client.start_task, timeout=self.config.connection_timeout
            )
            connected = True
            # Wait for configuration and telemetry, since we cannot safely
            # issue commands until we know both.
            await asyncio.wait_for(self.client.configured_task, timeout=CONFIG_TIMEOUT)
            await asyncio.wait_for(self.client.next_telemetry(), timeout=CONFIG_TIMEOUT)
        except asyncio.TimeoutError:
            error_code, err_msg = make_connect_error_info(
                prefix="Timed out", connected=connected, connect_descr=connect_descr
            )
            await self.fault(code=error_code, report=err_msg)
            raise salobj.ExpectedError(err_msg)
        except ConnectionRefusedError:
            err_msg = f"Connection refused by {connect_descr}"
            await self.fault(code=ErrorCode.CONNECTION_LOST, report=err_msg)
            raise salobj.ExpectedError(err_msg)
        except Exception:
            error_code, err_msg = make_connect_error_info(
                prefix="Unexpected error",
                connected=connected,
                connect_descr=connect_descr,
            )
            await self.fault(
                code=error_code, report=err_msg, traceback=traceback.format_exc()
            )
            raise

    async def disconnect(self) -> None:
        """Disconnect from the low-level controller.

        And shut down the mock controller, if using one.
        """
        if self.connected:
            try:
                # Workaround the mypy check
                assert self.client is not None

                await self.client.close()
            except Exception:
                self.log.exception("disconnect: self.client.close failed")
            self.client = None
        if self.mock_ctrl is not None:
            try:
                await self.mock_ctrl.close()
            except Exception:
                self.log.exception("disconnect: self.mock_ctrl.close failed")
            self.mock_ctrl = None

    async def enable_controller(self) -> None:
        """Enable the low-level controller.

        Raises
        ------
        lsst.ts.salobj.ExpectedError
            If the low-level controller is in fault state and the fault
            cannot be cleared. Or if a state transition command fails
            (which is unlikely).
        """
        self.assert_commandable()

        # Workaround the mypy check
        assert self.client is not None

        self.log.info(
            f"Enable low-level controller; initial state={self.client.telemetry.state}"
        )

        if self.client.telemetry.state == ControllerState.ENABLED:
            return

        if self.client.telemetry.state == ControllerState.FAULT:
            # Start by issuing the clearError command.
            self.log.info("Clearing low-level controller fault state")
            await self.run_command(
                code=self.CommandCode.SET_STATE,  # type: ignore[attr-defined]
                param1=SetStateParam.CLEAR_ERROR,
            )

        if self.client.telemetry.state != ControllerState.STANDBY:
            raise salobj.ExpectedError(
                f"Before enable: low-level controller state={self.client.telemetry.state}; "
                f"expected {ControllerState.STANDBY!r}"
            )

        # Enable the drives first
        await self._enable_drives(True)

        try:
            await self.run_command(
                code=self.CommandCode.SET_STATE,  # type: ignore[attr-defined]
                param1=SetStateParam.ENABLE,
            )
        except Exception as e:
            print(f"Low-level controller enable failed: {e!r}")
            raise

        await self.wait_controller_state(ControllerState.ENABLED)

    async def _enable_drives(self, status: bool, time: float = 1.0) -> None:
        """Enable the drives.

        Parameters
        ----------
        status : `bool`
            True if enable the drives. Otherwise, False.
        time : `float`, optional
            Sleep time in second. (the default is 1.0)
        """

        await self.run_command(
            code=self.CommandCode.ENABLE_DRIVES,  # type: ignore[attr-defined]
            param1=float(status),
        )
        await asyncio.sleep(time)

    async def begin_standby(self, data: salobj.BaseMsgType) -> None:
        try:
            await self._enable_drives(False)
        except Exception as error:
            self.log.warning(f"Ignoring the error when disabling the drives: {error}.")

    async def begin_disable(self, data: salobj.BaseMsgType) -> None:
        try:
            await self.standby_controller()

        except Exception as error:
            self.log.warning(
                f"Ignoring the error when putting the controller to STANDBY state: {error}."
            )

    async def standby_controller(self) -> None:
        """Standby the low-level controller."""

        self.assert_commandable()

        await self.run_command(
            code=self.CommandCode.SET_STATE,  # type: ignore[attr-defined]
            param1=SetStateParam.STANDBY,
        )
        await self._enable_drives(False)

    @abc.abstractmethod
    async def config_callback(self, client: CommandTelemetryClient) -> None:
        """Called when the TCP/IP controller outputs configuration.

        Parameters
        ----------
        client : `CommandTelemetryClient`
            TCP/IP client.
        """
        raise NotImplementedError()

    async def basic_telemetry_callback(self, client: CommandTelemetryClient) -> None:
        """Called when the TCP/IP controller outputs telemetry.

        Call telemetry_callback, then check the following:

        * If the low-level controller is in fault state,
          transition the CSC to FAULT state.
        * IF the low-level controller is not in enabled state
          or if the CSC has lost the ability to command the low-level
          controller, move the CSC to DISABLED state.

        Parameters
        ----------
        client : `CommandTelemetryClient`
            TCP/IP client.
        """
        try:
            await self.telemetry_callback(client)
        except Exception:
            self.log.exception("telemetry_callback failed")
        if self.summary_state != salobj.State.ENABLED:
            return

        if client.telemetry.state == ControllerState.FAULT:
            await self.fault(
                code=ErrorCode.CONTROLLER_FAULT,
                report="Low-level controller went to FAULT state",
            )
            return

        disable_conditions = []
        if not self.evt_commandableByDDS.data.state:
            disable_conditions.append("the EUI has taken control")
        if disable_conditions:
            why_str = ", ".join(disable_conditions)
            self.log.warning(f"Disabling the CSC because {why_str}")
            data = self.cmd_disable.DataType()
            asyncio.create_task(
                self._do_change_state(
                    data, "disable", [salobj.State.ENABLED], salobj.State.DISABLED
                )
            )

    @abc.abstractmethod
    async def telemetry_callback(self, client: CommandTelemetryClient) -> None:
        """Called when the TCP/IP controller outputs telemetry.

        Parameters
        ----------
        client : `CommandTelemetryClient`
            TCP/IP client.

        Notes
        -----
        This method must set the following events:

        * evt_controllerState
        * evt_commandableByDDS

        Here is a typical implementation::

            await self.evt_controllerState.set_write(
                controllerState=int(client.telemetry.state),
                enabledSubstate=int(client.telemetry.enabled_substate),
            )
            await self.evt_commandableByDDS.set_write(
                state=bool(
                    client.telemetry.application_status
                    & ApplicationStatus.DDS_COMMAND_SOURCE
                )
            )
        """
        raise NotImplementedError()
