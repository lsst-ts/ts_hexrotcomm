.. py:currentmodule:: lsst.ts.hexrotcomm

.. _lsst.ts.hexrotcomm.version_history:

###############
Version History
###############

v1.3.3
------

* Add the **extra_commands** argument to ``BaseCsc.__init__()``.
* Remove the **ts-idl**.

v1.3.2
------

* Add the ``BaseCsc.standby_controller()``.

v1.3.1
------

* Fix the race condition in ``BaseCsc.basic_telemetry_callback()`` with the ``BaseCsc.begin_disable()``.
The reason we can do so is because the controller has a simplified state machine now.
It only has the **Standby**, **Enabled**, and **Fault** states.

v1.3.0
------

* Remove the code related to the deprecated state machine in controller.
* Migrate the functions from **ts_mtrotator**.

v1.2.2
------

* Update the version of ts-conda-build to 0.4 in the conda recipe.

v1.2.1
------

* Minimize the dependency of rotator xml in **SimpleCsc** class. 

v1.2.0
------

* Add configureEmergencyAcceleration & configureEmergencyJerk to `SimpleCsc`.

v1.1.3
------

* Support the **mypy**.

v1.1.2
------

* Import the enums from **ts_xml** instead of **ts_idl**.
* Fix the failed tests because the rotator has no **OFFLINE** state anymore.
* Update the ``.ts_pre_commit_config.yaml``.

v1.1.1
------

* Unpin python version in coda recipe.

Requires:

* ts_utils 1
* ts_salobj 7
* ts_idl 3.6
* ts_tcpip 1.1
* MTRotator IDL file built from ts_xml

v1.1.0
------

* Support ts_mtrotator using the new simplified low-level controller states:

    * Use ts_idl enums for MTHexapod instead of MTRotator.
    * Add some TODO notes for future changes, should MTHexapod also adopt the simpler states.

Requires:

* ts_utils 1
* ts_salobj 7
* ts_idl 3.6
* ts_tcpip 1.1
* MTRotator IDL file built from ts_xml

v1.0.0
------

* `BaseMockController`: inherit from lsst.ts.tcpip.OneClientReadLoopServer.
  This requires ts_tcpip 1.1.
* test_command_telemetry_server: use lsst.ts.tcpip.Client instead of asyncio.open_connection (or one test).
* Use ts_pre_commit_config.
* ``Jenkinsfile``: use the new shared library.
* Remove scons support.

Requires:

* ts_utils 1
* ts_salobj 7
* ts_idl 3.6
* ts_tcpip 1.1
* MTRotator IDL file built from ts_xml

v0.31.1
-------

* pre-commit: update black to 23.1.0, isort to 5.12.0, mypy to 1.0.0, and pre-commit-hooks to v4.4.0.
* ``Jenkinsfile``: modernize.

Requires:

* ts_utils 1
* ts_salobj 7
* ts_idl 3.6
* ts_tcpip 1
* MTRotator IDL file built from ts_xml

v0.31.0
-------

* `CommandTelemetryClient`: inherit from `lsst.ts.tcpip.Client`, which requires ts_tcpip 1.0.
* `BaseMockController`: update to use ts_tcpip 1.0 features in `lsst.ts.tcpip.OneClientServer`.
* Stop exporting symbols from ts_tcpip, except ``LOCAL_HOST``, which is still used by ts_mtrotator.
* Make tests/test_command_telemetry_server.py more robust by avoiding asyncTearDown.

Requires:

* ts_utils 1
* ts_salobj 7
* ts_idl 3.6
* ts_tcpip 1
* MTRotator IDL file built from ts_xml

v0.30.2
-------

* `CommandTelemetryClient`: fix one logging statement.

Requires:

* ts_utils 1
* ts_salobj 7
* ts_idl 3.6
* ts_tcpip 0.1
* MTRotator IDL file built from ts_xml

v0.30.1
-------

* Build with pyproject.toml

Requires:

* ts_utils 1
* ts_salobj 7
* ts_idl 3.6
* ts_tcpip 0.1
* MTRotator IDL file built from ts_xml

v0.30.0
-------

* Only send the CLEAR_ERROR command once, instead of twice with a pause between.
  This requires ts_hexapod_controller v1.3.2 and ts_rotator_controller v1.4.3.
