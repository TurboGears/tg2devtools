import gettext
import os
import shutil
import subprocess
import sys
import site
import tempfile
import unittest

from webtest import TestApp
from itertools import count
from venv import EnvBuilder
from tg.util import Bunch

from devtools.gearbox.quickstart import QuickstartCommand
from devtools.gearbox.quickstart.command import QuickstartAPICommand
from gearbox.commands.setup_app import SetupAppCommand


PY_VERSION = sys.version_info[:2]
PROJECT_NAME = 'TGTest-%02d'
ENV_NAME = 'TESTENV'
CLEANUP = True
COUNTER = count()
QUIET = '-q'  # Set this to -v to enable installed packages logging, or to -q to disable it


def get_passed_and_failed(env_cmd, python_cmd, testpath):
    """Run test suite under testpath, return set of passed tests."""
    os.chdir(testpath)
    args = '. %s; %s -W ignore -mpytest -v --no-header --no-summary' % (env_cmd, python_cmd)
    out = subprocess.Popen(args,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT,
                           shell=True, encoding="utf-8").communicate()[0]
    passed, failed = [], []
    lines = out.splitlines()
    for line in lines:
        test = None
        line = line.split(' ', 1)
        if line[0].startswith('tgtest'):
            test = line[0]
        if test and len(line) == 2:
            line[1] = line[1].split()[0].strip()
            if line[1] in ('passed', 'PASSED'):
                passed.append(test)
                test = None
            elif line[1] in ('ERROR', 'FAILED'):
                failed.append(test)
                test = None
    return passed, failed, lines


