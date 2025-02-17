"""Sphinx configuration file for an LSST stack package.

This configuration only affects single-package Sphinx documentation builds.
"""

import lsst.ts.hexrotcomm  # noqa
from documenteer.conf.pipelinespkg import *  # type: ignore # noqa

project = "ts_hexrotcomm"
html_theme_options["logotext"] = project  # type: ignore # noqa
html_title = project
html_short_title = project
doxylink = {}  # type: ignore # noqa

intersphinx_mapping["ts_xml"] = ("https://ts-xml.lsst.io", None)  # type: ignore # noqa
intersphinx_mapping["ts_salobj"] = ("https://ts-salobj.lsst.io", None)  # type: ignore # noqa
intersphinx_mapping["ts_tcpip"] = ("https://ts-tcpip.lsst.io", None)  # type: ignore # noqa
