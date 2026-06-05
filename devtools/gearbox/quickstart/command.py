import re
import os
import shutil
import uuid
import importlib.metadata
import importlib.util


from gearbox.template import GearBoxTemplate
from gearbox.command import Command

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
        vars['template_engine'] = 'kajiki'

        if vars['migrations']:
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

        return parser

    def take_action(self, opts):
        opts.egg_plugins = []

        if opts.no_sqlalchemy:
            opts.sqlalchemy = False
            if not opts.ming:
                opts.migrations = False

        if opts.ming:
            opts.sqlalchemy = False
            opts.migrations = False

        if opts.no_auth or (opts.no_sqlalchemy and not opts.ming):
            opts.auth = False

        if not opts.package:
            package = opts.name.lower()
            package = beginning_letter.sub("", package)
            package = valid_only.sub("", package)
            opts.package = package

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

        opts.name = safe_name(opts.name)
        opts.project = opts.name

        try:
            importlib.metadata.metadata(opts.name)
        except importlib.metadata.PackageNotFoundError:
            pass
        else:
            print('The name "%s" is already in use' % opts.name)

        try:
            if importlib.util.find_spec(opts.package):
                print('The package name "%s" is already in use'
                    % opts.package)
                return
        except ImportError:
            pass

        if os.path.exists(opts.name):
            print('A directory called "%s" already exists. Exiting.'
                % opts.name)
            return

        opts.cookiesecret = str(uuid.uuid4())
        opts.passwordsalt = str(uuid.uuid4())

        quickstart_path = os.path.os.path.abspath(os.path.dirname(__file__))

        # Workaround for templates ported from Paste
        # which check for 'True' instead of True
        template_vars = dict(vars(opts))
        #for key, value in template_vars.items():
        #    if value is True:
        #        template_vars[key] = 'True'

        QuickstartTemplate().run(os.path.join(quickstart_path, 'template'),
                                 opts.name, template_vars)

        os.chdir(opts.name)
        print("")

        # dirty hack to allow "empty" dirs
        for base, _path, files in os.walk('./'):
            for filename in files:
                if filename == 'empty':
                    os.remove(os.path.join(base, filename))

        package_template_dir = os.path.abspath(os.path.join(opts.package, 'templates'))
        alt_template_dir = os.path.join(quickstart_path, 'patches', 'quickstart_kajiki')
        print('Writing kajiki template files to ./%s' % os.path.join(opts.package, 'templates'))
        shutil.rmtree(package_template_dir)
        shutil.copytree(alt_template_dir, package_template_dir)

        if opts.ming:
            print('Writing Ming model files to ./%s' % os.path.join(
                opts.package, 'model'))
            package_model_dir = os.path.abspath(os.path.join(opts.package, 'model'))
            ming_model_dir = os.path.join(quickstart_path, 'patches', 'model_ming')
            shutil.copy(os.path.join(ming_model_dir, 'session.py'),
                package_model_dir)

        if not opts.migrations:
            print('Disabling migrations support')
            # remove existing migrations directory
            package_migrations_dir = os.path.abspath('migration')
            shutil.rmtree(package_migrations_dir, ignore_errors=True)


def safe_name(name: str) -> str:
    """Convert an arbitrary string to a standard distribution name

    from setuptools.pkg_resources.safe_name
    """
    return re.sub('[^A-Za-z0-9.]+', '-', name)