* setup.cfg: specify asyncio_mode = auto to eliminate a warning.

Requires:

* ts_utils 1
* ts_salobj 7
* ts_idl 3.6
* ts_tcpip 0.1
* MTRotator IDL file built from ts_xml

v0.29.0
-------

* Update for ts_salobj v7, which is required.
  This also requires ts_xml 11.

Requires:

* ts_utils 1
* ts_salobj 7
* ts_idl 3.6
* ts_tcpip 0.1
* MTRotator IDL file built from ts_xml

v0.28.1
-------

* Fix enabling of the low-level controller (DM-32902): wait for one telemetry sample after first connecting.
* `BaseCsc`: eliminate the unused ``wait_summary_state`` method and add some long messages to ``enable_controller``.

Requires:

* ts_utils 1
* ts_salobj 6.8
* ts_idl 3.6
* ts_tcpip 0.1
* ts_xml 10.2
* MTRotator IDL file, e.g. built using ``make_idl_file.py MTRotator`` (for `SimpleCsc` and unit tests)

v0.28.0
-------

* Update for ts_hexapod_controller 1.3.0 and ts_rotator_controller 1.4.0:

    * Use a single socket for communication with the low-level controller.
      Eliminate the `CommandTelemetryServer` class, moving its non-server functionality into `BaseMockController`.

    * Use new standardized frame IDs for data from the low-level controller.
      Provide these values in a new `FrameId` enum class.
      Eliminate the FRAME_ID class constant in config and telemetry structs.

    * `Command`: replace the ``sync_pattern`` field with ``commander``.
      The new field has a standard value for commands from the CSC, which is provided as a `Command` class constant.

    * `Header`: update the type of the ``frame_id`` field to match a change in the low-level controllers.

* `CommandTelemetryClient`: expand the ``connected`` property to check that the reader is not None.
  The main driver was to make type checkers happier, but it also adds a modicum of safety.

Requires:

* ts_utils 1
* ts_salobj 6.8
* ts_idl 3.6
* ts_tcpip 0.1
* ts_xml 10.2
* MTRotator IDL file, e.g. built using ``make_idl_file.py MTRotator`` (for `SimpleCsc` and unit tests)

v0.27.0
-------

* `BaseCsc`: remove the ``clearError`` command (which was not supported, but still present in the XML).
  This change requires ts_xml 10.2.

Requires:

* ts_utils 1
* ts_salobj 6.8
* ts_idl 3.6
* ts_tcpip 0.1
* ts_xml 10.2
* MTRotator IDL file, e.g. built using ``make_idl_file.py MTRotator`` (for `SimpleCsc` and unit tests)

v0.26.0
-------

* Updated unit tests for compatibility with ts_salobj 6.8, which is now required.
* `CONFIG_SCHEMA`: update id link to use `main` instead of `master`.
* ``setup.cfg``: prevent pytest from checking version.py

Requires:

* ts_utils 1
* ts_salobj 6.8
* ts_idl 3.6
* ts_tcpip 0.1
* ts_xml 7.2
* MTRotator IDL file, e.g. built using ``make_idl_file.py MTRotator`` (for `SimpleCsc` and unit tests)

v0.25.0
-------

* `CommandTelemetryClient` and `CommandTelemetryServer`: support command acknowledgement:

    * Change ``CommandTelemetryClient.put_command`` to `CommandTelemetryClient.run_command`.
    * Add `CommandStatusCode` enum, `CommandStatus` struct, and `CommandError` exception.

* `BaseCsc`: update for command acknowledgement.

Requires:

* ts_utils 1
* ts_salobj 6.3
* ts_idl 3.6
* ts_tcpip 0.1
* ts_xml 7.2
* MTRotator IDL file, e.g. built using ``make_idl_file.py MTRotator`` (for `SimpleCsc` and unit tests)

v0.24.0
-------

* `BaseCsc`:

    * Go to FAULT state and report error code NO_CONFIG if the low-level controller does not report config shortly after connecting.
      This requires ts_idl 3.6.
    * Remove the deprecated ``schema_path`` constructor argument.
      It and was not being used.

Requires:

