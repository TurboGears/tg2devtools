import os
import shutil
import subprocess
import sys
import site
import pkg_resources
import re

from nose.tools import ok_
from webtest import TestApp
from itertools import count
from nose import SkipTest
from virtualenv import create_environment
from tg.util import Bunch

from devtools.gearbox.quickstart import QuickstartCommand
from gearbox.commands.setup_app import SetupAppCommand


PY_VERSION = sys.version_info[:2]
PY2 = sys.version_info[0] == 2
PROJECT_NAME = 'TGTest-%02d'
ENV_NAME = 'TESTENV'
CLEANUP = True
COUNTER = count()
QUIET = '-q'  # Set this to -v to enable installed packages logging, or to -q to disable it


def run_pytest(env_cmd, testpath):
    """Run test suite under testpath, return set of passed tests."""
    result = {'errors': 0, 'failed': 0, 'out': b'', 'coverage': {'passed': 0, 'missing': 0, 'cover': 0}}
    os.chdir(testpath)
    args = '. %s; pytest' % env_cmd
    print('running tests %s' % testpath)
    out = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
    ).communicate()[0]
    result['out'] = out = out.decode('utf-8')
    assert out[0]  # faster than calculating len of out that should be > 0
    # print('pytest output:')
    # print(out)

    cov_pattern = re.compile(r'TOTAL\W*(\d*)\W*(\d*)\W*(\d*)')
    for line in out.splitlines()[::-1]:
        match = cov_pattern.match(line)
        if match:
            break
    else:
        raise Exception('no coverage output found. output: %s' % out)
    result['coverage']['line'] = match.group(0)
    result['coverage']['passed'] = match.group(1)
    result['coverage']['missing'] = match.group(2)
    result['coverage']['cover'] = match.group(3)

    # detecting number of errors and failed tests from short summary
    try:
        summary = out[out.index('short test summary info'):]
    except ValueError:
        summary = ''
    lines = summary.splitlines()
    for line in lines:
        if 'ERROR' in line:
            result['errors'] += 1
        elif 'FAIL' in line:
            result['failed'] += 1

    return result


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
        print('creating virtual environment in %s' % cls.env_dir)
        # if you get errors about setuptools, maybe you made an error in command.py
        create_environment(cls.env_dir)

        # Enable the newly created virtualenv
        cls.pip_cmd, cls.python_cmd, cls.env_cmd, site_packages = cls.enter_virtualenv()

        # Reinstall gearbox to force it being installed inside the
        # virtualenv using supported PBR version
        subprocess.call([cls.pip_cmd, QUIET, 'install', '-U', 'setuptools==18.0.1'])
        subprocess.call([cls.pip_cmd, QUIET, 'install', '-U', 'pip'])
        subprocess.call([cls.pip_cmd, QUIET, 'install', '--pre', '-I', 'gearbox'])

        # Dependencies required to run tests of a TGApp, as
        # we run them with python setup.py test that is unable
        # download dependencies on systems without TLS1.2 support.
        subprocess.call([cls.pip_cmd, QUIET, 'install', '--pre', '-I', 'coverage'])
        subprocess.call([cls.pip_cmd, QUIET, 'install', '--pre', '-I', 'pytest'])
        subprocess.call([cls.pip_cmd, QUIET, 'install', '--pre', '-I', 'pytest-cov'])
        subprocess.call([cls.pip_cmd, QUIET, 'install', '--pre', '-I', 'webtest'])

        # Then install specific requirements
        for p in cls.preinstall:
            subprocess.call([cls.pip_cmd, QUIET, 'install', '--pre', '-I', p])

        subprocess.call([cls.pip_cmd, QUIET, 'install', '-I', 'git+git://github.com/TurboGears/crank.git'])
        subprocess.call([cls.pip_cmd, QUIET, 'install', '-I', 'git+git://github.com/TurboGears/backlash.git'])
        subprocess.call([cls.pip_cmd, QUIET, 'install', '-I', 'git+git://github.com/TurboGears/tgext.debugbar.git'])

        # Install TurboGears from development branch to test future compatibility
        cls.venv_uninstall('WebOb')
        cls.venv_uninstall('TurboGears2')
        subprocess.call([cls.pip_cmd, QUIET, 'install', '--pre', '-I', 'git+git://github.com/TurboGears/tg2.git@development'])

        # Install tg.devtools inside the virtualenv
        subprocess.call([cls.pip_cmd, QUIET, 'install', '--pre', '-e', cls.base_dir + '[testing]'])

        # Install All Template Engines inside the virtualenv so that
        # They all get configured as we share a single python process
        # for all configurations.
        subprocess.call([cls.pip_cmd, QUIET, 'install', '--upgrade', '--no-deps', '--force-reinstall', '--pre', 'Jinja2'])
        subprocess.call([cls.pip_cmd, QUIET, 'install', '--upgrade', '--no-deps', '--force-reinstall', '--pre', 'Genshi'])
        subprocess.call([cls.pip_cmd, QUIET, 'install', '--upgrade', '--no-deps', '--force-reinstall', '--pre', 'mako'])
        subprocess.call([cls.pip_cmd, QUIET, 'install', '--upgrade', '--no-deps', '--force-reinstall', '--pre', 'kajiki'])

        # This is to avoid the TGTest package to be detected as
        # being already installed.
        proj_name = PROJECT_NAME % next(COUNTER)
        cls.proj_dir = os.path.join(cls.base_dir, proj_name)

        # Create a quickstarted app by runnig 'gearbox quickstart'
        opts = cls.parser.parse_args(cls.args.split() + [proj_name])
        cls.command.run(opts)

        # Install quickstarted project dependencies
        subprocess.call([cls.pip_cmd, QUIET, 'install', '--pre', '-e', cls.proj_dir])

        # Mark the packages as installed even outside the virtualenv
        # so we can load app in tests which are not executed inside
        # the newly created virtualenv.
        site.addsitedir(site_packages)
        cls.past_working_set_state = pkg_resources.working_set.__getstate__()
        pkg_resources.working_set.add_entry(site_packages)
        pkg_resources.working_set.add_entry(cls.proj_dir)

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
    def venv_uninstall(cls, package):
        # Do it 5 times to ensure it was uninstalled for real.
        # Due to the -I used in other commands,
        # multiple versions of the same package might be installed concurrently.
        for i in range(5):
            subprocess.call([cls.pip_cmd, 'uninstall', '-y', package])