class TestQuickstartGeneration(unittest.TestCase):

    def setUp(self):
        self.command = QuickstartCommand(None, {})
        self.parser = self.command.get_parser('tg2devtools-test')

    def quickstart(self, *args):
        old_cwd = os.getcwd()
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        os.chdir(tmpdir.name)
        self.addCleanup(os.chdir, old_cwd)

        opts = self.parser.parse_args(list(args) + ['ModernApp'])
        self.command.run(opts)
        return os.path.join(tmpdir.name, 'ModernApp'), 'modernapp'

    def test_default_generates_modern_kajiki_sqlalchemy_demo(self):
        project_dir, package = self.quickstart()

        with open(os.path.join(project_dir, package, 'controllers', 'root.py')) as f:
            root = f.read()
        with open(os.path.join(project_dir, package, 'controllers', 'demo.py')) as f:
            demo = f.read()
        with open(os.path.join(project_dir, package, 'model', 'todo.py')) as f:
            todo = f.read()
        with open(os.path.join(project_dir, package, 'templates', 'master.xhtml')) as f:
            master = f.read()
        with open(os.path.join(project_dir, package, 'templates', 'demo', 'index.xhtml')) as f:
            demo_template = f.read()
        with open(os.path.join(project_dir, package, 'templates', 'demo', 'todo_list.xhtml')) as f:
            todo_template = f.read()
        with open(os.path.join(project_dir, package, 'templates', 'demo', 'protected.xhtml')) as f:
            protected_template = f.read()
        with open(os.path.join(project_dir, package, 'tests', 'functional', 'test_root.py')) as f:
            root_tests = f.read()
        with open(os.path.join(project_dir, package, 'tests', 'functional', 'test_demo.py')) as f:
            demo_tests = f.read()
        with open(os.path.join(project_dir, 'pyproject.toml')) as f:
            pyproject = f.read()
        with open(os.path.join(project_dir, 'test.ini')) as f:
            test_ini = f.read()

        self.assertIn('redirect(\'/demo\')', root)
        self.assertIn("request.identity['user']", root)
        self.assertNotIn("request.identity['repoze.who.userid']", root)
        self.assertIn(f"@expose('{package}.templates.demo.index')", demo)
        self.assertIn(f"@expose('{package}.templates.demo.todo_list')", demo)
        self.assertIn(f"@expose('{package}.templates.demo.protected')", demo)
        self.assertIn('return self._todo_data()\n\n    @expose', demo)
        self.assertIn('@validate(error_handler=todos)', demo)
        self.assertIn('def add(self, title: str):', demo)
        self.assertNotIn('priority', demo.lower())
        self.assertIn('def toggle(self, todo_id: int, done: bool = False):', demo)
        self.assertIn('DBSession.query(TodoItem).filter_by(id=todo_id).first()', demo)
        self.assertNotIn('DBSession.get(TodoItem, todo_id)', demo)
        self.assertIn("class TodoItem", todo)
        self.assertNotIn('priority', todo.lower())
        self.assertIn('cdn.jsdelivr.net/npm/bootstrap@5.3.3', master)
        self.assertIn('unpkg.com/htmx.org', master)
        self.assertIn('href="https://www.turbogears.org/"', master)
        self.assertIn('href="https://kajiki.readthedocs.io/"', master)
        self.assertIn('href="https://getbootstrap.com/"', master)
        self.assertIn('href="https://htmx.org/"', master)
        self.assertIn('class="navbar-brand" href="${tg.url(\'/\')}"', master)
        self.assertIn(f'tmpl_context.project_name = "{package}"', demo)
        self.assertIn('Create your own actions, controllers, templates, and models', demo_template)
        self.assertIn('<code>templates/demo/</code>', demo_template)
        self.assertIn('rm -rf controllers/demo.py model/todo.py templates/demo tests/functional/test_demo.py', demo_template)
        self.assertIn('gearbox patch controllers/root.py DemoController -d', demo_template)
        self.assertIn('gearbox patch controllers/root.py "redirect(\'/demo\')" -r "return \'Hello World\'"', demo_template)
        self.assertIn('gearbox patch model/__init__.py TodoItem -d', demo_template)
        self.assertNotIn('and the demo templates', demo_template)
        self.assertNotIn('This quickstart is a small Kajiki-only', demo_template)
        self.assertIn('py:extends="master.xhtml"', demo_template)
        self.assertIn('href="demo/todo_list.xhtml"', demo_template)
        self.assertIn('py:extends="master.xhtml"', protected_template)
        self.assertIn('class="row g-4"', demo_template)
        self.assertIn('class="col-lg-5"', demo_template)
        self.assertIn('class="col-lg-7"', demo_template)
        self.assertIn('name="title"', todo_template)
        self.assertNotIn('priority', todo_template.lower())
        self.assertIn('test_index_redirects_to_demo', root_tests)
        self.assertNotIn('test_todo_demo_stores_items', root_tests)
        self.assertIn('class TestDemoController', demo_tests)
        self.assertIn('test_todo_demo_stores_items', demo_tests)
        self.assertIn('test_todo_demo_toggles_done_state', demo_tests)
        self.assertIn('test_protected_demo_with_manager', demo_tests)
        self.assertNotIn('priority', demo_tests.lower())
        self.assertIn('"TurboGears2 >= 2.5.1dev1"', pyproject)
        self.assertIn('sqlalchemy.url = sqlite:///:memory:', test_ini)
        self.assertTrue(os.path.exists(os.path.join(project_dir, package, 'templates', 'demo', '__init__.py')))
        self.assertTrue(os.path.exists(os.path.join(project_dir, package, 'tests', 'functional', 'test_demo.py')))
        self.assertFalse(os.path.exists(os.path.join(project_dir, package, 'controllers', 'secure.py')))
        self.assertFalse(os.path.exists(os.path.join(project_dir, package, 'templates', 'demo.xhtml')))
        self.assertFalse(os.path.exists(os.path.join(project_dir, package, 'templates', 'todo_list.xhtml')))
        self.assertFalse(os.path.exists(os.path.join(project_dir, package, 'templates', 'about.xhtml')))

    def test_api_quickstart_does_not_generate_default_routes(self):
        old_cwd = os.getcwd()
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        os.chdir(tmpdir.name)
        self.addCleanup(os.chdir, old_cwd)

        command = QuickstartAPICommand(None, {})
        parser = command.get_parser('tg2devtools-api-test')
        opts = parser.parse_args(['ModernAPI'])
        command.run(opts)

        project_dir = os.path.join(tmpdir.name, 'ModernAPI')
        with open(os.path.join(project_dir, 'modernapi', 'controllers', 'root.py')) as f:
            root = f.read()
        with open(os.path.join(project_dir, 'modernapi', 'controllers', 'api', '__init__.py')) as f:
            api = f.read()
        with open(os.path.join(project_dir, 'modernapi', 'controllers', 'demo.py')) as f:
            demo = f.read()

        fallback_name = '_' + 'default'
        generated_fallbacks = []
        for base, _dirs, files in os.walk(project_dir):
            for filename in files:
                if filename.endswith('.py'):
                    path = os.path.join(base, filename)
                    with open(path) as f:
                        if 'def %s(' % fallback_name in f.read():
                            generated_fallbacks.append(os.path.relpath(path, project_dir))

        self.assertIn('def index(self):', api)
        self.assertIn('def openapi(self):', api)
        self.assertIn('def docs(self):', api)
        self.assertNotIn('OpenAPIController', api)
        self.assertNotIn('DocsController', api)
        self.assertNotIn('DemoController', api)
        self.assertIn('demo = DemoController()', root)
        self.assertIn("request.identity['user']", root)
        self.assertNotIn("request.identity['repoze.who.userid']", root)
        self.assertIn('def admin(self, **kw):', demo)
        self.assertIn("request.identity['user'].user_name", demo)
        self.assertNotIn("request.identity['repoze.who.userid']", demo)
        self.assertNotIn('AdminController', demo)
        self.assertFalse(os.path.exists(os.path.join(project_dir, 'modernapi', 'controllers', 'api', 'openapi.py')))
        self.assertFalse(os.path.exists(os.path.join(project_dir, 'modernapi', 'controllers', 'api', 'docs.py')))
        self.assertFalse(os.path.exists(os.path.join(project_dir, 'modernapi', 'controllers', 'api', 'demo')))
        self.assertEqual([], generated_fallbacks)

    def test_nosa_omits_persistent_todo_demo(self):
        project_dir, package = self.quickstart('--nosa')

        with open(os.path.join(project_dir, package, 'controllers', 'demo.py')) as f:
            demo = f.read()
        with open(os.path.join(project_dir, package, 'model', 'todo.py')) as f:
            todo = f.read()

        self.assertNotIn('TodoItem', demo)
        self.assertNotIn('class TodoItem', todo)
        self.assertIn('has_todos=False', demo)
        self.assertFalse(os.path.exists(os.path.join(project_dir, 'migration')))

    def test_ming_generates_persistent_todo_demo(self):
        project_dir, package = self.quickstart('--ming')

        with open(os.path.join(project_dir, package, 'controllers', 'demo.py')) as f:
            demo = f.read()
        with open(os.path.join(project_dir, package, 'model', 'todo.py')) as f:
            todo = f.read()
        with open(os.path.join(project_dir, package, 'model', '__init__.py')) as f:
            model_init = f.read()
        with open(os.path.join(project_dir, package, 'tests', 'functional', 'test_demo.py')) as f:
            demo_tests = f.read()

        self.assertIn('from bson import ObjectId', demo)
        self.assertIn('def toggle(self, todo_id: str, done: bool = False):', demo)
        self.assertIn('TodoItem.query.get(_id=ObjectId(todo_id))', demo)
        self.assertIn('has_todos=True', demo)
        self.assertIn('class TodoItem(MappedClass)', todo)
        self.assertIn("name = 'todo_item'", todo)
        self.assertIn('from %s.model.todo import TodoItem' % package, model_init)
        self.assertIn('test_todo_demo_stores_items', demo_tests)
        self.assertIn('test_todo_demo_toggles_done_state', demo_tests)
        self.assertFalse(os.path.exists(os.path.join(project_dir, 'migration')))


