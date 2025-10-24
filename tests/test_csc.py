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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
import asyncio
import pathlib
import unittest
import unittest.mock

import pytest
from lsst.ts import hexrotcomm, salobj
from lsst.ts.xml.enums.MTHexapod import (
    ApplicationStatus,
    ControllerState,
    EnabledSubstate,
    ErrorCode,
)

STD_TIMEOUT = 5  # timeout for command ack

TEST_CONFIG_DIR = pathlib.Path(__file__).parent / "data" / "config"


class TestSimpleCsc(hexrotcomm.BaseCscTestCase, unittest.IsolatedAsyncioTestCase):
    def basic_make_csc(
        self,
        config_dir: str | pathlib.Path,
        initial_state: salobj.State,
        simulation_mode: int,
    ) -> hexrotcomm.SimpleCsc:
        return hexrotcomm.SimpleCsc(
            initial_state=initial_state,
            simulation_mode=simulation_mode,
            config_dir=config_dir,
        )

    async def test_constructor_errors(self) -> None:
        for bad_initial_state in (0, salobj.State.OFFLINE, max(salobj.State) + 1):
            with pytest.raises(ValueError):
                hexrotcomm.SimpleCsc(
                    initial_state=bad_initial_state,
                    config_dir=TEST_CONFIG_DIR,
                    simulation_mode=1,
                )

        for bad_simulation_mode in (-1, 0, 2):
            with pytest.raises(ValueError):
                hexrotcomm.SimpleCsc(
                    initial_state=salobj.State.STANDBY,
                    config_dir=TEST_CONFIG_DIR,
                    simulation_mode=bad_simulation_mode,
                )

        with pytest.raises(ValueError):
            hexrotcomm.SimpleCsc(
                initial_state=salobj.State.STANDBY,
                simulation_mode=1,
                config_dir="no_such_directory",
            )

        # When not simulating the only valid initial state is STANDBY
        for bad_initial_state in salobj.State:
            if bad_initial_state == salobj.State.STANDBY:
                continue
            with pytest.raises(ValueError):
                hexrotcomm.SimpleCsc(
                    initial_state=bad_initial_state,
                    config_dir=TEST_CONFIG_DIR,
                    simulation_mode=0,
                )

    async def test_invalid_config(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            simulation_mode=1,
            config_dir=TEST_CONFIG_DIR,
        ):
            # Try config files with invalid data.
            # The command should fail and the summary state remain in STANDBY.
            for bad_config_path in TEST_CONFIG_DIR.glob("bad_*.yaml"):
                bad_config_name = bad_config_path.name
                with self.subTest(bad_config_name=bad_config_name):
                    with salobj.assertRaisesAckError():
                        await self.remote.cmd_start.set_start(
                            configurationOverride=bad_config_name, timeout=STD_TIMEOUT
                        )
                    assert self.csc.summary_state == salobj.State.STANDBY

            # Now try a valid config
            await self.remote.cmd_start.set_start(configurationOverride="", timeout=STD_TIMEOUT)
            assert self.csc.summary_state == salobj.State.DISABLED

    async def test_controller_fault(self) -> None:
        """Controller going to fault should send CSC to fault, error code 1"""
        async with self.make_csc(
            initial_state=salobj.State.ENABLED,
            simulation_mode=1,
            config_dir=TEST_CONFIG_DIR,
        ):
            await self.assert_next_sample(
                topic=self.remote.evt_controllerState,
                controllerState=ControllerState.ENABLED,
                enabledSubstate=EnabledSubstate.STATIONARY,
            )
            await self.assert_next_summary_state(salobj.State.ENABLED)
            await self.assert_next_sample(topic=self.remote.evt_errorCode, errorCode=0)

            self.csc.mock_ctrl.set_state(ControllerState.FAULT)
            await self.assert_next_sample(
                topic=self.remote.evt_controllerState,
                controllerState=ControllerState.FAULT,
            )
            await self.assert_next_summary_state(salobj.State.FAULT)
            await self.assert_next_sample(
                topic=self.remote.evt_errorCode, errorCode=ErrorCode.CONTROLLER_FAULT
            )

    async def test_cannot_connect(self) -> None:
        """Being unable to connect should send CSC to fault state.

        The error code should be ErrorCode.CONNECTION_LOST
        """
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            simulation_mode=1,
            config_dir=TEST_CONFIG_DIR,
        ):
            await self.assert_next_summary_state(salobj.State.STANDBY)
            await self.assert_next_sample(topic=self.remote.evt_errorCode, errorCode=0)

            # Tell the CSC not to make a mock controller,
            # so it will fail to connect to the low-level controller.
            self.csc.allow_mock_controller = False

            with salobj.assertRaisesAckError():
                await self.remote.cmd_start.start(timeout=STD_TIMEOUT)
            await self.assert_next_summary_state(salobj.State.FAULT)
            await self.assert_next_sample(
                topic=self.remote.evt_errorCode, errorCode=ErrorCode.CONNECTION_LOST
            )

    async def test_no_config(self) -> None:
        short_config_timeout = 1
        with (
            unittest.mock.patch("lsst.ts.hexrotcomm.base_csc.CONFIG_TIMEOUT", short_config_timeout),
            unittest.mock.patch("lsst.ts.hexrotcomm.simple_mock_controller.ENABLE_CONFIG", False),
        ):
            async with self.make_csc(
                initial_state=salobj.State.STANDBY,
                simulation_mode=1,
                config_dir=TEST_CONFIG_DIR,
            ):
                await self.assert_next_summary_state(salobj.State.STANDBY)
                await self.assert_next_sample(topic=self.remote.evt_errorCode, errorCode=0)

                with salobj.assertRaisesAckError(ack=salobj.SalRetCode.CMD_FAILED):
                    await self.remote.cmd_start.start(timeout=STD_TIMEOUT + short_config_timeout)
                await self.assert_next_summary_state(salobj.State.FAULT)
                data = await self.assert_next_sample(
                    topic=self.remote.evt_errorCode,
                    errorCode=ErrorCode.NO_CONFIG,
                    traceback="",
                )
                assert "Timed out" in data.errorReport

    async def test_lose_connection(self) -> None:
        """Losing the connection should send CSC to fault state.

        The error code should be ErrorCode.CONNECTION_LOST
        """
        async with self.make_csc(
            initial_state=salobj.State.ENABLED,
            simulation_mode=1,
            config_dir=TEST_CONFIG_DIR,
        ):
            assert self.csc.client.should_be_connected
            await self.assert_next_sample(
                topic=self.remote.evt_controllerState,
                controllerState=ControllerState.ENABLED,
                enabledSubstate=EnabledSubstate.STATIONARY,
            )
            await self.assert_next_summary_state(salobj.State.ENABLED)
            await self.assert_next_sample(topic=self.remote.evt_errorCode, errorCode=0)

            assert self.csc.client.should_be_connected
            await self.csc.mock_ctrl.close_client()
            await self.assert_next_summary_state(salobj.State.FAULT)
            await self.assert_next_sample(
                topic=self.remote.evt_errorCode, errorCode=ErrorCode.CONNECTION_LOST
            )

            # Test recovery
            await self.remote.cmd_standby.start(timeout=STD_TIMEOUT)
            await self.assert_next_sample(topic=self.remote.evt_errorCode, errorCode=0)

    async def test_eui_takes_control(self) -> None:
        """If the EUI takes control this should disable the CSC"""
        async with self.make_csc(
            initial_state=salobj.State.ENABLED,
            simulation_mode=1,
            config_dir=TEST_CONFIG_DIR,
        ):
            await self.assert_next_sample(
                topic=self.remote.evt_controllerState,
                controllerState=ControllerState.ENABLED,
                enabledSubstate=EnabledSubstate.STATIONARY,
            )
            await self.assert_next_summary_state(salobj.State.ENABLED)
            await self.assert_next_sample(
                topic=self.remote.evt_commandableByDDS,
                state=True,
            )

            # Clear the DDS_COMMAND_SOURCE flag
            self.csc.mock_ctrl.telemetry.application_status &= ~ApplicationStatus.DDS_COMMAND_SOURCE
            await self.assert_next_sample(
                topic=self.remote.evt_commandableByDDS,
                state=False,
            )
            await self.assert_next_summary_state(salobj.State.DISABLED)

    async def move_sequentially(self, *positions: list[float], delay: float | None = None) -> None:
        """Move sequentially to different positions, in order to test
        `BaseCsc.run_multiple_commands`.

        Warning: assumes that the CSC is enabled and the positions
        are in bounds.

        Parameters
        ----------
        positions : `List` [`double`]
            Positions to move to, in order (deg).
        delay : `float` (optional)
            Delay between commands (sec); or no delay if `None`.
            Only intended for unit testing.
        """
        commands = []
        for position in positions:
            command = self.csc.make_command(code=hexrotcomm.SimpleCommandCode.MOVE, param1=position)
            commands.append(command)
        await self.csc.run_multiple_commands(*commands, delay=delay)

    async def test_move(self) -> None:
        """Test the move command."""
        destination = 2  # a small move so the test runs quickly
        async with self.make_csc(
            initial_state=salobj.State.ENABLED,
            simulation_mode=1,
            config_dir=TEST_CONFIG_DIR,
        ):
            await self.assert_next_summary_state(salobj.State.ENABLED)
            await self.assert_next_sample(
                topic=self.remote.evt_controllerState,
                controllerState=ControllerState.ENABLED,
            )
            data = await self.remote.tel_rotation.next(flush=True, timeout=STD_TIMEOUT)
            assert data.demandPosition == pytest.approx(0)
            await self.remote.cmd_move.set_start(position=destination, timeout=STD_TIMEOUT)
            data = await self.remote.tel_rotation.next(flush=True, timeout=STD_TIMEOUT)
            assert data.demandPosition == pytest.approx(destination)

    async def test_run_multiple_commands(self) -> None:
        """Test BaseCsc.run_multiple_commands."""
        target_positions = (1, 2, 3)  # Small moves so the test runs quickly
        async with self.make_csc(
            initial_state=salobj.State.ENABLED,
            simulation_mode=1,
            config_dir=TEST_CONFIG_DIR,
        ):
            await self.assert_next_sample(
                topic=self.remote.evt_controllerState,
                controllerState=ControllerState.ENABLED,
            )
            telemetry_delay = self.csc.mock_ctrl.telemetry_interval * 3

            # Record demand positions from the `rotation` telemetry topic.
            demand_positions = []

            async def rotation_callback(data: salobj.BaseMsgType) -> None:
                if data.demandPosition not in demand_positions:
                    demand_positions.append(data.demandPosition)

            self.remote.tel_rotation.callback = rotation_callback

            # Wait for initial telemetry.
            await asyncio.sleep(telemetry_delay)

            # Start moving to the specified positions
            task1 = asyncio.ensure_future(
                self.move_sequentially(*target_positions, delay=telemetry_delay)  # type: ignore[arg-type]
            )
            # Give this task a chance to start running
            await asyncio.sleep(0.01)

            # Try to move to yet another position; this should be delayed
            # until the first set of moves is finished.
            other_move = self.csc.cmd_move.DataType()
            other_move.position = 1 + max(*target_positions)
            await self.csc.do_move(other_move)

            # task1 should have finished before the do_move command.
            assert task1.done()

            # Wait for final telemetry.
            await asyncio.sleep(telemetry_delay)

            expected_positions = [0] + list(target_positions) + [other_move.position]
            assert expected_positions == demand_positions

    async def test_standard_state_transitions(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            simulation_mode=1,
            config_dir=TEST_CONFIG_DIR,
        ):
            await self.check_standard_state_transitions(enabled_commands=("move",))
