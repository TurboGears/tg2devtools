from __future__ import print_function

import re
import pkg_resources
import os
import shutil
import sys

from gearbox.template import GearBoxTemplate
from gearbox.command import Command

PY3 = sys.version_info[0] == 3
beginning_letter = re.compile(r"^[^a-z]*")
valid_only = re.compile(r"[^a-z0-9_]")


class QuickstartTemplate(GearBoxTemplate):

    def pre(self, command, output_dir, vars):
        """Called before template is applied."""
        package_logger = vars['package']
        if package_logger == 'root':
            # Rename the app logger in the rare case a project is named 'root'
            package_logger = 'app'
        vars['package_logger'] = package_logger

        template_engine = vars.setdefault('template_engine', 'genshi')

        if template_engine == 'mako':
            # Support a Babel extractor default for Mako
            vars['babel_templates_extractor'] = ("('templates/**.mako',"
                " 'mako', None),\n%s#%s") % (' ' * 4, ' ' * 8)
        else:
            vars['babel_templates_extractor'] = ''

        if vars['geo'] == 'True':
            # Add tgext.geo as paster plugin
            vars['egg_plugins'].append('tgext.geo')

        if vars['migrations'] == 'True':
            vars['egg_plugins'].append('tg.devtools')


class QuickstartCommand(Command):

    def get_description(self):
        return 'Creates a new TurboGears2 project'

    def get_parser(self, prog_name):
        parser = super(QuickstartCommand, self).get_parser(prog_name)

        parser.add_argument("name")

        parser.add_argument("-a", "--auth",
            help='add authentication and authorization support',
            action="store_true", dest="auth", default=True)

        parser.add_argument("-n", "--noauth",
            help='No authorization support',
            action="store_true", dest="no_auth")

        parser.add_argument("-m", "--mako",
            help="default templates mako",
            action="store_true", dest="mako")

        parser.add_argument("-j", "--jinja",
            help="default templates jinja",
            action="store_true", dest="jinja")

        parser.add_argument("-k", "--kajiki",
            help="default templates kajiki",
            action="store_true", dest="kajiki")

        parser.add_argument("-g", "--geo",
            help="add GIS support",
            action="store_true", dest="geo")

        parser.add_argument("-p", "--package",
            help="package name for the code",
            dest="package")

        parser.add_argument("-s", "--sqlalchemy",
            help="use SQLAlchemy as ORM",
            action="store_true", dest="sqlalchemy", default=True)

        parser.add_argument("-i", "--ming",
            help="use Ming as ORM",
            action="store_true", dest="ming", default=False)

        parser.add_argument("-x", "--nosa",
            help="No SQLAlchemy",
            action="store_true", dest="no_sqlalchemy", default=False)

        parser.add_argument("--disable-migrations",
            help="disable alembic model migrations",
            action="store_false", dest="migrations", default=True)

        parser.add_argument("--enable-tw1",
            help="use toscawidgets 1.x in place of 2.x version",
            action="store_true", dest="tw1", default=False)

        parser.add_argument("--skip-tw",
            help="Disables ToscaWidgets",
            action="store_true", dest="skip_tw", default=False)

        parser.add_argument("--skip-genshi",
            help="Disables Genshi default template",
            action="store_true", dest="skip_genshi", default=False)

        return parser

    def take_action(self, opts):
        opts.egg_plugins = []

        if opts.no_sqlalchemy:
            opts.sqlalchemy = False

        if opts.ming:
            opts.sqlalchemy = False
            opts.migrations = False

        if opts.no_auth:
            opts.auth = False

        if not opts.package:
            package = opts.name.lower()
            package = beginning_letter.sub("", package)
            package = valid_only.sub("", package)
            opts.package = package

        if opts.tw1:
            opts.skip_tw = False

        if opts.auth:
            if opts.ming:
                opts.auth = "ming"
                opts.ming = True
            else:
                opts.auth = "sqlalchemy"
                opts.sqlalchemy = True
        else:
            opts.auth = None

        opts.database = opts.sqlalchemy or opts.ming

        opts.name = pkg_resources.safe_name(opts.name)
        opts.project = opts.name

        env = pkg_resources.Environment()
        if opts.name.lower() in env:
            print('The name "%s" is already in use by' % opts.name)
            for dist in env[opts.name]:
                print(dist)
                return

        import imp
        try:
            if imp.find_module(opts.package):
                print('The package name "%s" is already in use'
                    % opts.package)
                return
        except ImportError:
            pass

        if os.path.exists(opts.name):
            print('A directory called "%s" already exists. Exiting.'
                % opts.name)
            return

        opts.cookiesecret = None
        try:
            import uuid
            opts.cookiesecret = str(uuid.uuid4())
        except ImportError:
            import random
            import base64
            import struct
            opts.cookiesecret = base64.b64encode(''.join(
                [struct.pack('i', random.randrange(2 ** 31))
                    for _n in range(6)])).strip()

        devtools_path = os.path.dirname(os.path.os.path.abspath(
            os.path.dirname(__file__)))

        # Workaround for templates ported from Paste
        # which check for 'True' instead of True
        template_vars = dict(vars(opts))
        #for key, value in template_vars.items():
        #    if value is True:
        #        template_vars[key] = 'True'

        template_vars['PY3'] = PY3
        QuickstartTemplate().run(os.path.join(devtools_path,
            'templates', 'turbogears'), opts.name, template_vars)

        os.chdir(opts.name)

        sys.argv = ['setup.py', 'egg_info']
        imp.load_module('setup', *imp.find_module('setup', ['.']))

        # dirty hack to allow "empty" dirs
        for base, _path, files in os.walk('./'):
            for filename in files:
                if filename == 'empty':
                    os.remove(os.path.join(base, filename))

        if opts.skip_genshi or opts.mako or opts.kajiki or opts.jinja:
            # remove existing template files
            package_template_dir = os.path.abspath(os.path.join(opts.package,
                'templates'))
            shutil.rmtree(package_template_dir, ignore_errors=True)

        # copy over the alternative templates if appropriate
        if opts.mako or opts.kajiki or opts.jinja:
            def overwrite_templates(template_type):
                print('Writing %s template files to ./%s' % (
                    template_type, os.path.join(opts.package, 'templates')))
                # replace template files with alternative ones
                alt_template_dir = os.path.join(devtools_path,
                    'commands', 'quickstart_%s' % template_type)
                shutil.copytree(alt_template_dir, package_template_dir)

            if opts.mako:
                overwrite_templates('mako')
            elif opts.jinja:
                overwrite_templates('jinja')
            elif opts.kajiki:
                overwrite_templates('kajiki')

        if opts.ming:
            print('Writing Ming model files to ./%s' % os.path.join(
                opts.package, 'model'))
            package_model_dir = os.path.abspath(os.path.join(opts.package,
                'model'))
            ming_model_dir = os.path.join(devtools_path,
                'commands', 'model_ming')
            shutil.copy(os.path.join(ming_model_dir, 'session.py'),
                package_model_dir)

        if not opts.migrations:
            print('Disabling migrations support')
            # remove existing migrations directory
            package_migrations_dir = os.path.abspath('migration')
            shutil.rmtree(package_migrations_dir, ignore_errors=True)
