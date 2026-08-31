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

__all__ = ["CONFIG_SCHEMA"]

import yaml

# Configuration for SimpleCsc
CONFIG_SCHEMA = yaml.safe_load(
    """
$schema: http://json-schema.org/draft-07/schema#
$id: https://github.com/lsst-ts/ts_hexrotcomm/blob/main/python/lsst/ts/hexrotcomm/config_schema.py
title: MTRotator v2
description: Configuration for SimpleCsc, which has no configuration.
type: object
properties:
  host:
    description: >-
      IP address of the TCP/IP interface.
      Ignored for SimpleCsc, because it always runs in simulation mode.
    type: string
    format: hostname
  port:
    description: >-
      Port number of the TCP/IP interface.
      Ignored for SimpleCsc, because it always runs in simulation mode.
    type: integer
  connection_timeout:
    description: Time limit for connecting to the TCP/IP interface (sec)
    type: number
    exclusiveMinimum: 0
required: [host, port, connection_timeout]
additionalProperties: false
"""
)
