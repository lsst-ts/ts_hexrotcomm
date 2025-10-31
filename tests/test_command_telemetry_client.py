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
import contextlib
import logging
import unittest

import pytest
from lsst.ts import hexrotcomm, salobj, tcpip
from lsst.ts.xml.enums.MTHexapod import ControllerState

# Standard timeout (seconds)
STD_TIMEOUT = 1

logging.basicConfig()


class CommandTelemetryClientTestCase(unittest.IsolatedAsyncioTestCase):
    """Test CommandTelemetryClient, SimpleMockController, and thus
    BaseMockController.
    """

    def setUp(self) -> None:
        # client = None  # set by make_client

        # Queue of connected, filled by the self.client_connect_callback
        self.client_connect_queue: asyncio.Queue = asyncio.Queue()

        # Queue of config filled by the self.config_callback
        self.config_list: list = []

        # List of telemetry, filled by the CommandTelemetryClient's
        # telemetry_callback. This is a list (not a queue like
        # client_connect_queue and config_list)
        # because we almost always want the latest value
        self.telemetry_list: list = []

        # If True then connected_callback, command_callback and
        # telemetry_callback all raise RuntimeError *after* adding
        # their argument to the appropriate queue.
        self.callbacks_raise = False

        self.log = logging.getLogger()
        self.log.setLevel(logging.INFO)

    @contextlib.asynccontextmanager
    async def make_mock_controller(self) -> hexrotcomm.SimpleMockController:
        """Make a mock controller and wait for it to connect.

        Sets the following attributes:

        * self.initial_min_position
        * self.initial_max_position
        * self.initial_max_velocity
        * self.initial_cmd_position
        """
        mock_ctrl = hexrotcomm.SimpleMockController(
            log=self.log,
            port=0,
            initial_state=ControllerState.ENABLED,
        )
        await mock_ctrl.start_task
        self.initial_min_position = mock_ctrl.config.min_position
        self.initial_max_position = mock_ctrl.config.max_position
        self.initial_max_velocity = mock_ctrl.config.max_velocity
        self.initial_cmd_position = mock_ctrl.telemetry.cmd_position
        try:
            yield mock_ctrl
        finally:
            await mock_ctrl.close()

    @contextlib.asynccontextmanager
    async def make_client(
        self, mock_ctrl: hexrotcomm.SimpleMockController
    ) -> hexrotcomm.CommandTelemetryClient:
        """Make a CommandTelemetryClient and wait for it to connect.

        Parameters
        ----------
        mock_ctrl : `SimpleMockController`
            Simple mock controller, as constructed by make_mock_controller.
        """
        client = hexrotcomm.CommandTelemetryClient(
            log=mock_ctrl.log,
            ConfigClass=hexrotcomm.SimpleConfig,
            TelemetryClass=hexrotcomm.SimpleTelemetry,
            host=tcpip.LOCALHOST_IPV4,
            port=mock_ctrl.port,
            connect_callback=self.client_connect_callback,
            config_callback=self.config_callback,
            telemetry_callback=self.telemetry_callback,
        )
        await asyncio.wait_for(client.start_task, timeout=STD_TIMEOUT)
        await self.assert_next_connected(True)
        print(f"client started; port={mock_ctrl.port}")
        try:
            yield client
        finally:
            await client.close()

    async def client_connect_callback(self, server: tcpip.OneClientReadLoopServer) -> None:
        self.client_connect_queue.put_nowait(server.connected)
        if self.callbacks_raise:
            raise RuntimeError("connect_callback raising because self.callbacks_raise is true")

    async def config_callback(self, server: tcpip.OneClientReadLoopServer) -> None:
        self.config_list.append(server.config)
        if self.callbacks_raise:
            raise RuntimeError("config_callback raising because self.callbacks_raise is true")

    async def telemetry_callback(self, server: tcpip.OneClientReadLoopServer) -> None:
        self.telemetry_list.append(server.telemetry)
        if self.callbacks_raise:
            raise RuntimeError("telemetry_callback raising because self.callbacks_raise is true")

    async def assert_next_connected(self, connected: bool, timeout: float = STD_TIMEOUT) -> None:
        """Assert results of next connect_callback.

        Parameters
        ----------
        connected : `bool`
            Should we be connected?
        timeout : `float`
            Time to wait for connect_callback (seconds).
        """
        is_connected = await asyncio.wait_for(self.client_connect_queue.get(), timeout=timeout)
        assert connected == is_connected

    async def test_constructor_errors(self) -> None:
        good_callbacks = dict(
            config_callback=self.config_callback,
            telemetry_callback=self.telemetry_callback,
            connect_callback=self.client_connect_callback,
        )

        def non_coro_callback() -> None:
            pass

        async with self.make_mock_controller() as mock_ctrl:
            for key in good_callbacks:
                bad_callbacks = good_callbacks.copy()
                bad_callbacks[key] = non_coro_callback  # type: ignore[assignment]
                with pytest.raises(TypeError):
                    hexrotcomm.CommandTelemetryClient(
                        log=mock_ctrl.log,
                        ConfigClass=hexrotcomm.SimpleConfig,
                        TelemetryClass=hexrotcomm.SimpleTelemetry,
                        host=tcpip.LOCALHOST_IPV4,
                        port=mock_ctrl.port,
                        **bad_callbacks,
                    )

    async def test_initial_conditions(self) -> None:
        async with self.make_mock_controller() as mock_ctrl:
            assert not mock_ctrl.connected
            async with self.make_client(mock_ctrl) as client:
                assert client.connected
                assert mock_ctrl.connected
                await asyncio.wait_for(client.configured_task, timeout=STD_TIMEOUT)
                config = client.config
                assert config.min_position == self.initial_min_position
                assert config.max_position == self.initial_max_position
                assert config.drives_enabled is False
                telemetry = await asyncio.wait_for(client.next_telemetry(), timeout=STD_TIMEOUT)
                assert telemetry.cmd_position == self.initial_cmd_position
                assert telemetry.curr_position >= self.initial_cmd_position

                # Extra calls to client.start should fail
                with pytest.raises(RuntimeError):
                    await client.start()

    async def test_client_reconnect(self) -> None:
        """Test that BaseMockController allows reconnection."""
        async with self.make_mock_controller() as mock_ctrl:
            async with self.make_client(mock_ctrl) as client:
                await client.close()
                await self.assert_next_connected(False)
                await asyncio.sleep(STD_TIMEOUT)
                assert not mock_ctrl.connected

            async with self.make_client(mock_ctrl) as client:
                assert mock_ctrl.connected

    async def test_move_command(self) -> None:
        async with self.make_mock_controller() as mock_ctrl, self.make_client(mock_ctrl) as client:
            await asyncio.wait_for(client.configured_task, timeout=STD_TIMEOUT)
            config = client.config
            assert config.min_position == self.initial_min_position
            assert config.max_position == self.initial_max_position
            telemetry = await client.next_telemetry()
            assert telemetry.cmd_position == self.initial_cmd_position

            expected_counter = -1
            for good_position in (
                self.initial_min_position,
                self.initial_max_position,
                (self.initial_min_position + self.initial_max_position) / 2,
            ):
                expected_counter += 1
                with self.subTest(good_position=good_position):
                    await self.check_move(
                        client=client,
                        cmd_position=good_position,
                        expected_counter=expected_counter,
                    )
            last_good_position = good_position

            for bad_position in (
                self.initial_min_position - 0.001,
                self.initial_max_position + 0.001,
            ):
                expected_counter += 1
                with self.subTest(bad_position=bad_position):
                    await self.check_move(
                        client=client,
                        cmd_position=bad_position,
                        expected_counter=expected_counter,
                        expected_position=last_good_position,
                        should_fail=True,
                    )

            # set position commands should not trigger configuration output.
            await asyncio.sleep(STD_TIMEOUT)
            assert len(self.config_list) == 1

    async def test_bad_frame_id(self) -> None:
        """Test that sending a header with an unknown frame ID causes
        the server to flush the rest of the message and continue.
        """
        async with self.make_mock_controller() as mock_ctrl, self.make_client(mock_ctrl):
            # Stop the telemetry loop and clear telemetry_list
            mock_ctrl.telemetry_loop_task.cancel()
            # give the task time to finish; probably not needed
            await asyncio.sleep(0.01)
            self.telemetry_list = []

            # Fill a telemetry struct with arbitrary data.
            telemetry = hexrotcomm.SimpleTelemetry(
                application_status=5,
                state=1,
                enabled_substate=2,
                curr_position=6.3,
                cmd_position=-15.4,
            )

            # Write a header with invalid frame ID and telemetry data.
            # The bad header should trigger an error log message
            # and the data should be flushed.
            bad_frame_id = 1025
            bad_header = hexrotcomm.Header()
            bad_header.frame_id = bad_frame_id
            with self.assertLogs(level=logging.ERROR):
                await mock_ctrl.write_from(bad_header)
                await mock_ctrl.write_from(telemetry)
                # Give the reader time to read and deal with the message.
                await asyncio.sleep(STD_TIMEOUT)
            assert len(self.telemetry_list) == 0

            # Write a good header and telemetry and test that they are read.
            good_header = hexrotcomm.Header()
            good_header.frame_id = hexrotcomm.FrameId.TELEMETRY
            await mock_ctrl.write_from(good_header)
            await mock_ctrl.write_from(telemetry)
            # Give the reader time to read and deal with the message.
            await asyncio.sleep(STD_TIMEOUT)
            assert len(self.telemetry_list) == 1
            read_telemetry = self.telemetry_list[0]
            for name in (
                "application_status",
                "state",
                "enabled_substate",
                "curr_position",
                "cmd_position",
            ):
                assert getattr(read_telemetry, name) == getattr(telemetry, name), name

    async def test_run_command_errors(self) -> None:
        """Test expected failures in BaseMockController.run_command."""
        async with self.make_mock_controller() as mock_ctrl, self.make_client(mock_ctrl) as client:
            assert client.connected

            command = hexrotcomm.Command()
            command.code = hexrotcomm.SimpleCommandCode.MOVE
            command.param1 = 0

            # Should fail if not an instance of Command
            with pytest.raises(ValueError):
                await client.run_command("not a command")

            # The client should still be connected
            assert client.connected

            # Should fail if command client is not connected
            await client.close()
            assert not client.connected
            with pytest.raises(ConnectionError):
                await client.run_command(command)

    async def test_failed_callbacks(self) -> None:
        """Check that the server gracefully handles callback functions
        that raise an exception.
        """
        self.callbacks_raise = True
        async with self.make_mock_controller() as mock_ctrl, self.make_client(mock_ctrl) as client:
            with pytest.raises(RuntimeError):
                await asyncio.wait_for(client.configured_task, timeout=STD_TIMEOUT)
            config = client.config
            assert config.min_position == self.initial_min_position
            assert config.max_position == self.initial_max_position
            assert len(self.config_list) == 1
            await asyncio.wait_for(client.next_telemetry(), timeout=STD_TIMEOUT)
            assert len(self.telemetry_list) >= 1
            assert client.connected

    async def test_truncate_command_status_reason(self) -> None:
        """Test that a too-long command status reason is truncated."""
        async with (
            self.make_mock_controller() as mock_ctrl,
            tcpip.Client(host=mock_ctrl.host, port=mock_ctrl.port, log=mock_ctrl.log) as client,
        ):
            await asyncio.wait_for(mock_ctrl.connected_task, timeout=STD_TIMEOUT)
            reason_len = hexrotcomm.CommandStatus.reason.size
            assert reason_len > 0
            command_status = hexrotcomm.CommandStatus()
            counter = 45
            status = hexrotcomm.CommandStatusCode.ACK
            duration = 3.14
            too_long_reason = "ab" * reason_len
            too_long_reason_bytes = too_long_reason.encode()
            await mock_ctrl.write_command_status(
                counter=counter,
                status=status,
                duration=duration,
                reason=too_long_reason,
            )

            header, command_status = await asyncio.wait_for(
                self.next_command_status(client), timeout=STD_TIMEOUT
            )
            assert header.counter == counter
            assert command_status.status == status
            assert command_status.duration == duration
            assert len(command_status.reason) < len(too_long_reason_bytes)
            assert command_status.reason == too_long_reason_bytes[0:reason_len]

    async def next_command_status(
        self, client: tcpip.Client
    ) -> tuple[hexrotcomm.Header, hexrotcomm.CommandStatus]:
        """Read next command status, ignoring config and telemetry.

        Parameters
        ----------
        client : `tcpip.Client`
            TCP/IP client.

        Returns
        -------
        header_cmdstatus : tuple[hexrotcomm.Header, hexrotcomm.CommandStatus]
            Header and command status.
        """
        header = hexrotcomm.Header()
        command_status = hexrotcomm.CommandStatus()
        config = hexrotcomm.SimpleConfig()
        telemetry = hexrotcomm.SimpleTelemetry()
        while True:
            await client.read_into(header)
            if header.frame_id == hexrotcomm.FrameId.COMMAND_STATUS:
                await client.read_into(command_status)
                return header, command_status
            elif header.frame_id == hexrotcomm.FrameId.CONFIG:
                await client.read_into(config)
            elif header.frame_id == hexrotcomm.FrameId.TELEMETRY:
                await client.read_into(telemetry)
            else:
                raise RuntimeError(f"Unrecognized frame_id: {header.frame_id}")

    async def check_move(
        self,
        client: tcpip.Client,
        cmd_position: float,
        expected_counter: int,
        expected_position: float | None = None,
        should_fail: bool = False,
    ) -> None:
        """Command a position and check the result.

        If the commanded position is in bounds then the telemetry
        should update to match. If not, then the command should be
        ignored and the reported position will not change.

        Parameters
        ----------
        cmd_position : `float`
            Commanded position.
        expected_position : `float` (optional)
            Position expected from telemetry. If None then use ``cmd_position``
        """
        if expected_position is None:
            expected_position = cmd_position

        command = hexrotcomm.Command()
        command.code = hexrotcomm.SimpleCommandCode.MOVE
        command.param1 = cmd_position
        if should_fail:
            with pytest.raises(salobj.ExpectedError):
                await client.run_command(command)
        else:
            await client.run_command(command)
        assert command.commander == command.COMMANDER
        assert command.counter == expected_counter

        telemetry = await client.next_telemetry()
        assert telemetry.cmd_position == expected_position