class BaseTestQuickStart(object):

    args = ''
    preinstall = []

    @classmethod
    def setUpClass(cls):
        cls.command = QuickstartCommand(None, {})
        cls.parser = cls.command.get_parser('tg2devtools-test')

        cls.base_dir = os.getcwd()

        # All the envs must be named equally due to python not supporting
        # unloading modules, so the modules loaded on first fixture must
        # be in the same place on the next fixtures.
        cls.env_dir = os.path.join(os.path.abspath(cls.base_dir), ENV_NAME)

        # directory for executable scripts in the virtual environment
        cls.bin_dir = os.path.join(cls.env_dir,
            'Scripts' if sys.platform == 'win32' else 'bin')

        # This is to avoid previously failed tests to break successive fixtures
        shutil.rmtree(cls.env_dir, ignore_errors=True)

        # Create virtualenv for current fixture
        EnvBuilder(with_pip=True, symlinks=True).create(cls.env_dir)

        # Enable the newly created virtualenv
        cls.pip_cmd, cls.python_cmd, cls.env_cmd, site_packages = cls.enter_virtualenv()

        # Reinstall gearbox to force it being installed inside the
        # virtualenv using supported PBR version
        cls.run_pip(['install', '-U', 'setuptools', 'pip', 'wheel'])
        cls.run_pip(['install', '-I', 'git+https://github.com/TurboGears/tempita'])
        cls.run_pip(['install', '--pre', '-I', 'gearbox'])

        # Then install specific requirements
        for p in cls.preinstall:
            cls.run_pip(['install', '--pre', '-I', p])

        cls.run_pip(['install', '-I', 'git+https://github.com/TurboGears/crank'])
        cls.run_pip(['install', '-I', 'git+https://github.com/TurboGears/backlash'])
        cls.run_pip(['install', '-I', 'git+https://github.com/TurboGears/tgext.debugbar'])

        # Install TurboGears from development branch to test future compatibility
        cls.venv_uninstall('WebOb')
        cls.venv_uninstall('TurboGears2')
        cls.run_pip(['install', '--pre', '-I', 'git+https://github.com/TurboGears/tg2.git@development'])

        # Install tg.devtools inside the virtualenv
        cls.run_pip(['install', '--pre', '-e', cls.base_dir])

        # Install All Template Engines inside the virtualenv so that
        # They all get configured as we share a single python process
        # for all configurations.
        for engine in ("Jinja2", "Genshi", "make", "kajiki"):
            cls.run_pip(['install', '--upgrade', '--no-deps', '--force-reinstall',
                         '--pre', engine])

        # This is to avoid the TGTest package to be detected as
        # being already installed.
        proj_name = PROJECT_NAME % next(COUNTER)
        cls.proj_dir = os.path.join(cls.base_dir, proj_name)

        # Create a quickstarted app by runnig 'gearbox quickstart'
        opts = cls.parser.parse_args(cls.args.split() + [proj_name])
        cls.command.run(opts)

        # Install quickstarted project dependencies
        cls.run_pip(['install', '--pre', '-e', '%s[testing]' % cls.proj_dir])

        # Mark the packages as installed even outside the virtualenv
        # so we can load app in tests which are not executed inside
        # the newly created virtualenv.
        site.addsitedir(site_packages)

    def setUp(self):
        os.chdir(self.proj_dir)
        from paste.deploy import loadapp
        self.app = loadapp('config:test.ini', relative_to=self.proj_dir)
        self.app = TestApp(self.app)

    def init_database(self):
        os.chdir(self.proj_dir)
        cmd = SetupAppCommand(Bunch(options=Bunch(verbose_level=1)), Bunch())
        try:
            cmd.run(Bunch(config_file='config:test.ini', section_name=None))
        except:
            # DB already initialised, ignore it.
            pass

    @classmethod
    def tearDownClass(cls):
        # This is in case the tests have been skipped
        if not hasattr(cls, 'past_working_set_state'):
            return

        cls.exit_virtualenv()

        os.chdir(cls.base_dir)
        if CLEANUP:
            shutil.rmtree(cls.proj_dir, ignore_errors=False)
            shutil.rmtree(cls.env_dir, ignore_errors=False)

    @classmethod
    def enter_virtualenv(cls):
        cls.old_os_path = os.environ['PATH']
        os.environ['PATH'] = cls.env_dir + os.pathsep + cls.old_os_path

        base = os.path.abspath(cls.env_dir)
        site_packages = os.path.join(
            base, 'lib', 'python%s.%s' % sys.version_info[:2], 'site-packages'
        )
        cls.prev_sys_path = list(sys.path)

        cls.past_prefix = sys.prefix
        cls.past_real_prefix = getattr(sys, 'real_prefix', None)

        site.addsitedir(site_packages)
        sys.real_prefix = sys.prefix
        sys.prefix = base

        # Move the added items to the front of the path:
        new_sys_path = []
        for item in list(sys.path):
            if item not in cls.prev_sys_path:
                new_sys_path.append(item)
                sys.path.remove(item)
        sys.path[:0] = new_sys_path

        return (os.path.join(cls.bin_dir, 'pip'),
                os.path.join(cls.bin_dir, 'python'),
                os.path.join(cls.bin_dir, 'activate'),
                site_packages)

    @classmethod
    def exit_virtualenv(cls):
        os.environ['PATH'] = cls.old_os_path
        sys.path = cls.prev_sys_path
        sys.prefix = cls.past_prefix

        if cls.past_real_prefix is not None:
            sys.real_prefix = cls.past_real_prefix
        else:
            delattr(sys, 'real_prefix')

    @classmethod
    def run_pip(cls, opt):
        return subprocess.call([cls.python_cmd, '-mpip', QUIET] + opt)

    @classmethod
    def venv_uninstall(cls, package):
        # Do it 5 times to ensure it was uninstalled for real.
        # Due to the -I used in other commands,
        # multiple versions of the same package might be installed concurrently.
        for i in range(5):
            cls.run_pip(['uninstall', '-y', package])


