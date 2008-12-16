from devtools.pastetemplate import TurboGearsTemplate
import os, shutil
import pkg_resources
from paste.deploy import loadapp
from paste.fixture import TestApp
from paste.script.create_distro import CreateDistroCommand

testDataPath = os.path.join(
        os.path.abspath(os.path.dirname(__file__)),
        'data')

app = None

class MochOptions:
    simulate = False
    overwrite = True
    templates = ['turbogears2',]
    output_dir = testDataPath
    list_templates = False
    list_variables = False
    config = None
    inspect_files = False
    svn_repository = False

def setup():
    # if a test failed previously we need to cleanup the mess
    # not mandatory but cleaner
    #shutil.rmtree(testDataPath, ignore_errors=True)

    global app
    command = CreateDistroCommand('name')
    command.verbose = True
    command.simulate = False
    command.options = MochOptions()
    command.interactive=False
    command.args=['TGTest',]
    command.args.append("sqlalchemy=%s" % True)
    command.args.append("elixir=%s" % False)
    command.args.append("sqlobject=%s" % False)
    command.args.append("auth=%s" % False)

    print command

    proj_dir = os.path.join(testDataPath, 'TGTest')

    command.templates = TurboGearsTemplate('TGTest')
    command.create_template(
            TurboGearsTemplate('TGTest'),
            proj_dir,
            {
                'package': 'TGTest',
                'project': 'tgtest',
                'egg': 'tgtest',
                'sqlalchemy': True,
                'sqlobject': False,
                'elixir': False,
                'auth': False
            })

    command.command()
    
    pkg_resources.working_set.add_entry(proj_dir)
    app = loadapp('config:development.ini', relative_to=proj_dir)
    app = TestApp(app)

def teardown():
    shutil.rmtree(testDataPath, ignore_errors=True)
    
def test_app_runs_index():
    resp = app.get('/')
    s =  resp.body
    print s
    assert """<h2>Getting help</h2>
      <ul class="links">
        <li><a href="http://docs.turbogears.org/2.0">Documentation</a></li>
        <li><a href="http://docs.turbogears.org/2.0/API">API Reference</a></li>
        <li><a href="http://trac.turbogears.org/turbogears/">Bug Tracker</a></li>
        <li><a href="http://groups.google.com/group/turbogears">Mailing
        List</a></li>
      </ul>""" in s, s

