import os
import shutil
import subprocess
import sys
from nose.tools import ok_
import pkg_resources
from paste.deploy import loadapp
from webtest import TestApp
from itertools import count
from nose import SkipTest

from devtools.gearbox.quickstart import QuickstartCommand

PY2 = sys.version_info[0] == 2
PROJECT_NAME = 'TGTest-%02d'
CLEANUP = True
COUNTER = count()


def get_passed_and_failed(testpath):
    """Run test suite under testpath, return set of passed tests."""
    os.chdir(testpath)
    args = 'python -W ignore setup.py test'.split()
    out = subprocess.Popen(args, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE).communicate()[1]
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

    def __init__(self, **options):
        self.command = QuickstartCommand(None, {})
        self.parser = self.command.get_parser('tg2devtools-test')

        self.base_dir = os.getcwd()

    def setUp(self):
        os.chdir(self.base_dir)

        # This is to avoid the TGTest package to be detected as
        # being already installed.
        proj_name = PROJECT_NAME % next(COUNTER)
        self.proj_dir = os.path.join(self.base_dir, proj_name)

        opts = self.parser.parse_args(self.args.split() + [proj_name])
        self.command.run(opts)

        # Mark the packages as installed so we can load app
        pkg_resources.working_set.add_entry(self.proj_dir)

        os.chdir(self.proj_dir)
        self.app = loadapp('config:test.ini', relative_to=self.proj_dir)
        self.app = TestApp(self.app)

    def tearDown(self):
        os.chdir(self.base_dir)
        if CLEANUP:
            shutil.rmtree(self.proj_dir, ignore_errors=False)


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
        ok_('<div id="loginform">' in resp)

    def test_unauthenticated_admin(self):
        ok_('<div id="loginform">'
            in self.app.get('/admin/', status=302).follow())

    def test_subtests(self):
        passed, failed = get_passed_and_failed(os.path.join(self.proj_dir))
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

    def setUp(self):
        if not PY2:
            raise SkipTest('Skipping Test, admin not available on Py3')
        super(TestDefaultQuickStart, self).setUp()


class TestMakoQuickStart(CommonTestQuickStart):
    args = '--mako --nosa --noauth'

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
    args = '--jinja --nosa --noauth'

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

    args = '--nosa --noauth'

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

    def setUp(self):
        if not PY2:
            raise SkipTest('Skipping Test, admin not available on Py3')
        super(TestNoAuthQuickStart, self).setUp()

    def test_login(self):
        self.app.get('/login', status=404)

    def test_unauthenticated_admin(self):
        self.app.get('/admin', status=404)


class TestMingBQuickStart(CommonTestQuickStart):

    args = '--ming'

    def setUp(self):
        if not PY2:
            raise SkipTest('Skipping Test, admin not available on Py3')
        super(TestMingBQuickStart, self).setUp()


class TestNoTWQuickStart(CommonTestQuickStart):

    args = '--skip-tw'

    def test_unauthenticated_admin(self):
        self.app.get('/admin', status=404)