class CommonTestQuickStart(BaseTestQuickStart):

    # tests that must be passed
    pass_tests = [
        '/tests/functional/test_authentication.',
        '/tests/functional/test_root.',
        '/tests/models/test_auth.']
    # tests that must fail (should not exist)
    fail_tests = []
    # tests that must not be run
    skip_tests = []

    def test_index(self):
        resp = self.app.get('/', status=302)
        assert resp.headers['Location'] == 'http://localhost/demo'

    def test_login(self):
        resp = self.app.get('/login')
        assert '<h1>Login</h1>' in resp

    def test_subtests(self):
        passed, failed, lines = get_passed_and_failed(self.env_cmd,
                                                      self.python_cmd,
                                                      os.path.join(self.proj_dir))
        for has_failed in failed:
            for must_fail in self.fail_tests:
                if must_fail in has_failed:
                    break
            else:
                assert False, 'Failed %s\n\n%s' % (has_failed, '\n'.join(lines))
        for must_pass in self.pass_tests:
            for has_passed in passed:
                if must_pass in has_passed:
                    break
            else:
                print("Passed:\n" + '\n'.join(passed))
                assert False, 'Did not pass %s\n\n%s' % (must_pass, '\n'.join(lines))
        for must_fail in self.fail_tests:
            for has_failed in failed:
                if must_fail in has_failed:
                    break
            else:
                print("Failed:\n" + '\n'.join(failed))
                assert False, 'Did not fail %s' % must_fail
        for must_skip in self.skip_tests:
            for has_run in passed + failed:
                if must_skip in has_run:
                    print("Run:\n" + '\n'.join(passed + failed))
                    assert False, 'Did not skip %s' % must_skip


