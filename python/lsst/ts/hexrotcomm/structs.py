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

__all__ = ["Command", "CommandStatus", "Header"]

import ctypes

# Called ``LENGTH_CMD_STATUS_REASON`` in the Moog controller code.
COMMAND_STATUS_REASON_LEN = 50


class Command(ctypes.Structure):
    """Command for a Moog controller.

    Called ``commandStreamStructure_t`` in the Moog controller.
    """

    _pack_ = 1
    _fields_ = [
        ("commander", ctypes.c_uint),
        ("counter", ctypes.c_uint),
        ("code", ctypes.c_uint),
        ("param1", ctypes.c_double),
        ("param2", ctypes.c_double),
        ("param3", ctypes.c_double),
        ("param4", ctypes.c_double),
        ("param5", ctypes.c_double),
        ("param6", ctypes.c_double),
    ]
    COMMANDER = 2  # value of the commander field for a CSC


class CommandStatus(ctypes.Structure):
    """Command status from a Moog controller.

    Called ``commandStatusStructure_t`` in the Moog controller.
    """

    _pack_ = 1
    _fields_ = [
        ("status", ctypes.c_uint),  # called cmdStatus in the Moog controller.
        ("duration", ctypes.c_double),
        ("reason", ctypes.c_char * COMMAND_STATUS_REASON_LEN),
    ]


class Header(ctypes.Structure):
    """Initial part of telemetry or configuration data from a Moog controller.

    Called ``telemetryHeaderStructure_t`` in the Moog controller.
    """

    _pack_ = 1
    _fields_ = [
        ("frame_id", ctypes.c_uint),
        ("counter", ctypes.c_uint),
        ("tai_sec", ctypes.c_int64),
        ("tai_nsec", ctypes.c_long),
    ]
