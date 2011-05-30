"""Quickstart command to generate a new project.

TurboGears 2 uses Paste to create and deploy projects as well as create new
controllers and their tests.

Quickstart takes the files from turbogears.pastetemplates and processes them to
produce a new, ready-to-run project.

Create a new project named helloworld with this command::

    $ paster quickstart helloworld

You can use TurboGears2, Pylons, and WebHelper paster commands within the
project, as well as any paster commands that are provided by a plugin, or you
create yourself.

Usage:

.. parsed-literal::

    paster quickstart [--version][-h|--help]
            [-p *PACKAGE*][--dry-run][-s|--sqlalchemy][-x|--nosa][-a|--auth][-n|--noauth][-g|--geo]

.. container:: paster-usage

  --version
      how program's version number and exit
  -h, --help
      show this help message and exit
  -p PACKAGE, --package=PACKAGE
      package name for the code
  --dry-run
      dry run (don't actually do anything)
  -s, --sqlalchemy
      use SQLAlchemy as ORM
  -x, --nosa
      Do not use SQLAlchemy
  -a, --auth
      provide authentication and authorization support
  -n, --noauth
      provide no authentication or authorization support
  -g, --geo
      add GIS support
"""

import pkg_resources
import re
import optparse
from paste.script import command
from paste.script import create_distro
import os
import shutil
import stat
import sys

beginning_letter = re.compile(r"^[^a-z]*")
valid_only = re.compile(r"[^a-z0-9_]")

