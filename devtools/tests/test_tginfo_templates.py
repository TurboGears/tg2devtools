import contextlib
import importlib
import io
import json
import os
import sys
import tempfile
import textwrap
import types
import unittest
from pathlib import Path

from devtools.gearbox.tginfo import TgInfoCommand

class FakeDecoration:
    def __init__(self, engines=None):
        self.engines = engines or {}
        self.custom_engines = {}
        self.requirements = []
        self.validations = []
        self.exposed = bool(self.engines)


class FakeDottedFilenameFinder:
    def __init__(self, project_root):
        self.project_root = project_root

    def get_dotted_filename(self, template_name, template_extension='.html'):
        if template_name == 'sampleapp.templates.fallback':
            raise LookupError('finder cannot resolve fallback template')
        package, basename = template_name.rsplit('.', 1)
        return str(self.project_root / Path(package.replace('.', '/')) / f'{basename}{template_extension}')


class TgInfoTemplatesTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tempdir.name)
        (self.project_root / 'development.ini').write_text('[app:main]\n')
        package = self.project_root / 'sampleapp'
        templates = package / 'templates'
        (package / 'controllers').mkdir(parents=True)
        (templates / 'partials').mkdir(parents=True)
        (package / '__init__.py').write_text('')
        (package / 'controllers' / '__init__.py').write_text('')
        (templates / '__init__.py').write_text("raise AssertionError('template packages must not be imported')\n")
        (templates / 'index.xhtml').write_text('<html />')
        (templates / 'index.mak').write_text('<html />')
        (templates / 'data.xhtml').write_text('<html />')
        (templates / 'email.mak').write_text('<html />')
        (templates / 'fallback.xhtml').write_text('<html />')
        (templates / 'fallback.mak').write_text('<html />')
        (templates / 'listing.jinja').write_text('<html />')
        (templates / 'legacy.html').write_text('<html />')
        (templates / 'partials' / '_widget.xhtml').write_text('<div />')
        (templates / 'notes.txt').write_text('not a recognized template')
        (package / 'controllers' / 'root.py').write_text(textwrap.dedent('''\
            class RootController(object):
                def index(self):
                    return {}

                def data(self):
                    return {}

                def email(self):
                    return {}

                def fallback(self):
                    return {}
        '''))

        self.old_modules = dict(sys.modules)
        self.replaced_modules = {
            name: sys.modules.get(name)
            for name in ('tg', 'paste', 'paste.deploy')
        }
        sys.path.insert(0, str(self.project_root))
        self.root_module = importlib.import_module('sampleapp.controllers.root')
        self.root_module.RootController.index.decoration = FakeDecoration({
            'text/html': ('kajiki', 'sampleapp.templates.index', [], {}),
        })
        self.root_module.RootController.data.decoration = FakeDecoration({
            'text/html': (None, 'sampleapp.templates.data', [], {}),
        })
        self.root_module.RootController.email.decoration = FakeDecoration({
            'text/html': ('mako', 'sampleapp.templates.email', [], {}),
        })
        self.root_module.RootController.fallback.decoration = FakeDecoration({
            'text/html': ('mako', 'sampleapp.templates.fallback', [], {}),
        })

    def tearDown(self):
        sys.path = [path for path in sys.path if path != str(self.project_root)]
        for name in list(sys.modules):
            if name not in self.old_modules:
                sys.modules.pop(name, None)
        for name, module in self.replaced_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        self.tempdir.cleanup()

    def take_tginfo(self, subcommand, *args):
        command = TgInfoCommand(None, {})
        opts = command.get_parser('gearbox tginfo').parse_args([
            subcommand, '--project', str(self.project_root), *args,
        ])
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            command.take_action(opts)
        return stdout.getvalue(), stderr.getvalue()

    def run_tginfo(self, subcommand):
        stdout, _ = self.take_tginfo(subcommand, '--json')
        return json.loads(stdout)

    def install_fake_tg(self):
        tg = types.ModuleType('tg')
        tg.config = {
            'package_name': 'sampleapp',
            'application_root_module': self.root_module,
            'paths': {'templates': [str(self.project_root / 'sampleapp' / 'templates')]},
            'default_renderer': 'kajiki',
            'renderers': ['json', 'kajiki', 'mako', 'jinja', 'genshi'],
            'tg.app_globals': types.SimpleNamespace(
                dotted_filename_finder=FakeDottedFilenameFinder(self.project_root),
            ),
        }
        sys.modules['tg'] = tg

        paste = types.ModuleType('paste')
        deploy = types.ModuleType('paste.deploy')
        calls = []

        def loadapp(config_name, relative_to=None):
            calls.append((config_name, relative_to, os.getcwd(), str(self.project_root) in sys.path))
            return object()

        deploy.loadapp = loadapp
        paste.deploy = deploy
        sys.modules['paste'] = paste
        sys.modules['paste.deploy'] = deploy
        return calls

    def test_templates_lists_all_recognized_files_with_route_backlinks(self):
        calls = self.install_fake_tg()

        templates = self.run_tginfo('templates')

        self.assertEqual(calls, [
            ('config:development.ini', str(self.project_root), str(self.project_root), True),
        ])
        expected_row_keys = {'name', 'file', 'renderer', 'exposed_by'}
        for row in templates:
            self.assertEqual(set(row), expected_row_keys)
            self.assertFalse(os.path.isabs(row['file']))
        by_file = {row['file']: row for row in templates}
        self.assertEqual(set(by_file), {
            'sampleapp/templates/data.xhtml',
            'sampleapp/templates/email.mak',
            'sampleapp/templates/fallback.mak',
            'sampleapp/templates/fallback.xhtml',
            'sampleapp/templates/index.mak',
            'sampleapp/templates/index.xhtml',
            'sampleapp/templates/legacy.html',
            'sampleapp/templates/listing.jinja',
            'sampleapp/templates/partials/_widget.xhtml',
        })
        self.assertEqual(by_file['sampleapp/templates/index.xhtml'], {
            'name': 'sampleapp.templates.index',
            'file': 'sampleapp/templates/index.xhtml',
            'renderer': 'kajiki',
            'exposed_by': ['/'],
        })
        self.assertEqual(by_file['sampleapp/templates/index.mak']['exposed_by'], [])
        self.assertEqual(by_file['sampleapp/templates/data.xhtml']['exposed_by'], ['/data'])
        self.assertEqual(by_file['sampleapp/templates/email.mak']['renderer'], 'mako')
        self.assertEqual(by_file['sampleapp/templates/email.mak']['exposed_by'], ['/email'])
        self.assertEqual(by_file['sampleapp/templates/fallback.mak']['exposed_by'], ['/fallback'])
        self.assertEqual(by_file['sampleapp/templates/fallback.xhtml']['exposed_by'], [])
        self.assertEqual(by_file['sampleapp/templates/listing.jinja']['renderer'], 'jinja')
        self.assertEqual(by_file['sampleapp/templates/listing.jinja']['exposed_by'], [])
        self.assertEqual(by_file['sampleapp/templates/legacy.html']['renderer'], 'genshi')
        self.assertEqual(by_file['sampleapp/templates/partials/_widget.xhtml'], {
            'name': 'sampleapp.templates.partials._widget',
            'file': 'sampleapp/templates/partials/_widget.xhtml',
            'renderer': 'kajiki',
            'exposed_by': [],
        })
        json.dumps(templates, sort_keys=True)

    def test_templates_action_loads_config_parsed_from_command_line(self):
        calls = self.install_fake_tg()

        self.take_tginfo('templates', '--config', 'test.ini')

        self.assertEqual(calls, [
            ('config:test.ini', str(self.project_root), str(self.project_root), True),
        ])

    def test_human_templates_output_mentions_unexposed_templates(self):
        self.install_fake_tg()

        output, _ = self.take_tginfo('templates')

        self.assertIn('sampleapp/templates/index.xhtml [kajiki] sampleapp.templates.index exposed by /', output)
        self.assertIn('sampleapp/templates/partials/_widget.xhtml [kajiki]', output)
        self.assertIn('not exposed by static routes', output)




if __name__ == '__main__':
    unittest.main()
