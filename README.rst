===================================
TurboGears 2 DevTools
===================================

[![Build Status](https://img.shields.io/travis/TurboGears/tg2devtools.svg)](https://travis-ci.org/TurboGears/tg2devtools)
[![PyPI version](https://img.shields.io/pypi/v/tg.devtools.svg)](https://pypi.org/project/tg.devtools)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

TurboGears 2 DevTools is a command-line toolkit that streamlines the development of TurboGears2 applications. 
Built on top of Gearbox, it helps you quickly scaffold new full-stack projects, generate extensions, 
manage database migrations, and launch interactive shells—all from one unified interface.

Key Features
------------
- **Quickstart**: Scaffold a new TurboGears2 project in minutes.
- **Extension Generator**: Easily create and integrate TurboGears extensions.
- **Database Migrations**: Run migration commands for SQLAlchemy and Alembic effortlessly.
- **Interactive Shell**: Launch a shell preloaded with your app's context for rapid testing.
- **Gearbox Integration**: Seamlessly work with Gearbox to serve and manage your applications.

Getting Started
---------------
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

      gearbox tgshell

Resources
---------
- **TurboGears Website**: `http://www.turbogears.org`
- **Documentation**: `https://turbogears.readthedocs.io`
- **Community & Support**: Join our mailing list or Gitter chatroom.

Contributing
------------
Contributions, bug reports, and feature requests are welcome! 

License
-------
TurboGears 2 DevTools is licensed under the MIT License. 
See the [LICENSE](LICENSE.txt) file for details.