class QuickstartCommand(command.Command):
    """Create a new TurboGears 2 project.

Create a new Turbogears project with this command.

Example usage::

    $ paster quickstart yourproject

or start project with authentication and authorization support::

    $ paster quickstart -a yourproject
    """

    version = pkg_resources.get_distribution('turbogears2').version
    max_args = 3
    min_args = 0
    summary = __doc__.splitlines()[0]
    usage = '\n' + __doc__
    group_name = "TurboGears2"
    name = None
    auth = None
    geo = False
    package = None
    svn_repository = None
    sqlalchemy = False
    templates = "turbogears2"
    dry_run = False
    no_input = False

    parser = command.Command.standard_parser(quiet=True)
    parser = optparse.OptionParser(
                    usage="%prog quickstart [options] [project name]",
                    version="%prog " + version)

    parser.add_option("-a", "--auth",
            help='add authentication and authorization support',
            action="store_true", dest="auth")

    parser.add_option("-n", "--noauth",
            help='No authorization support',
            action="store_true", dest="no_auth")
    
    parser.add_option("-m", "--mako",
            help="default templates mako",
            action="store_true", dest="mako")

    parser.add_option("-g", "--geo",
            help="add GIS support",
            action="store_true", dest="geo")

    parser.add_option("-p", "--package",
            help="package name for the code",
            dest="package")

    parser.add_option("-s", "--sqlalchemy",
            help="use SQLAlchemy as ORM",
            action="store_true", dest="sqlalchemy", default=False)

    parser.add_option("-x", "--nosa",
            help="No SQLAlchemy",
            action="store_true", dest="no_sqlalchemy", default=False)

    parser.add_option("--disable-migrations",
            help="disable sqlalchemy-migrate model migrations",
            action="store_false", dest="migrations", default=True)

    parser.add_option("--dry-run",
            help="dry run (don't actually do anything)",
            action="store_true", dest="dry_run")

    parser.add_option("--noinput",
            help="no input (don't ask any questions)",
            action="store_true", dest="no_input")

    def command(self):
        """Quickstarts the new project."""

        self.__dict__.update(self.options.__dict__)
        
        
        if self.no_sqlalchemy:
            self.sqlalchemy = False
        
        if self.no_auth:
            self.auth=False
            
        if self.args:
            self.name = self.args[0]

        while not self.name:
            self.name = raw_input("Enter project name: ")

            
        if not self.package:
            package = self.name.lower()
            package = beginning_letter.sub("", package)
            package = valid_only.sub("", package)
            if package and self.no_input:
                self.package = package
            else:
                self.package = None
                while not self.package:
                    self.package = raw_input(
                        "Enter package name [%s]: " % package).strip() or package

        if self.no_input:

            #defaults
            self.mako = False
            self.auth = True
            self.migrations = True

        while self.mako is None:
            self.mako = raw_input(
                "Would you prefer mako templates? (yes/[no]): ")
            self.mako = dict(y=True, n=False).get(
                self.mako.lstrip()[:1].lower() or 'n')
            if self.mako is None:
                print "Please enter y(es) or n(o)."

        while self.auth is None:
            self.auth = raw_input(
                "Do you need authentication and authorization"
                " in this project? ([yes]/no): ")
            self.auth = dict(y=True, n=False).get(
                self.auth.lstrip()[:1].lower() or 'y')
            if self.auth is None:
                print "Please enter y(es) or n(o)."

        if self.auth:
            self.auth = "sqlalchemy"
            self.sqlalchemy = True
        else:
            self.auth = None

        self.name = pkg_resources.safe_name(self.name)

        env = pkg_resources.Environment()
        if self.name.lower() in env:
            print 'The name "%s" is already in use by' % self.name,
            for dist in env[self.name]:
                print dist
                return

        import imp
        try:
            if imp.find_module(self.package):
                print 'The package name "%s" is already in use' % self.package
                return
        except ImportError:
            pass

        if os.path.exists(self.name):
            print 'A directory called "%s" already exists. Exiting.' % self.name
            return

        self.cookiesecret = None
        try:
            import uuid
            self.cookiesecret = str(uuid.uuid4())
        except ImportError:
            import random
            import base64
            import struct
            self.cookiesecret = base64.b64encode("".join([struct.pack('i', random.randrange(2**31)) for x in [1,2,3,4,5,6]])).strip()

        command = create_distro.CreateDistroCommand("create")
        cmd_args = []
        for template in self.templates.split():
            cmd_args.append("--template=%s" % template)
        if self.dry_run:
            cmd_args.append("--simulate")
            cmd_args.append("-q")
        cmd_args.append(self.name)
        cmd_args.append("sqlalchemy=%s" % self.sqlalchemy)
        cmd_args.append("auth=%s" % self.auth)
        cmd_args.append("geo=%s" % self.geo)
        cmd_args.append("package=%s" % self.package)
        cmd_args.append("tgversion=%s" % self.version)
        cmd_args.append("mako=%s"%self.mako)
        cmd_args.append("migrations=%s"%self.migrations)
        cmd_args.append("cookiesecret=%s"%self.cookiesecret)
        # set the exact ORM-version for the proper requirements
        # it's extracted from our own requirements, so looking
        # them up must be in sync (there must be the extras_require named
        # sqlalchemy)
        
        command.run(cmd_args)

        if self.dry_run:
            return 
            
        os.chdir(self.name)
       
        sys.argv = ["setup.py", "egg_info"]
        import imp
        imp.load_module("setup", *imp.find_module("setup", ["."]))

        # dirty hack to allow "empty" dirs
        for base, path, files in os.walk("./"):
            for file in files:
                if file == "empty":
                    os.remove(os.path.join(base, file))

        #copy over the mako templates if appropriate
        if self.mako:
            print 'Writing mako template files to ./'+os.path.join(self.package, 'templates')

            #remove existing template files
            package_template_dir = os.path.abspath(os.path.join(self.package, 'templates'))
            shutil.rmtree(package_template_dir, ignore_errors=True)

            #replace template files with mako ones
            mako_template_dir = os.path.abspath(os.path.dirname(__file__))+'/quickstart_mako'
            shutil.copytree(mako_template_dir, package_template_dir)

        if not self.migrations:
            print 'Disabling migrations support'

            #remove existing migrations directory
            package_migrations_dir = os.path.abspath('migration')
            shutil.rmtree(package_migrations_dir, ignore_errors=True)