* ts_utils 1
* ts_salobj 6.3
* ts_idl 3.6
* ts_tcpip 0.1
* ts_xml 7.2
* MTRotator IDL file, e.g. built using ``make_idl_file.py MTRotator`` (for `SimpleCsc` and unit tests)

v0.23.1
-------

* `BaseCsc`: go to FAULT state if the CSC cannot connect to the low-level controller.
* Modernize unit tests to use bare assert.

Requires:

* ts_utils 1
* ts_salobj 6.3
* ts_idl 2.2
* ts_tcpip 0.1
* ts_xml 7.2
* MTRotator IDL file, e.g. built using ``make_idl_file.py MTRotator`` (for `SimpleCsc` and unit tests)

v0.23.0
-------

* Swap client and server, so the client runs in the CSC and the server runs in the mock controller.
  This change requires new versions of the low-level controller code: ts_hexapod_controller and ts_rotator_controller (see ts_mthexapod and ts_mtrotator for details).

* `BaseCsc` changes:

    * Connect to the low-level controller as part of the ``start`` command.
    * Make the CSC summary state mostly independent of the low-level controller state (an excellent suggestion from Tiago).
      As part of the ``enable`` command, the CSC commands the low-level controller to its own enabled state,
      including clearing errors, if necessary.
      See :ref:`communication protocol <lsst.ts.hexrotcomm_communication_protocol>` for more information.
    * Configuration should now include fields for TCP/IP host, port and connection_timeout.
      An alternative for the first two is to override the default host and port properties.
    * The ``clearError`` command is no longer supported (and will be removed in a future ticket).
      Use the standard sequence ``standby``, ``start``, and ``enable`` to recover from errors.
    * The CSC is no longer alive in the OFFLINE state.
    * Update to use `lsst.ts.idl.enums.MTRotator.ErrorCode`, which requires ts_idl 3.4.

* `CommandTelemetryServer`: make the `host` constructor argument optional, with a default of ``tcpip.LOCALHOST_IPV4``.
  Also prohibit constructing with host=None and port=0, to make sure we can determine the randomly chosen ports.
* Add optional ``host`` constructor argument to `BaseMockController` and `SimpleMockController`.
* Add a ``Jenkinsfile``.
* setup.cfg: add [options] section.

Requires:

* ts_utils 1
* ts_salobj 6.3
* ts_idl 2.2
* ts_tcpip 0.1
* ts_xml 7.2
* MTRotator IDL file, e.g. built using ``make_idl_file.py MTRotator`` (for `SimpleCsc` and unit tests)

v0.22.0
-------

* Make state transition commands more reliable and more efficient:
  allow more time for the low-level controller to implement the change,
  and stop waiting as soon as the change is reported.
* Updated to use ts_utils, which is required.
* `BaseCsc`:

    * Add ``wait_summary_state`` method.
    * ``assert_summary_state`` method: deprecate the ``isbefore`` argument.

* `CommandTelemetryServer`:

    * Remove the `skip` argument of the ``next_telemetry`` method.
      It is much better to check each telemetry packet for the data you are awaiting.
    * Remove diagnostic print statements.

* `test_command_telemetry_server.py`: fix test cleanup, which was not running due to a typo.

Requires:

* ts_utils 1
* ts_salobj 6.3
* ts_idl 2.2
* ts_tcpip 0.1
* ts_xml 7.2
* MTRotator IDL file, e.g. built using ``make_idl_file.py MTRotator`` (for `SimpleCsc` and unit tests)

v0.21.0
-------

Deprecations:

* You should obtain the following from ts_tcpip: OneClientServer, close_stream_writer, read_into, write_from, LOCAL_HOST.
  At some point these symbols will no longer be available from ts_hexrotcomm.

* Use the new ts_tcpip package.
  Temporarily make the symbols that moved available in lsst.ts.hexrotcomm, for backwards compatibility.
* Test black formatting with pytest instead of a custom unit test.

Requires:

* ts_salobj 6.3
* ts_idl 2.2
* ts_tcpip 0.1
* ts_xml 7.2
* MTRotator IDL file, e.g. built using ``make_idl_file.py MTRotator`` (for `SimpleCsc` and unit tests)

v0.20.0
-------