class CommonTestQuickStartWithAuth(CommonTestQuickStart):
    def test_secured_controller(self):
        assert (
            '<h1>Login</h1>' in self.app.get('/demo/protected', status=302).follow()
        )

    def test_secured_controller_with_prefix(self):
        resp1 = self.app.get('/prefix/demo/protected', extra_environ={'SCRIPT_NAME': '/prefix'}, status=302)
        assert (
            resp1.headers['Location'] == 'http://localhost/prefix/login?came_from=%2Fprefix%2Fdemo%2Fprotected'
        ), resp1.headers['Location']
        resp2 = resp1.follow(extra_environ={'SCRIPT_NAME': '/prefix'})
        assert '/prefix/login_handler' in resp2, resp2

    def test_login_with_prefix(self):
        self.init_database()
        resp1 = self.app.post('/prefix/login_handler?came_from=%2Fprefix%2Fdemo%2Fprotected',
                              params={'login': 'manager', 'password': 'managepass'},
                              extra_environ={'SCRIPT_NAME': '/prefix'})
        assert (
            resp1.headers['Location'] == 'http://localhost/prefix/post_login?came_from=%2Fprefix%2Fdemo%2Fprotected'
        ), resp1.headers['Location']
        resp2 = resp1.follow(extra_environ={'SCRIPT_NAME': '/prefix'})
        assert (
            resp2.headers['Location'] == 'http://localhost/prefix/demo/protected'
        ), resp2.headers['Location']

    def test_login_failure_with_prefix(self):
        self.init_database()
        resp = self.app.post('/prefix/login_handler?came_from=%2Fprefix%2Fdemo%2Fprotected',
                             params={'login': 'WRONG', 'password': 'WRONG'},
                             extra_environ={'SCRIPT_NAME': '/prefix'})
        location = resp.headers['Location']
        assert 'http://localhost/prefix/login' in location, location
        assert 'came_from=%2Fprefix%2Fdemo%2Fprotected' in location, location


