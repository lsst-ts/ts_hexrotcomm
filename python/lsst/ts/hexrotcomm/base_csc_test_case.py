# This file is part of ts_hexrotcomm.
#
# Developed for the Vera C. Rubin Observatory Telescope and Site Systems.
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

__all__ = ["BaseCscTestCase"]

import contextlib
import pathlib
import typing

from lsst.ts import salobj
from lsst.ts.xml.enums.MTHexapod import ControllerState

# Standard timeout (sec)
# Long to avoid unnecessary timeouts on slow CI systems.
STD_TIMEOUT = 60


class BaseCscTestCase(salobj.BaseCscTestCase):
    """A variant of salobj.BaseCscTestCase that captures all but the last
    controller state in make_csc.
    """

    @contextlib.asynccontextmanager
    async def make_csc(
        self,
        initial_state: salobj.State = salobj.State.STANDBY,
        config_dir: str | pathlib.Path | None = None,
        simulation_mode: int = 0,
        log_level: int | None = None,
        timeout: float = STD_TIMEOUT,
        **kwargs: dict[str, typing.Any],
    ) -> salobj.BaseCsc:
        """Create a CSC and remote and wait for them to start.

        The csc is accessed as ``self.csc`` and the remote as ``self.remote``.

        This override reads and checks all but the last ``controllerState``
        event during startup, in addition to the ``summaryState`` event.

        Parameters
        ----------
        name : `str`
            Name of SAL component.
        initial_state : `lsst.ts.salobj.State` or `int`, optional
            The initial state of the CSC. Defaults to STANDBY.
        config_dir : `str`, optional
            Directory of configuration files, or `None` (the default)
            for the standard configuration directory (obtained from
            `ConfigureCsc._get_default_config_dir`).
        simulation_mode : `int`, optional
            Simulation mode. Defaults to 0 because not all CSCs support
            simulation. However, tests of CSCs that support simulation
            will almost certainly want to set this nonzero.
        log_level : `int` or `None`, optional
            Logging level, such as `logging.INFO`.
            If `None` then do not set the log level, leaving the default
            behavior of `SalInfo`: increase the log level to INFO.
        timeout : `float`
            Time limit for the CSC to start (seconds).
        **kwargs : `dict`
            Extra keyword arguments for `basic_make_csc`.
            For a configurable CSC this may include ``override``,
            especially if ``initial_state`` is DISABLED or ENABLED.

        Notes
        -----
        Adds a logging.StreamHandler if one is not already present.
        """
        async with super().make_csc(
            initial_state=initial_state,
            config_dir=config_dir,
            simulation_mode=simulation_mode,
            log_level=log_level,
            timeout=timeout,
            **kwargs,
        ):
            if initial_state == salobj.State.ENABLED:
                # Wait for and check the intermediate controller state,
                # so unit test code only needs to check the final state
                # (don't swallow the final state, for backwards compatibility).
                await self.assert_next_sample(
                    topic=self.remote.evt_controllerState,
                    controllerState=ControllerState.STANDBY,
                )
            yield

    async def check_bin_script(
        self, name: str, index: int | None, exe_name: str, cmdline_args: list[str] = []
    ) -> None:
        """Test running the CSC command line script.

        Parameters
        ----------
        name : `str`
            Name of SAL component, e.g. "MTRotator"
        index : `int` or `None`
            SAL index of component.
        exe_name : `str`
            Name of executable, e.g. "run_rotator.py"
        cmdline_args : `List` [`str`]
            Additional command-line arguments, such as "--simulate".
        """
        await super().check_bin_script(
            name=name,
            index=index,
            exe_name=exe_name,
            default_initial_state=salobj.State.STANDBY,
            cmdline_args=cmdline_args,
        )
