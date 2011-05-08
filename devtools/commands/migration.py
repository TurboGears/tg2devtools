"""
TurboGears migration

paster migrate command integrate sqlalchemy-migrate into TurboGears 2.

To start a migration, run command::

    $ paster migrate create

And migrate command will create a 'migration' directory for you.
With migrate command you don't need use 'manage.py' in 'migration' directory anymore.

Then you could bind the database with migration with command::

    $ paster migrate version_control

Usage:

.. parsed-literal::

   paster migrate help
   paster migrate create
   paster migrate vc|version_control
   paster migrate dbv|db_version
   paster migrate v|version
   paster migrate manage [script.py]
   paster migrate test [script.py]
   paster migrate ci|commit [script.py]
   paster migrate up|upgrade [--version]
   paster migrate downgrade [--version]

.. container:: paster-usage

  --version
      database's version number

check http://code.google.com/p/sqlalchemy-migrate/wiki/MigrateVersioning for detail.

"""

import pkg_resources
from paste.script import command
import os, sys
import ConfigParser
from migrate.versioning.shell import main

class MigrateCommand(command.Command):
    """Create and apply SQLAlchemy migrations
Migrations will be managed inside the 'migration/versions' directory

Usage: paster migrate COMMAND ...
Use 'paster migrate help' to get list of commands and their usage

Create a new migration::

    $ paster migrate script 'Add New Things'

Apply migrations::

    $ paster migrate upgrade
"""

    version = pkg_resources.get_distribution('turbogears2').version
    max_args = 3
    min_args = 1
    min_args_error = __doc__
    summary = __doc__.splitlines()[0]
    usage = '\n' + __doc__
    group_name = "TurboGears2"

    parser = command.Command.standard_parser(verbose=True)
    parser.add_option("-c", "--config",
        help='application config file to read (default: development.ini)',
        dest='ini', default="development.ini")

    def command(self):
        sect = 'app:main'
        option = 'sqlalchemy.url'

        # get sqlalchemy.url config in app:mains
        conf = ConfigParser.ConfigParser()
        conf.read(self.options.ini)

        self.name = "migration"
        try:
            self.dburi = conf.get(sect, option, vars={'here':os.getcwd()})
        except:
            print "Unable to read config file or missing sqlalchemy.url in app:main section"
            return

        print "Migrations repository '%s',\ndatabase url '%s'\n"%(self.name, self.dburi)
        if not self.args:
            self.args = ['help']
        sys.argv[0] = sys.argv[0] + ' migrate'
        main(argv=self.args, url=self.dburi, repository=self.name, name=self.name)