* Change message headers to use TAI unix time.
  Rename the fields from tv_sec, tv_nsec to tai_sec, tai_nsec and set them accordingly.
  Note that this requires a corresponding update to the low-level rotator and hexapod controllers
  (see `DM-26451 <https://jira.lsstcorp.org/browse/DM-26451>`_
  and `DM-30120 <https://jira.lsstcorp.org/browse/DM-30120>`_)

Requires:

* ts_salobj 6.3
* ts_idl 2.2
* ts_xml 7.2
* MTRotator IDL file, e.g. built using ``make_idl_file.py MTRotator`` (for `SimpleCsc` and unit tests)

v0.19.0
-------

* Update for changes to the low-level hexapod and rotator TCP/IP interfaces:
  remove the mjd and mjd_frac fields from config and telemetry headers.

Requires:

* ts_salobj 6.3
* ts_idl 2.2
* ts_xml 7.2
* MTRotator IDL file, e.g. built using ``make_idl_file.py MTRotator`` (for `SimpleCsc` and unit tests)

v0.18.1
-------

* `BaseCsc`: bug fix: ``run_commands`` did not acquire the new ``write_lock``.
* `BaseCsc`: change ``assert_enabled`` to check that the CSC can command the low-level controller
  (like the other, similar, assert methods).
* `BaseCsc`: added method ``basic_run_command``.

Requires:

* ts_salobj 6.3
* ts_idl 2.2
* ts_xml 7.2
* MTRotator IDL file, e.g. built using ``make_idl_file.py MTRotator`` (for `SimpleCsc` and unit tests)

v0.18.0
-------

* `BaseCsc`: add ``write_lock`` attribute and aquire this lock while writing a command to the low-level controller.
  You should acquire this lock before cancelling any task that sends commands to the low-level controller,
  to prevent writing partial commands and leaving data in the TCP/IP stream buffer.

Requires:

* ts_salobj 6.3
* ts_idl 2.2
* ts_xml 7.2
* MTRotator IDL file, e.g. built using ``make_idl_file.py MTRotator`` (for `SimpleCsc` and unit tests)

v0.17.1
-------

* Format the code with black 20.8b1.

Requires:

* ts_salobj 6.3
* ts_idl 2.2
* ts_xml 7.2
* MTRotator IDL file, e.g. built using ``make_idl_file.py MTRotator`` (for `SimpleCsc` and unit tests)

v0.17.0
-------

* `close_stream_writer`: swallow `ConnectionResetError`, since this means the writer is closing or closed.
* `OneClientServer`: bug fix: ``connect_callback`` was not reliably called by ``close_client``.
* `SimpleCsc`: update to write the ``rotation`` MTRotator telemetry topic,
  instead of the deprecated ``application`` telemetry topic.
* `CommandTelemetryClient`: always set a writer attribute to `None` when closing it,
  to eliminate any danger of trying to close a writer twice.
* Use `unittest.IsolatedAsyncioTestCase` instead of the abandoned asynctest package.

Requires:

* ts_salobj 6.3
* ts_idl 2.2
* ts_xml 7.2
* MTRotator IDL file, e.g. built using ``make_idl_file.py MTRotator`` (for `SimpleCsc` and unit tests)

v0.16.0
-------

* `BaseCsc`: add ``config_schema`` constructor argument.
  This requires ts_salobj 6.3.
* `SimpleCsc`: specify config schema using the ``config_schema`` argument.
* Delete obsolete file ``schema/MTRotator.yaml``.

Requires:

* ts_salobj 6.3
* ts_idl 2.2
* ts_xml 7.2
* MTRotator IDL file, e.g. built using ``make_idl_file.py MTRotator`` (for `SimpleCsc` and unit tests)

v0.15.0
-------

* Update for ts_xml 7.2 (which is required for the unit tests to pass): add ``do_fault`` method to `SimpleCsc`.
* `CommandTelemetryServer`: improve handling of invalid headers:

    * Flush the remaining data and try to continue, instead of disconnecting.
    * Print the header bytes when an unrecognized frame ID is read.
* `OneClientServer`: bug fix: only set connected_task result if not already done.
* Modernize ``doc/conf.py`` for documenteer 0.6.

Requires:

* ts_salobj 6.1
* ts_idl 2.2
* ts_xml 7.2
* MTRotator IDL file, e.g. built using ``make_idl_file.py MTRotator`` (for `SimpleCsc` and unit tests)

