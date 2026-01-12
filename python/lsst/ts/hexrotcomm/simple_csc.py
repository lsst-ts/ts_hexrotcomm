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

__all__ = ["SimpleCsc"]

from pathlib import Path

from lsst.ts import hexrotcomm, salobj, utils
from lsst.ts.xml.component_info import ComponentInfo
from lsst.ts.xml.enums.MTHexapod import ApplicationStatus, EnabledSubstate

from . import simple_mock_controller
from .command_telemetry_client import CommandTelemetryClient
from .config_schema import CONFIG_SCHEMA


class SimpleCsc(hexrotcomm.BaseCsc):
    """Simple CSC to talk to SimpleMockController.

    This is based on the MTRotator CSC but only supports a small subset
    off commands, events and telemetry. See Notes for details.
    The move command sets the cmd_position and curr_position
    telemetry fields, then the controller slowly increments curr_position.

    Parameters
    ----------
    config_dir : `str`, optional
        Directory of configuration files, or None for the standard
        configuration directory (obtained from `_get_default_config_dir`).
        This is provided for unit testing.
    initial_state : `lsst.ts.salobj.State` or `int` (optional)
        The initial state of the CSC. Ignored (other than checking
        that it is a valid value) except in simulation mode,
        because in normal operation the initial state is the current state
        of the controller. This is provided for unit testing.
    override : `str`, optional
        Configuration override file to apply if ``initial_state`` is
        `State.DISABLED` or `State.ENABLED`.
    simulation_mode : `int` (optional)
        Simulation mode. Allowed values:

        * 0: regular operation.
        * 1: simulation: use a mock low level controller.

    Notes
    -----
    **Error Codes**

    * `lsst.ts.xml.enums.MTHexapod.ErrorCode.CONTROLLER_FAULT`:
      The low-level controller went to fault state.
    * `lsst.ts.xml.enums.MTHexapod.ErrorCode.CONNECTION_LOST`:
      Lost connection to the low-level controller.

    **SAL API**

    This CSC implements a subset of the MTRotator SAL API.

    Commands beyond the generic commands:

    * move

    Events beyond the generic events:

    * commandableByDDS
    * configuration
    * connected
    * controllerState

    Telemetry:

    * rotation
    """

    valid_simulation_modes = [1]
    version = "test"

    def __init__(
        self,
        config_dir: str | Path | None = None,
        initial_state: salobj.State = salobj.State.STANDBY,
        simulation_mode: int = 1,
        override: str = "",
    ) -> None:
        # Workaround the checking of "do_" commands in upstream
        supported_command_names = [name[3:] for name in dir(self) if name.startswith("do_")]

        component_info = ComponentInfo("MTRotator", "sal")
        topic_names = [name[4:] for name in component_info.topics if name.startswith("cmd_")]
        for topic_name in topic_names:
            if topic_name not in supported_command_names:
                setattr(self, f"do_{topic_name}", self._do_nothing)

        super().__init__(
            name="MTRotator",
            index=0,
            CommandCode=simple_mock_controller.SimpleCommandCode,
            ConfigClass=simple_mock_controller.SimpleConfig,
            TelemetryClass=simple_mock_controller.SimpleTelemetry,
            config_schema=CONFIG_SCHEMA,
            config_dir=config_dir,
            initial_state=initial_state,
            override=override,
            simulation_mode=simulation_mode,
        )

    async def _do_nothing(self, data: salobj.BaseMsgType) -> None:
        raise salobj.ExpectedError("Not implemented")

    async def do_move(self, data: salobj.BaseMsgType) -> None:
        """Specify a position."""
        self.assert_enabled_substate(EnabledSubstate.STATIONARY)
        if not self.client.config.min_position <= data.position <= self.client.config.max_position:
            raise salobj.ExpectedError(
                f"position {data.position} not in range "
                f"[{self.client.config.min_position}, "
                f"{self.client.config.max_position}]"
            )
        await self.run_command(code=simple_mock_controller.SimpleCommandCode.MOVE, param1=data.position)

    async def config_callback(self, client: CommandTelemetryClient) -> None:
        """Called when the TCP/IP controller outputs configuration.

        Parameters
        ----------
        client : `CommandTelemetryClient`
            TCP/IP client.
        """
        await self.evt_configuration.set_write(
            positionAngleUpperLimit=client.config.max_position,
            velocityLimit=client.config.max_velocity,
            accelerationLimit=0,
            positionAngleLowerLimit=client.config.min_position,
            followingErrorThreshold=0,
            trackingSuccessPositionThreshold=0,
            trackingLostTimeout=0,
            drivesEnabled=client.config.drives_enabled,
        )
        await self.evt_commandableByDDS.set_write(state=True)

    async def telemetry_callback(self, client: CommandTelemetryClient) -> None:
        """Called when the TCP/IP controller outputs telemetry.

        Parameters
        ----------
        client : `CommandTelemetryClient`
            TCP/IP client.
        """
        # Strangely telemetry.state and enabled_substate
        # are all floats from the controller. But they should only have
        # integer value, so I output them as integers.
        await self.evt_controllerState.set_write(
            controllerState=int(client.telemetry.state),
            enabledSubstate=int(client.telemetry.enabled_substate),
        )
        await self.evt_commandableByDDS.set_write(
            state=bool(client.telemetry.application_status & ApplicationStatus.DDS_COMMAND_SOURCE)
        )

        await self.tel_rotation.set_write(
            demandPosition=client.telemetry.cmd_position,
            actualPosition=client.telemetry.curr_position,
            timestamp=utils.current_tai(),
        )

    def make_mock_controller(self) -> simple_mock_controller.SimpleMockController:
        return simple_mock_controller.SimpleMockController(
            log=self.log,
            port=0,
        )
