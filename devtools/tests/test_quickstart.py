import os, shutil, nose
import pkg_resources
from paste.deploy import loadapp
from webtest import TestApp
from itertools import count
from nose.tools import ok_

from devtools.gearbox.quickstart import QuickstartCommand

BASE_PROJECT_NAME = 'TGTest'
COUNTER = count()

class BaseTestQuickStart(object):
    def __init__(self,**options):
        self.command = QuickstartCommand(None, {})
        self.parser = self.command.get_parser('tg2devtools-test')

        self.base_dir = os.getcwd()

    def setUp(self):
        os.chdir(self.base_dir)

        # This is to avoid the TGTest package to be detected as
        # being already installed.
        proj_name = '%s-%s' % (BASE_PROJECT_NAME, next(COUNTER))
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
        shutil.rmtree(self.proj_dir, ignore_errors=False)       

class CommonTestQuickStart(BaseTestQuickStart):
    def test_index(self):
        resp = self.app.get('/')
        assert 'Welcome to TurboGears' in resp, resp

    def test_login(self):
        resp = self.app.get('/login')
        assert '<div id="loginform">' in resp

    def test_unauthenticated_admin(self):
        assert '<div id="loginform">' in self.app.get('/admin/', status=302).follow()

    def test_subtests(self):
        # Don't know if there is a better way to run
        # testsuite of the quickstarted project
        testspath = os.path.join(self.proj_dir)
        ok_(nose.run(argv=['-w', testspath]))

class TestDefaultQuickStart(CommonTestQuickStart):
    args = ''

class TestMakoQuickStart(CommonTestQuickStart):
    args = '--mako'

class TestJinjaQuickStart(CommonTestQuickStart):
    args = '--jinja'

class TestNoDBQuickStart(CommonTestQuickStart):
    args = '--nosa'

class TestNoAuthQuickStart(CommonTestQuickStart):
    args = '--noauth'

    def test_login(self):
        resp = self.app.get('/login', status=404)
        assert resp.status_code == 404, resp.status_code

    def test_unauthenticated_admin(self):
        resp = self.app.get('/admin', status=404)
        assert resp.status_code == 404, resp.status_code

class TestMingBQuickStart(CommonTestQuickStart):
    args = '--ming'

class TestNoTWQuickStart(CommonTestQuickStart):
    args = '--skip-tw'

    def test_unauthenticated_admin(self):
        resp = self.app.get('/admin', status=404)
        assert resp.status_code == 404, resp.status_code