v0.14.0
-------

* Support different ports for different CSCs:

    * Eliminate COMMAND_PORT and TELEMETRY_PORT constants.
    * `CommandTelemetryServer`: replace use_random_port argument with port.
    * `CommandTelemetryClient` and `BaseMockController`: make the command_port and telemetry_port arguments required.

Requires:

* ts_salobj 6.1
* ts_idl 2.2
* ts_xml 7
* MTRotator IDL file, e.g. built using ``make_idl_file.py MTRotator`` (for `SimpleCsc` and unit tests)

v0.13.0
-------

* Add optional ``set_simulation_mode`` constructor argument to `BaseCsc` and `SimpleCsc`.
  This is a backwards compatible change.

Requires:

* ts_salobj 6.1
* ts_idl 2.2
* ts_xml 7
* MTRotator IDL file, e.g. built using ``make_idl_file.py MTRotator`` (for `SimpleCsc` and unit tests)

v0.12.1
-------

* Update Jenkinsfile.conda to use Jenkins Shared Library
* Pinned the ts-idl and ts-salobj version in conda recipe

Requires:

* ts_salobj 6.1
* ts_idl 2.2
* ts_xml 7
* MTRotator IDL file, e.g. built using ``make_idl_file.py MTRotator`` (for `SimpleCsc` and unit tests)

v0.12.0
-------

* Update the mock controller to make the time used in update_telemetry match the time in the header:

    * Update `CommandTelemetryClient.update_and_get_header` to return the current time in addition to the header,
      and update the call to `update_telemetry` to provide that time.
    * Update `BaseMockController,update_telemetry` and `SimpleMockController.update_telemetry` to receive time as an argument.

Requires:

* ts_salobj 6.1
* ts_idl 2.2
* ts_xml 7
* MTRotator IDL file, e.g. built using ``make_idl_file.py MTRotator`` (for `SimpleCsc` and unit tests)

v0.11.0
-------

* Update for ts_xml 7 and ts_idl 2.2:

    * Rename SAL component and ts_idl enum module ``Rotator`` to ``MTRotator``.

Requires:

* ts_salobj 6.1
* ts_idl 2.2
* ts_xml 7
* MTRotator IDL file, e.g. built using ``make_idl_file.py MTRotator`` (for `SimpleCsc` and unit tests)

v0.10.0
-------

* Update for ts_salobj 6.1.
* Update the handling of initial_state in `BaseCsc`:

    * If initial_state != OFFLINE then report all transitional summary states and controller states at startup.
    * Require initial_state = OFFLINE unless simulating.
* Add `BaseCscTestCase` with overridden versions of:

    * `BaseCscTestCase.make_csc`: read all but the final controller state at startup,
    * `BaseCscTestCase.check_bin_script`: set ``default_initial_state``.

Requires:

* ts_salobj 6.1
* ts_idl 2
* ts_xml 4.6 - 6
* Rotator IDL file, e.g. built using ``make_idl_file.py Rotator`` (for `SimpleCsc` and unit tests)

v0.9.0
======

* Add `close_stream_writer` function that closes an `asyncio.StreamWriter` and waits for it to close.
* Update code to wait for stream writers to close.

Requires:

* ts_salobj 5.11 - 6.0
* ts_idl 1 (with salobj 5) or 2 (with salobj 6)
* ts_xml 4.6 - 6
* Rotator IDL file, e.g. built using ``make_idl_file.py Rotator`` (for `SimpleCsc` and unit tests)

v0.8.0
======

Backward-incompatible changes:

* Remove ``BaseCscTestCase`` and ``CscCommander`` classes; use the versions in ts_salobj instead.
* Bug fix: `BaseCsc.get_config_pkg` returned "ts_config_ocs" instead of "ts_config_mttcs".

* Add missing call to ``begin_start`` to `BaseCsc.do_start`.
* Make `BaseCsc.fault` raise `NotImplementedError`, since the low-level controller maintains the summary state and offers no command to transition to the FAULT state.

Requires:

* ts_salobj 5.11 - 6
* ts_idl 1 (with salobj 5) or 2 (with salobj 6)
* ts_xml 4.6 - 6
* Rotator IDL file, e.g. built using ``make_idl_file.py Rotator`` (for `SimpleCsc` and unit tests)

