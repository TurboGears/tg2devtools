from __future__ import print_function

import re
import pkg_resources
import os
import shutil
import sys
import glob

from gearbox.template import GearBoxTemplate
from gearbox.command import Command

PY3 = sys.version_info[0] == 3
PYVERSION = sys.version_info[:2]
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

        if vars['genshi']:
            vars['template_engine'] = 'genshi'
        elif vars['jinja']:
            vars['template_engine'] = 'jinja'
        elif vars['mako']:
            vars['template_engine'] = 'mako'
        elif vars['kajiki']:
            vars['template_engine'] = 'kajiki'

        template_engine = vars.setdefault('template_engine', 'kajiki')

        if template_engine == 'mako':
            # Support a Babel extractor default for Mako
            vars['babel_templates_extractor'] = ("('templates/**.mako',"
                " 'mako', None),\n%s#%s") % (' ' * 4, ' ' * 8)
        else:
            vars['babel_templates_extractor'] = ''

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
            action="store_true", dest="kajiki",
            default=True)

        parser.add_argument("-g", "--genshi",
            help="default templates genshi",
            action="store_true", dest="genshi")

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

        parser.add_argument("--skip-default-template",
            help="Disables Kajiki default templates",
            action="store_true", dest="skip_default_tmpl", default=False)

        parser.add_argument("--minimal-quickstart",
            help="Throw away example boilerplate from quickstart project",
            action="store_true", dest="minimal_quickstart", default=False)

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

        if opts.skip_default_tmpl:
            opts.kajiki = False

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
        template_vars['PYVERSION'] = PYVERSION
        QuickstartTemplate().run(os.path.join(devtools_path, 'templates', 'turbogears'),
                                 opts.name, template_vars)

        os.chdir(opts.name)

        sys.argv = ['setup.py', 'egg_info']
        imp.load_module('setup', *imp.find_module('setup', ['.']))

        print("")

        # dirty hack to allow "empty" dirs
        for base, _path, files in os.walk('./'):
            for filename in files:
                if filename == 'empty':
                    os.remove(os.path.join(base, filename))

        if opts.mako or opts.genshi or opts.jinja or opts.kajiki:
            package_template_dir = os.path.abspath(os.path.join(opts.package, 'templates'))
            def overwrite_templates(template_type):
                print('Writing %s template files to ./%s' % (
                    template_type, os.path.join(opts.package, 'templates')
                ))
                # replace template files with alternative ones
                alt_template_dir = os.path.join(devtools_path, 'commands',
                                                'quickstart_%s' % template_type)
                shutil.rmtree(package_template_dir)
                shutil.copytree(alt_template_dir, package_template_dir)

            if opts.genshi:
                overwrite_templates('genshi')
            elif opts.jinja:
                overwrite_templates('jinja')
            elif opts.mako:
                overwrite_templates('mako')
            elif opts.kajiki:
                overwrite_templates('kajiki')

        if opts.kajiki:
            # Provide Kajiki as a lingua franca for pluggable apps.
            print('Adding Kajiki master for pluggable apps')
            package_template_dir = os.path.abspath(os.path.join(opts.package, 'templates'))
            alt_template_dir = os.path.join(devtools_path, 'commands', 'quickstart_kajiki')
            shutil.copy(os.path.join(alt_template_dir, 'master.xhtml'),
                        package_template_dir)

        if opts.minimal_quickstart:
            print('Minimal Quickstart requested, throwing away example parts')
            package_controllers_dir = os.path.abspath(os.path.join(opts.package, 'controllers'))
            os.unlink(next(glob.iglob(os.path.join(package_controllers_dir, 'secure.py'))))

            package_template_dir = os.path.abspath(os.path.join(opts.package, 'templates'))
            os.unlink(next(glob.iglob(os.path.join(package_template_dir, 'data.*'))))
            os.unlink(next(glob.iglob(os.path.join(package_template_dir, 'environ.*'))))
            os.unlink(next(glob.iglob(os.path.join(package_template_dir, 'about.*'))))

        if opts.ming:
            print('Writing Ming model files to ./%s' % os.path.join(
                opts.package, 'model'))
            package_model_dir = os.path.abspath(os.path.join(opts.package, 'model'))
            ming_model_dir = os.path.join(devtools_path,
                'commands', 'model_ming')
            shutil.copy(os.path.join(ming_model_dir, 'session.py'),
                package_model_dir)

        if not opts.migrations:
            print('Disabling migrations support')
            # remove existing migrations directory
            package_migrations_dir = os.path.abspath('migration')
            shutil.rmtree(package_migrations_dir, ignore_errors=True)
