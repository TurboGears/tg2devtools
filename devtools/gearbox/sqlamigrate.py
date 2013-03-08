"""
TurboGears migration

gearbox migrate command integrate sqlalchemy-migrate into TurboGears 2.

To start a migration, run command::

    $ gearbox migrate create

And migrate command will create a 'migration' directory for you.
With migrate command you don't need use 'manage.py' in 'migration' directory anymore.

Then you could bind the database with migration with command::

    $ gearbox migrate version_control

Usage:

.. parsed-literal::

   gearbox migrate help
   gearbox migrate create
   gearbox migrate vc|version_control
   gearbox migrate dbv|db_version
   gearbox migrate v|version
   gearbox migrate manage [script.py]
   gearbox migrate test [script.py]
   gearbox migrate ci|commit [script.py]
   gearbox migrate up|upgrade [--version]
   gearbox migrate downgrade [--version]

.. container:: gearbox-usage

  --version
      database's version number

check http://code.google.com/p/sqlalchemy-migrate/wiki/MigrateVersioning for detail.

"""
from __future__ import print_function
from gearbox.command import Command

try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser

import sys, os

class MigrateCommand(Command):
    """Create and apply SQLAlchemy migrations
    Migrations will be managed inside the 'migration/versions' directory

    Usage: gearbox migrate COMMAND ...
    Use 'gearbox migrate help' to get list of commands and their usage

    Create a new migration::

        $ gearbox migrate script 'Add New Things'

    Apply migrations::

        $ gearbox migrate upgrade
    """
    def get_description(self):
        return 'Handles TurboGears2 Database Migrations'

    def get_parser(self, prog_name):
        parser = super(MigrateCommand, self).get_parser(prog_name)

        parser.add_argument("-c", "--config",
            help='application config file to read (default: development.ini)',
            dest='ini', default="development.ini")

        parser.add_argument('args', nargs='*')

        return parser

    def take_action(self, opts):
        #Work-around for SQLA0.8 being incompatible with sqlalchemy-migrate
        import sqlalchemy
        sqlalchemy.exceptions = sqlalchemy.exc

        from migrate.versioning.shell import main

        sect = 'app:main'
        option = 'sqlalchemy.url'

        # get sqlalchemy.url config in app:mains
        conf = ConfigParser()
        conf.read(opts.ini)

        name = "migration"
        try:
            dburi = conf.get(sect, option, vars={'here':os.getcwd()})
        except:
            print("Unable to read config file or missing sqlalchemy.url in app:main section")
            return

        print("Migrations repository '%s',\ndatabase url '%s'\n"%(name, dburi))
        if not opts.args:
            opts.args = ['help']
        sys.argv[0] = sys.argv[0] + ' migrate'
        main(argv=opts.args, url=dburi, repository=name, name=name)