v0.7.0
======

* Make `BaseCsc` a configurable CSC.

Requires:

* ts_salobj 5.11 - 6
* ts_idl 1 (with salobj 5) or 2 (with salobj 6)
* ts_xml 4.6 - 6
* Rotator IDL file, e.g. built using ``make_idl_file.py Rotator`` (for `SimpleCsc` and unit tests)

v0.6.0
======

* Update for compatibility with ts_salobj 6.

Requires:

* ts_salobj 5.11 - 6
* ts_idl 1 (with salobj 5) or 2 (with salobj 6)
* ts_xml 4.6 - 6
* Rotator IDL file, e.g. built using ``make_idl_file.py Rotator`` (for `SimpleCsc` and unit tests)

v0.5.2
======

* Add black to conda test dependencies

Requires:

* ts_salobj 5.11
* ts_idl 1
* ts_xml 4.6
* Rotator IDL file, e.g. built using ``make_idl_file.py Rotator`` (for `SimpleCsc` and unit tests)

v0.5.1
======

* Add ``tests/test_black.py`` to verify that files are formatted with black.
  This requires ts_salobj 5.11 or later.
* Update `BaseCscTestCase.check_bin_script` to be compatible with ts_salobj 5.12.
* Fix f strings with no {}.
* Update ``.travis.yml`` to remove ``sudo: false`` to github travis checks pass once again.

Requires:

* ts_salobj 5.11
* ts_idl 1
* ts_xml 4.6
* Rotator IDL file, e.g. built using ``make_idl_file.py Rotator`` (for `SimpleCsc` and unit tests)

v0.5.0
======

* Make `BaseCsc` forward compatible with ts_xml 5.2 and with explicitly listing which generic topics are used.

Requires:

* ts_salobj 5
* ts_idl 1
* ts_xml 4.6
* Rotator IDL file, e.g. built using ``make_idl_file.py Rotator`` (for `SimpleCsc` and unit tests)

v0.4.0
======

* The clearError command in the mock controller now transitions to STANDBY instead of OFFLINE/AVAILABLE.
  This matches a recent change to the rotator controller and a planned change to the hexapod controller.
* Include conda package build configuration.
* Added a Jenkinsfile to support continuous integration and to build conda packages.
* Fixed a bug in `OneClientServer.close`: it would fail if called twice.

Requires:

* ts_salobj 5
* ts_idl 1
* ts_xml 4.6
* Rotator IDL file, e.g. built using ``make_idl_file.py Rotator`` (for `SimpleCsc` and unit tests)

v0.3.0
======

Major changes:

* Allow the ``connect_callback`` argument of `OneClientServer` to be `None`.
  That actually worked before, but it was not documented and resulted in an exception being logged for each callback.
* Code formatted by ``black``, with a pre-commit hook to enforce this. See the README file for configuration instructions.

Requires:

* ts_salobj 5
* ts_idl 1
* ts_xml 4.6
* Rotator IDL file, e.g. built using ``make_idl_file.py Rotator`` (for `SimpleCsc` and unit tests)

v0.2.0
======

Add `BaseCsc.make_command` and `BaseCsc.run_multiple_commands`.
Update for Rotator XML refinements.
Disambiguate the use of `cmd` (*warning*: not backwards compatible):

* Rename Command.cmd to Command.code
* Rename cmd argument to command for BaseCsc.run_command
  and CommandTelemetryServer.put_command

Requires:

* ts_salobj 5
* ts_idl 1
* ts_xml 4.6
* Rotator IDL file, e.g. built using ``make_idl_file.py Rotator`` (for `SimpleCsc` and unit tests)

v0.1.1
======

Fix an error in the MockController's CLEAR_ERROR command.

Requires:

* ts_salobj 5
* ts_idl 1
* Rotator IDL file, e.g. built using ``make_idl_file.py Rotator`` (for `SimpleCsc` and unit tests)

v0.1.0
======

Initial release.

Requires:

* ts_salobj 5
* ts_idl 1
* Rotator IDL file, e.g. built using ``make_idl_file.py Rotator`` (for `SimpleCsc` and unit tests)
