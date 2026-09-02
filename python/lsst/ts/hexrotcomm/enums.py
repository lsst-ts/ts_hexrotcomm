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

__all__ = ["CommandStatusCode", "FrameId", "SetStateParam"]

import enum


class CommandStatusCode(enum.IntEnum):
    """Possible values for CommandStatus.status.

    Called ``CmdStatus`` in the Moog controller.
    """

    ACK = 1
    NO_ACK = 2


class FrameId(enum.IntEnum):
    """Frame ID for each message type."""

    COMMAND_STATUS = 1
    TELEMETRY = 2
    CONFIG = 3


class SetStateParam(enum.IntEnum):
    """Values for ``Command.param1`` when
    ``Command.code = CommandCode.SET_STATE``.

    Called ``TriggerCmds`` in the Moog controller.
    """

    INVALID = 0
    ENABLE = 2
    STANDBY = 3
    CLEAR_ERROR = 6
    FAULT = 8
