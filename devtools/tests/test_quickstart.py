import os
import shutil
import subprocess
import sys
from nose.tools import ok_
import pkg_resources
from webtest import TestApp
from itertools import count
from nose import SkipTest
from virtualenv import create_environment
import site

from devtools.gearbox.quickstart import QuickstartCommand

PY_VERSION = sys.version_info[:2]
PY2 = sys.version_info[0] == 2
PROJECT_NAME = 'TGTest-%02d'
ENV_NAME = 'TESTENV'
CLEANUP = True
COUNTER = count()


def get_passed_and_failed(env_cmd, python_cmd, testpath):
    """Run test suite under testpath, return set of passed tests."""
    os.chdir(testpath)
    args = '. %s; %s -W ignore setup.py test' % (env_cmd, python_cmd)
    out = subprocess.Popen(args, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True).communicate()[1]
    passed, failed = [], []
    test = None
    for line in out.splitlines():
        line = line.decode('utf-8').split(' ... ', 1)
        if line[0].startswith('tgtest'):
            test = line[0]
        if test and len(line) == 2:
            if line[1] in ('ok', 'OK'):
                passed.append(test)
                test = None
            elif line[1] in ('ERROR', 'FAIL'):
                failed.append(test)
                test = None
    return passed, failed


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
        create_environment(cls.env_dir)

        # Enable the newly created virtualenv
        cls.pip_cmd, cls.python_cmd, cls.env_cmd, site_packages = cls.enter_virtualenv()

        # Reinstall gearbox to force it being installed inside the
        # virtualenv using supported PBR version
        subprocess.call([cls.pip_cmd, '-q', 'install', '--pre', '-I', 'gearbox'])
        for p in cls.preinstall:
            subprocess.call([cls.pip_cmd, '-q', 'install', '--pre', '-I', p])

        # Install TurboGears from development branch to test future compatibility
        subprocess.call([cls.pip_cmd, '-q', 'install', '-I', 'git+git://github.com/TurboGears/crank.git'])
        subprocess.call([cls.pip_cmd, '-q', 'install', '-I', 'git+git://github.com/TurboGears/backlash.git'])
        subprocess.call([cls.pip_cmd, '-q', 'install', '-I', 'git+git://github.com/TurboGears/tg2.git@next'])

        # Install tg.devtools inside the virtualenv
        subprocess.call([cls.pip_cmd, '-q', 'install', '--pre', '-e', cls.base_dir])

        # Install All Template Engines inside the virtualenv so that
        # They all get configured as we share a single python process
        # for all configurations.
        if PY_VERSION == (3, 2):
            jinja_version = 'Jinja2 < 2.7'
        else:
            jinja_version = 'Jinja2'
        subprocess.call([cls.pip_cmd, '-q', 'install', '--pre', jinja_version])
        subprocess.call([cls.pip_cmd, '-q', 'install', '--pre', 'Genshi'])
        subprocess.call([cls.pip_cmd, '-q', 'install', '--pre', 'mako'])

        # This is to avoid the TGTest package to be detected as
        # being already installed.
        proj_name = PROJECT_NAME % next(COUNTER)
        cls.proj_dir = os.path.join(cls.base_dir, proj_name)

        # Create a quickstarted app by runnig 'gearbox quickstart'
        opts = cls.parser.parse_args(cls.args.split() + [proj_name])
        cls.command.run(opts)

        # Install quickstarted project dependencies
        subprocess.call([cls.pip_cmd, '-q', 'install', '--pre', '-e', cls.proj_dir])

        # Mark the packages as installed even outside the virtualenv
        # so we can load app in tests which are not executed inside
        # the newly created virtualenv.
        site.addsitedir(site_packages)
        cls.past_working_set_state = pkg_resources.working_set.__getstate__()
        pkg_resources.working_set.add_entry(site_packages)
        pkg_resources.working_set.add_entry(cls.proj_dir)

    def setUp(self):
        os.chdir(self.proj_dir)

        from paste.deploy import loadapp
        self.app = loadapp('config:test.ini', relative_to=self.proj_dir)
        self.app = TestApp(self.app)

    @classmethod
    def tearDownClass(cls):
        # This is in case the tests have been skipped
        if not hasattr(cls, 'past_working_set_state'):
            return

        pkg_resources.working_set.__setstate__(cls.past_working_set_state)
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
        site_packages = os.path.join(base, 'lib', 'python%s' % sys.version[:3], 'site-packages')
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

        return  (os.path.join(cls.bin_dir, 'pip'),
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


class CommonTestQuickStart(BaseTestQuickStart):

    # tests that must be passed
    pass_tests = [
        '.tests.functional.test_authentication.',
        '.tests.functional.test_root.',
        '.tests.models.test_auth.']
    # tests that must fail (should not exist)
    fail_tests = []
    # tests that must not be run
    skip_tests = []

    def test_index(self):
        resp = self.app.get('/')
        ok_('Welcome to TurboGears' in resp, resp)

    def test_login(self):
        resp = self.app.get('/login')
        ok_('<h1>Login</h1>' in resp)

    def test_unauthenticated_admin(self):
        ok_('<h1>Login</h1>'
            in self.app.get('/admin/', status=302).follow())

    def test_subtests(self):
        passed, failed = get_passed_and_failed(self.env_cmd, self.python_cmd, os.path.join(self.proj_dir))
        for has_failed in failed:
            for must_fail in self.fail_tests:
                if must_fail in has_failed:
                    break
            else:
                ok_(False, 'Failed %s' % has_failed)
        for must_pass in self.pass_tests:
            for has_passed in passed:
                if must_pass in has_passed:
                    break
            else:
                print("Passed:\n" + '\n'.join(passed))
                ok_(False, 'Did not pass %s' % must_pass)
        for must_fail in self.fail_tests:
            for has_failed in failed:
                if must_fail in has_failed:
                    break
            else:
                print("Failed:\n" + '\n'.join(failed))
                ok_(False, 'Did not fail %s' % must_fail)
        for must_skip in self.skip_tests:
            for has_run in passed + failed:
                if must_skip in has_run:
                    print("Run:\n" + '\n'.join(passed + failed))
                    ok_(False, 'Did not skip %s' % must_skip)


class TestDefaultQuickStart(CommonTestQuickStart):
    args = ''

    @classmethod
    def setUpClass(cls):
        super(TestDefaultQuickStart, cls).setUpClass()

    def setUp(self):
        super(TestDefaultQuickStart, self).setUp()


class TestMakoQuickStart(CommonTestQuickStart):
    args = '--mako --nosa --noauth --skip-tw'

    pass_tests = ['.tests.functional.test_root.']
    skip_tests = [
        '.tests.functional.test_root.test_secc',
        '.tests.functional.test_authentication.',
        '.tests.models.test_auth.']

    def test_login(self):
        self.app.get('/login', status=404)

    def test_unauthenticated_admin(self):
        self.app.get('/admin', status=404)


class TestJinjaQuickStart(CommonTestQuickStart):
    args = '--jinja --nosa --noauth --skip-tw'

    pass_tests = ['.tests.functional.test_root.']
    skip_tests = [
        '.tests.functional.test_root.test_secc',
        '.tests.functional.test_authentication.',
        '.tests.models.test_auth.']

    def test_login(self):
        self.app.get('/login', status=404)

    def test_unauthenticated_admin(self):
        self.app.get('/admin', status=404)


class TestNoDBQuickStart(CommonTestQuickStart):

    pass_tests = ['.tests.functional.test_root.']
    skip_tests = [
        '.tests.functional.test_root.test_secc',
        '.tests.functional.test_authentication.',
        '.tests.models.test_auth.']

    args = '--nosa --noauth --skip-tw'

    def test_login(self):
        self.app.get('/login', status=404)

    def test_unauthenticated_admin(self):
        self.app.get('/admin', status=404)


class TestNoAuthQuickStart(CommonTestQuickStart):

    pass_tests = ['.tests.functional.test_root.']
    skip_tests = [
        '.tests.functional.test_root.test_secc',
        '.tests.functional.test_authentication.',
        '.tests.models.test_auth.']

    args = '--noauth'

    @classmethod
    def setUpClass(cls):
        super(TestNoAuthQuickStart, cls).setUpClass()

    def setUp(self):
        super(TestNoAuthQuickStart, self).setUp()

    def test_login(self):
        self.app.get('/login', status=404)

    def test_unauthenticated_admin(self):
        self.app.get('/admin', status=404)


class TestMingBQuickStart(CommonTestQuickStart):

    args = '--ming'
    # preinstall = ['Paste', 'PasteScript']  # Ming doesn't require those anymore

    @classmethod
    def setUpClass(cls):
        super(TestMingBQuickStart, cls).setUpClass()

    def setUp(self):
        super(TestMingBQuickStart, self).setUp()


class TestNoTWQuickStart(CommonTestQuickStart):

    args = '--skip-tw'

    def test_unauthenticated_admin(self):
        self.app.get('/admin', status=404)