class CommonTestQuickStart(BaseTestQuickStart):
    def test_quickstarted_tests(self):
        result = run_pytest(
            self.env_cmd, os.path.join(self.proj_dir)
        )
        if result['failed'] + result['errors'] != 0:
            print(result['out'])
            assert False, (result['failed'], result['errors'])
        if result['coverage']['passed'] == 0:
            assert False, result['coverage']
        if result['coverage']['missing'] == 0:
            assert False, result['coverage']
        if result['coverage']['cover'] == 100:
            assert False, result['coverage']


class TestDefaultQuickStart(CommonTestQuickStart):
    args = ''


class TestMakoQuickStart(CommonTestQuickStart):
    args = '--mako --nosa --noauth --skip-tw'


class TestGenshiQuickStart(CommonTestQuickStart):
    args = '--genshi --nosa --noauth --skip-tw'

class TestJinjaQuickStart(CommonTestQuickStart):
    args = '--jinja --nosa --noauth --skip-tw'


class TestNoDBQuickStart(CommonTestQuickStart):
    args = '--nosa --noauth --skip-tw'


class TestNoAuthQuickStart(CommonTestQuickStart):
    args = '--noauth'


class TestMingBQuickStart(CommonTestQuickStart):
    args = '--ming'


class TestNoTWQuickStart(CommonTestQuickStart):
    args = '--skip-tw'


class TestMinimalQuickStart(CommonTestQuickStart):
    args = '--minimal-quickstart'
