import argparse
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


class FakeDecoration:
    def __init__(self, engines=None, custom_engines=None, requirements=None, validations=None):
        self.engines = engines or {}
        self.custom_engines = custom_engines or {}
        self.requirements = requirements or []
        self.validations = validations or []
        self.exposed = bool(self.engines) or bool(self.custom_engines)


class FakeRequirement:
    def __init__(self, predicate):
        self.predicate = predicate


class FakeValidation:
    validators = {'name': 'not_empty'}
    error_handler = 'validation_error'
    chain_validation = False


class FakeDottedFilenameFinder:
    def __init__(self, project_root):
        self.project_root = project_root

    def get_dotted_filename(self, template_name, template_extension='.html'):
        package, basename = template_name.rsplit('.', 1)
        return str(self.project_root / Path(package.replace('.', '/')) / f'{basename}{template_extension}')


class RecordingDBSession:
    def __init__(self, write_operations):
        self.write_operations = write_operations

    def add(self, value):
        self.write_operations.append(('add', value))

    def delete(self, value):
        self.write_operations.append(('delete', value))

    def flush(self):
        self.write_operations.append(('flush',))

    def commit(self):
        self.write_operations.append(('commit',))


class TgInfoQuickstartCommandTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tempdir.name)
        self.load_calls = []
        self.runtime_requests = []
        self.database_writes = []
        self.old_module_names = set(sys.modules)
        self.replaced_modules = {
            name: sys.modules.get(name)
            for name in (
                'tg',
                'paste',
                'paste.deploy',
                'gearbox',
                'gearbox.command',
                'devtools.gearbox.tginfo',
                'quickstart_db_sentinel',
            )
        }
        database = types.ModuleType('quickstart_db_sentinel')
        database.DBSession = RecordingDBSession(self.database_writes)
        database.write_operations = self.database_writes
        sys.modules['quickstart_db_sentinel'] = database
        self._write_quickstart_project()
        sys.path.insert(0, str(self.project_root))
        self.root_module = importlib.import_module('quickstartapp.controllers.root')
        self._decorate_controllers()
        self._install_fake_runtime_modules()
        sys.modules.pop('devtools.gearbox.tginfo', None)
        self.tginfo = importlib.import_module('devtools.gearbox.tginfo')

    def tearDown(self):
        sys.path = [path for path in sys.path if path != str(self.project_root)]
        sys.modules.pop('devtools.gearbox.tginfo', None)
        for name in list(sys.modules):
            if name not in self.old_module_names:
                sys.modules.pop(name, None)
        for name, module in self.replaced_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        self.tempdir.cleanup()

    def test_tginfo_reports_quickstart_facts_without_runtime_side_effects(self):
        summary = self.run_tginfo('summary', '--project', str(self.project_root), '--json')
        routes = self.run_tginfo('routes', '--project', str(self.project_root), '--config', 'test.ini', '--json')
        models = self.run_tginfo('models', '--project', str(self.project_root), '--json')
        templates = self.run_tginfo('templates', '--project', str(self.project_root), '--json')
        scaffolds = self.run_tginfo('scaffolds', '--project', str(self.project_root), '--json')

        self.assertEqual(self.load_calls, [
            ('config:development.ini', str(self.project_root), str(self.project_root), True),
            ('config:test.ini', str(self.project_root), str(self.project_root), True),
            ('config:development.ini', str(self.project_root), str(self.project_root), True),
        ])
        self.assertEqual(self.runtime_requests, [])
        self.assertEqual(self.database_writes, [])
        self.assertNotIn('quickstartapp.websetup', sys.modules)
        self.assertNotIn('migration.env', sys.modules)

        self.assertEqual(summary['package_name'], 'quickstartapp')
        self.assertEqual(summary['default_renderer'], 'kajiki')
        self.assertEqual(summary['root_controller']['class'], 'quickstartapp.controllers.root.RootController')
        self.assertEqual(summary['database'], {'enabled': True, 'orm': 'sqlalchemy'})
        self.assertEqual(summary['auth'], {'enabled': True})

        by_path_action = {(row['path'], row['action']): row for row in routes}
        self.assertIn(('/', 'index'), by_path_action)
        self.assertIn(('/about', 'about'), by_path_action)
        self.assertIn(('/data', 'data'), by_path_action)
        self.assertIn(('/secc/', 'index'), by_path_action)
        self.assertIn(('/secc/*', '_default'), by_path_action)
        self.assertIn(('/blog/*', '_lookup'), by_path_action)
        self.assertIn(('/mounted/*', '_default'), by_path_action)
        self.assertNotIn(('/index', 'index'), by_path_action)
        self.assertNotIn(('/secc/index', 'index'), by_path_action)

        root_index = by_path_action[('/', 'index')]
        self.assertEqual(root_index['kind'], 'index')
        self.assertEqual(root_index['controller_doc'], 'Quickstart root controller docs.')
        self.assertEqual(root_index['action_doc'], 'Quickstart welcome page.')
        self.assertEqual(root_index['exposes'][0]['template_file'], 'quickstartapp/templates/index.xhtml')

        secure_index = by_path_action[('/secc/', 'index')]
        self.assertEqual(secure_index['controller_allow_only'], 'manage permission')
        self.assertEqual(secure_index['controller_doc'], 'Quickstart secure controller docs.')

        data = by_path_action[('/data', 'data')]
        self.assertEqual(data['params'], [
            {'name': 'name', 'kind': 'positional_or_keyword', 'required': True},
            {'name': 'page', 'kind': 'positional_or_keyword', 'required': False, 'default': 1},
            {'name': 'kw', 'kind': 'var_keyword', 'required': False},
        ])
        self.assertEqual(data['action_requires'], ['logged in'])
        self.assertEqual(data['validations'], [{
            'validators': "{'name': 'not_empty'}",
            'error_handler': 'validation_error',
            'chain_validation': False,
        }])
        self.assertEqual(
            [(exposure['renderer'], exposure['content_type'], exposure['template_file']) for exposure in data['exposes']],
            [('json', 'application/json', None), ('kajiki', 'text/html', 'quickstartapp/templates/data.xhtml')],
        )
        self.assertEqual(by_path_action[('/blog/*', '_lookup')]['kind'], 'dynamic_lookup')
        self.assertEqual(by_path_action[('/secc/*', '_default')]['kind'], 'dynamic_default')
        self.assertEqual(by_path_action[('/mounted/*', '_default')]['kind'], 'wsgi_app')

        by_model = {row['name']: row for row in models}
        self.assertEqual(by_model['User']['orm'], 'sqlalchemy')
        self.assertEqual(by_model['Page']['orm'], 'ming')

        by_template = {row['file']: row for row in templates}
        self.assertEqual(by_template['quickstartapp/templates/index.xhtml']['exposed_by'], ['/'])
        self.assertEqual(by_template['quickstartapp/templates/data.xhtml']['exposed_by'], ['/data'])
        self.assertEqual(by_template['quickstartapp/templates/about.xhtml']['exposed_by'], ['/about'])
        self.assertEqual(by_template['quickstartapp/templates/unlinked.xhtml']['exposed_by'], [])

        self.assertEqual(scaffolds, [{
            'name': 'controller',
            'template_path': 'quickstartapp/controllers/controller.py.template',
            'relative_dir': 'quickstartapp/controllers',
            'output_extension': '.py',
            'default_output_pattern': 'quickstartapp/controllers/{target}.py',
        }])

    def run_tginfo(self, *args):
        command = self.tginfo.TgInfoCommand(None, {})
        opts = command.get_parser('gearbox tginfo').parse_args(list(args))
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            command.take_action(opts)
        expected_stderr = '' if args[0] in ('models', 'scaffolds') else 'quickstart startup banner\n'
        self.assertEqual(stderr.getvalue(), expected_stderr)
        self.assertTrue(stdout.getvalue().endswith('\n'))
        self.assertFalse(stdout.getvalue().endswith('\n\n'))
        return json.loads(stdout.getvalue())

    def _write_quickstart_project(self):
        (self.project_root / 'development.ini').write_text('[app:main]\n')
        (self.project_root / 'test.ini').write_text('[app:main]\n')
        (self.project_root / 'pyproject.toml').write_text(textwrap.dedent('''\
            [project.entry-points."paste.app_factory"]
            main = "quickstartapp.config.app:make_app"
        '''))
        package = self.project_root / 'quickstartapp'
        for directory in (
            package / 'controllers',
            package / 'config',
            package / 'model',
            package / 'templates',
            package / 'scaffolds',
            self.project_root / 'migration',
        ):
            directory.mkdir(parents=True)
        for path in (
            package / '__init__.py',
            package / 'controllers' / '__init__.py',
            package / 'config' / '__init__.py',
            self.project_root / 'migration' / '__init__.py',
        ):
            path.write_text('')
        (package / 'websetup.py').write_text("raise AssertionError('tginfo must not run setup-app')\n")
        (self.project_root / 'migration' / 'env.py').write_text("raise AssertionError('tginfo must not run migrations')\n")
        (package / 'config' / 'app.py').write_text(textwrap.dedent('''\
            def make_app(global_conf, **app_conf):
                raise AssertionError('tginfo must not load the app through the project factory in this test')
        '''))
        (package / 'controllers' / 'root.py').write_text(textwrap.dedent('''\
            class WSGIAppController(object):
                def __init__(self):
                    def app(environ, start_response):
                        raise AssertionError('tginfo must not invoke mounted WSGI apps')
                    self.app = app

                def inner(self):
                    return None

            class SecureController(object):
                """Quickstart secure controller docs."""
                allow_only = 'manage permission'

                def index(self):
                    """Quickstart secure index docs."""
                    return {}

                def _default(self, *args, **kw):
                    """Quickstart secure dynamic default docs."""
                    return {}

            class BlogController(object):
                def _lookup(self, *remainder):
                    """Quickstart dynamic lookup docs."""
                    return None

            class RootController(object):
                """Quickstart root controller docs."""
                secc = SecureController()
                blog = BlogController()
                mounted = WSGIAppController()

                def index(self):
                    """Quickstart welcome page."""
                    return {}

                def about(self):
                    """Quickstart about page."""
                    return {}

                def data(self, name, page=1, **kw):
                    """Quickstart data endpoint."""
                    return {}
        '''))
        (package / 'model' / '__init__.py').write_text(textwrap.dedent('''\
            from quickstartapp.model.auth import User
            from quickstartapp.model.content import Page
            from quickstartapp.model.db import DBSession, write_operations

            __all__ = ('User', 'Page')
        '''))
        (package / 'model' / 'auth.py').write_text(textwrap.dedent('''\
            class User(object):
                """Quickstart user model."""
                __table__ = object()
        '''))
        (package / 'model' / 'content.py').write_text(textwrap.dedent('''\
            class Page(object):
                """Quickstart Ming page model."""
                class __mongometa__:
                    name = 'page'
        '''))
        (package / 'model' / 'db.py').write_text(textwrap.dedent('''\
            from quickstart_db_sentinel import DBSession, write_operations
        '''))
        for template in ('index', 'about', 'data', 'secure', 'unlinked'):
            (package / 'templates' / f'{template}.xhtml').write_text('<html />')
        (package / 'controllers' / 'controller.py.template').write_text('controller scaffold')

    def _decorate_controllers(self):
        root = self.root_module.RootController
        secure = self.root_module.SecureController
        root.index.decoration = FakeDecoration(engines={
            'text/html': ('kajiki', 'quickstartapp.templates.index', [], {}),
        })
        root.about.decoration = FakeDecoration(engines={
            'text/html': ('kajiki', 'quickstartapp.templates.about', [], {}),
        })
        root.data.decoration = FakeDecoration(
            engines={
                'application/json': ('json', '', [], {}),
                'text/html': ('kajiki', 'quickstartapp.templates.data', [], {}),
            },
            requirements=[FakeRequirement('logged in')],
            validations=[FakeValidation()],
        )
        secure.index.decoration = FakeDecoration(engines={
            'text/html': ('kajiki', 'quickstartapp.templates.secure', [], {}),
        })
        secure._default.decoration = FakeDecoration(engines={
            'text/html': ('kajiki', 'quickstartapp.templates.secure', [], {}),
        })

    def _install_fake_runtime_modules(self):
        database = sys.modules['quickstart_db_sentinel']
        tg = types.ModuleType('tg')
        tg.config = {
            'package_name': 'quickstartapp',
            'default_renderer': 'kajiki',
            'renderers': ['json', 'kajiki'],
            'application_root_module': self.root_module,
            'paths': {'templates': [str(self.project_root / 'quickstartapp' / 'templates')]},
            'tg.app_globals': types.SimpleNamespace(
                dotted_filename_finder=FakeDottedFilenameFinder(self.project_root),
            ),
            'use_sqlalchemy': True,
            'use_ming': False,
            'DBSession': database.DBSession,
            'sa_auth.enabled': True,
        }
        paste = types.ModuleType('paste')
        deploy = types.ModuleType('paste.deploy')

        def loadapp(config_name, relative_to=None):
            print('quickstart startup banner')
            self.load_calls.append((config_name, relative_to, os.getcwd(), str(self.project_root) in sys.path))

            def app(environ, start_response):
                self.runtime_requests.append((environ, start_response))
                raise AssertionError('tginfo must not issue runtime requests')
            return app

        deploy.loadapp = loadapp
        paste.deploy = deploy

        gearbox = types.ModuleType('gearbox')
        command = types.ModuleType('gearbox.command')

        class Command(object):
            def __init__(self, *args, **kwargs):
                pass

            def get_parser(self, prog_name):
                return argparse.ArgumentParser(prog=prog_name)

        command.Command = Command
        gearbox.command = command
        sys.modules.update({
            'tg': tg,
            'paste': paste,
            'paste.deploy': deploy,
            'gearbox': gearbox,
            'gearbox.command': command,
        })


if __name__ == '__main__':
    unittest.main()
