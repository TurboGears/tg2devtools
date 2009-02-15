from devtools.pastetemplate import TurboGearsTemplate
import os, shutil
import pkg_resources
from paste.deploy import loadapp
from webtest import TestApp
from paste.script.create_distro import CreateDistroCommand

testDataPath = os.path.join(
        os.path.abspath(os.path.dirname(__file__)),
        'data')

class MochOptions(object):
    simulate = False
    overwrite = True
    templates = ['turbogears2',]
    output_dir = testDataPath
    list_templates = False
    list_variables = False
    config = None
    inspect_files = False
    svn_repository = False

class TestQuickStart(object):
    def __init__(self,**options):
        self.app = None
        self.template_vars = {
                    'package': 'TGTest',
                    'project': 'tgtest',
                    'egg': 'tgtest',
                    'egg_plugins': ['PasteScript', 'Pylons', 'TurboGears2', 'tg.devtools'],
                    'sqlalchemy': True,
                    'sqlobject': False,
                    'elixir': False,
                    'auth': True,
                    'geo': False
        }

    def setUp(self):
        command = CreateDistroCommand('TGQuickStartUnitTest')
        command.verbose = False
        command.simulate = False
        command.options = MochOptions()
        command.interactive=False
        command.args=['TGTest',]

        proj_dir = os.path.join(testDataPath, 'TGTest')
        command.create_template(
                TurboGearsTemplate('TGTest'),
                proj_dir,
                self.template_vars)
        command.command()
        
        pkg_resources.working_set.add_entry(proj_dir)
        self.app = loadapp('config:development.ini', relative_to=proj_dir)
        self.app = TestApp(self.app)

    def tearDown(self):
        shutil.rmtree(testDataPath, ignore_errors=True)
        
    def test_index(self):
        resp = self.app.get('/')
        assert 'Now Viewing: index' in resp

    def test_login(self):
        resp = self.app.get('/login')
        assert '<div id="loginform">' in resp

    def test_admin(self):
        resp = self.app.get('/admin/')
        print resp
        assert 'This is a fully-configurable administrative tool to help you administer your website.' in resp
        assert '<li><a href="group/">Groups</a></li><li><a href="user/">Users</a></li><li><a href="permission/">Permissions</a></li>' in resp

#now we run the quickstarted project nosetests
#FIXME, we need a better implementation
import nose
cls = TestQuickStart()
cls.setUp()
testspath = os.path.join(testDataPath,'TGTest','tgtest','tests')
nose.main(argv=['-w',testspath],exit=False)
cls.tearDown()
