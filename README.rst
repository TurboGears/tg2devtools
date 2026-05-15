===================================
TurboGears 2 DevTools
===================================

.. image:: https://github.com/TurboGears/tg2devtools/actions/workflows/run-tests.yml/badge.svg
    :target: https://github.com/TurboGears/tg2devtools/actions/workflows/run-tests.yml

.. image:: https://img.shields.io/pypi/v/tg.devtools.svg
   :target: https://pypi.python.org/pypi/tg.devtools

.. image:: https://img.shields.io/pypi/pyversions/TurboGears2.svg
    :target: https://pypi.python.org/pypi/TurboGears2

.. image:: https://img.shields.io/pypi/l/tg.devtools.svg
    :target: https://pypi.python.org/pypi/tg.devtools

TurboGears 2 DevTools is a command-line toolkit that streamlines the development of TurboGears2 applications. 
Built on top of Gearbox, it helps you quickly scaffold new full-stack projects, generate extensions, 
manage database migrations, and launch interactive shells all from one unified interface.

Key Features
------------
- **Quickstart**: Scaffold a new TurboGears2 project in minutes.
- **Extension Generator**: Easily create and integrate TurboGears extensions.
- **Database Migrations**: Run migration commands for SQLAlchemy and Alembic effortlessly.
- **Interactive Shell**: Launch a shell preloaded with your app's context for rapid testing.
- **Internationalization**: Extract, initialize, update, and compile translation catalogs for your application.
- **Agent Inspection**: Inspect routes, models, templates, and scaffold templates with ``tginfo``.
- **MCP Integration**: Serve TurboGears-aware MCP tools over stdio and initialize supported client configs.
- **Gearbox Integration**: Seamlessly work with Gearbox to serve and manage your applications.

Getting Started
---------------

.. image:: https://asciinema.org/a/703596.png
    :target: https://asciinema.org/a/703596?autoplay=1


**Installation:**

To install via pip, run:

::

    pip install tg.devtools

For development and testing, install with extras:

::

    pip install -e .[testing]

**Creating a New Project:**

Use the quickstart command to generate a new TurboGears2 full-stack application:

::

    gearbox quickstart myproject

This creates a ready-to-run project with a standard directory structure and preconfigured settings.
To start the newly created web application, follow the instructions in the project ``README.rst`` file.

Usage Examples
--------------
- **Generate a TG Extension:**

  ::

      gearbox tgext

- **Run Database Migrations:**

  ::

      gearbox sqla-migrate
      gearbox migrate

- **Launch an Interactive Shell:**

  ::

      gearbox tgshell -c development.ini

- **Inspect a Project for Agents and Scripts:**

  ::

      gearbox tginfo summary --project . --config development.ini
      gearbox tginfo routes --project . --config development.ini --json
      gearbox tginfo models --project . --config development.ini --json
      gearbox tginfo templates --project . --config development.ini --json
      gearbox tginfo scaffolds --project . --config development.ini --json

  ``tginfo`` is read-only. It can import the target application just like
  ``gearbox tgshell`` or ``gearbox serve``, but it does not run ``setup-app``,
  migrations, database writes, or runtime requests as part of inspection.

- **Serve TurboGears MCP Tools:**

  ::

      gearbox tgmcp --project . --config development.ini

  ``tgmcp`` serves MCP over stdio only. It is implemented directly in
  ``tg.devtools`` without an extra MCP SDK dependency, and stdout is reserved
  for MCP JSON-RPC protocol messages. Run it in an environment that can import
  Gearbox, TurboGears, ``tg.devtools``, the target application, and the
  application's runtime dependencies, the same practical requirement as
  ``gearbox tgshell``.

  The MCP read tools inspect project summary, routes, models, templates, and
  scaffold templates. The ``tg_scaffold`` tool is the only v1 MCP tool that
  writes project files; it delegates to Gearbox scaffold semantics.

- **Configure Supported MCP Clients:**

  ::

      gearbox tgmcp init claude --project .
      gearbox tgmcp init codex --project .
      gearbox tgmcp init vscode --project .
      gearbox tgmcp init pi --project .
      gearbox tgmcp init all --project .

  Supported init targets are ``claude``, ``codex``, ``vscode``, ``pi``, and
  ``all``. The command writes or merges only the selected client config files
  and, unless ``--no-agents-md`` is passed, ``AGENTS.md``. The ``pi`` target
  updates ``AGENTS.md`` only.

- **Runtime Debugging:**

  Use ``gearbox tgshell -c development.ini`` when you need the fully loaded
  application context for runtime checks, including WebTest requests. Runtime
  request debugging belongs in ``tgshell`` rather than ``tginfo`` or MCP route
  tracing.

- **Safety Boundaries:**

  ``tginfo`` and MCP inspection tools are read-only. ``tg_scaffold`` is the
  only v1 MCP tool that writes project files, and ``tgmcp init`` writes only
  selected client config files and ``AGENTS.md``. Do not run ``setup-app``,
  migrations, or other database-mutating commands as routine inspection; use
  them only when intentionally changing a development or test environment.

- **Manage Translations:**

  ::

      gearbox i18n extract
      gearbox i18n init -l es
      gearbox i18n update
      gearbox i18n compile

Resources
---------
- **TurboGears Website**: `http://www.turbogears.org`
- **Documentation**: `https://turbogears.readthedocs.io`
- **Agent/MCP Design Reference**: ``SPEC_MCP.txt`` in this repository.
- **Community & Support**: Join our `Mailing List <http://groups.google.com/group/turbogears>`_ or `Gitter Chatroom <https://gitter.im/turbogears/Lobby>`_ chatroom.

Contributing
------------
Contributions, bug reports, and feature requests are welcome! 

License
-------
TurboGears 2 DevTools is licensed under the MIT License. 
See the ``LICENSE.txt`` file for details.