class TestDefaultQuickStart(CommonTestQuickStartWithAuth, unittest.TestCase):
    args = ''
    pass_tests = [
        '/tests/functional/test_authentication.',
        '/tests/functional/test_demo.py::TestDemoController::test_todo_demo_stores_items',
        '/tests/functional/test_demo.py::TestDemoController::test_todo_demo_toggles_done_state',
        '/tests/functional/test_demo.py::TestDemoController::test_protected_demo_with_manager',
        '/tests/models/test_auth.',
    ]

    @classmethod
    def setUpClass(cls):
        super(TestDefaultQuickStart, cls).setUpClass()

    def setUp(self):
        super(TestDefaultQuickStart, self).setUp()

    def test_translation_i18n_commands_create_artifacts(self):
        package = os.path.basename(self.proj_dir).lower().replace('-', '')
        pot_file = os.path.join(package, 'i18n', '%s.pot' % package)
        po_file = os.path.join(package, 'i18n', 'es', 'LC_MESSAGES', '%s.po' % package)
        mo_file = os.path.join(package, 'i18n', 'es', 'LC_MESSAGES', '%s.mo' % package)
        env = dict(os.environ, PATH=self.bin_dir + os.pathsep + os.environ['PATH'])

        def run_i18n(*args):
            result = subprocess.run(
                [os.path.join(self.bin_dir, 'gearbox'), 'i18n'] + list(args),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=300,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stdout)

        run_i18n('extract')
        with open(pot_file) as f:
            pot = f.read()
        self.assertIn('msgid "Only for managers"', pot)

        run_i18n('init', '-l', 'es')
        with open(po_file) as f:
            po = f.read()
        self.assertIn('"Language: es', po)
        self.assertIn('msgid "Only for managers"', po)

        with open(os.path.join(package, 'controllers', 'root.py'), 'a') as f:
            f.write("\nI18N_UPDATE_PROBE = l_('Added during i18n update')\n")
        run_i18n('extract')
        run_i18n('update', '-l', 'es')
        with open(po_file) as f:
            po = f.read()
        self.assertIn('msgid "Added during i18n update"', po)
        translated_po = po.replace(
            'msgid "Added during i18n update"\nmsgstr ""',
            'msgid "Added during i18n update"\nmsgstr "Agregado durante i18n update"',
        )
        self.assertNotEqual(po, translated_po)
        with open(po_file, 'w') as f:
            f.write(translated_po)

        run_i18n('compile', '-l', 'es')
        with open(mo_file, 'rb') as f:
            translations = gettext.GNUTranslations(f)
        self.assertEqual(
            translations.gettext('Added during i18n update'),
            'Agregado durante i18n update',
        )


class TestNoDBQuickStart(CommonTestQuickStart, unittest.TestCase):

    pass_tests = [
        '/tests/functional/test_demo.py::TestDemoController::test_todo_demo_is_omitted_without_sqlalchemy',
        '/tests/functional/test_demo.py::TestDemoController::test_auth_demo_is_omitted_without_auth',
    ]
    skip_tests = [
        'TestDemoController::test_todo_demo_stores_items',
        'TestDemoController::test_todo_demo_toggles_done_state',
        'TestDemoController::test_protected_demo_with_manager',
        'TestDemoController::test_protected_demo_with_editor',
        'TestDemoController::test_protected_demo_with_anonymous',
        '/tests/functional/test_authentication.',
        '/tests/models/test_auth.']

    args = '--nosa'

    def test_login(self):
        self.app.get('/login', status=404)


class TestNoAuthQuickStart(CommonTestQuickStart, unittest.TestCase):

    pass_tests = [
        '/tests/functional/test_demo.py::TestDemoController::test_todo_demo_stores_items',
        '/tests/functional/test_demo.py::TestDemoController::test_todo_demo_toggles_done_state',
        '/tests/functional/test_demo.py::TestDemoController::test_auth_demo_is_omitted_without_auth',
    ]
    skip_tests = [
        'TestDemoController::test_protected_demo_with_manager',
        'TestDemoController::test_protected_demo_with_editor',
        'TestDemoController::test_protected_demo_with_anonymous',
        '/tests/functional/test_authentication.',
        '/tests/models/test_auth.']

    args = '--noauth'

    @classmethod
    def setUpClass(cls):
        super(TestNoAuthQuickStart, cls).setUpClass()

    def setUp(self):
        super(TestNoAuthQuickStart, self).setUp()

    def test_login(self):
        self.app.get('/login', status=404)


class TestMingBQuickStart(CommonTestQuickStartWithAuth, unittest.TestCase):

    args = '--ming'
    pass_tests = [
        '/tests/functional/test_authentication.',
        '/tests/functional/test_demo.py::TestDemoController::test_todo_demo_stores_items',
        '/tests/functional/test_demo.py::TestDemoController::test_todo_demo_toggles_done_state',
        '/tests/functional/test_demo.py::TestDemoController::test_protected_demo_with_manager',
        '/tests/models/test_auth.',
    ]
    # preinstall = ['Paste', 'PasteScript']  # Ming doesn't require those anymore

    @classmethod
    def setUpClass(cls):
        super(TestMingBQuickStart, cls).setUpClass()

    def setUp(self):
        super(TestMingBQuickStart, self).setUp()
