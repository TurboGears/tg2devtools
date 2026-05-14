import argparse
import contextlib
import importlib
import inspect
import io
import json
import os
import sys
import tempfile
import textwrap
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from devtools.gearbox.tginfo_summary import collect_project_routes


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
    error_handler = 'handle_error'
    chain_validation = False


class FakeDottedFilenameFinder:
    def __init__(self, project_root):
        self.project_root = project_root
        self.calls = []

    def get_dotted_filename(self, template_name, template_extension='.html'):
        self.calls.append((template_name, template_extension))
        try:
            template_name, explicit_extension = template_name.rsplit('!', 1)
            template_extension = f'.{explicit_extension}'
        except ValueError:
            pass
        package, basename = template_name.rsplit('.', 1)
        return str(self.project_root / Path(package.replace('.', '/')) / f'{basename}{template_extension}')


class TgInfoRoutesTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tempdir.name)
        (self.project_root / 'development.ini').write_text('[app:main]\n')
        package = self.project_root / 'sampleapp'
        (package / 'controllers').mkdir(parents=True)
        (package / 'templates').mkdir()
        (package / '__init__.py').write_text('')
        (package / 'controllers' / '__init__.py').write_text('')
        (package / 'templates' / '__init__.py').write_text('')
        (package / 'templates' / 'index.xhtml').write_text('<html />')
        (package / 'templates' / 'data.xhtml').write_text('<html />')
        (package / 'templates' / 'mako_page.mak').write_text('<html />')
        (package / 'templates' / 'jinja_page.jinja').write_text('<html />')
        (package / 'templates' / 'genshi_page.html').write_text('<html />')
        (package / 'templates' / 'custom.txt').write_text('custom')
        (package / 'controllers' / 'root.py').write_text(textwrap.dedent('''\
            DYNAMIC_ACCESSES = []
            WSGI_APP_CALLS = []

            class WSGIAppController(object):
                def __init__(self):
                    def app(environ, start_response):
                        WSGI_APP_CALLS.append((environ, start_response))
                        raise AssertionError('tginfo route collection must not invoke mounted WSGI apps')
                    self.app = app

                def inner(self):
                    return None

            class SecureController(object):
                """Secure controller docs."""
                allow_only = 'manage permission'

                def index(self):
                    """Secure index docs."""
                    return {}

                def some_where(self):
                    """Somewhere docs."""
                    return {}

                def _default(self, *args, **kw):
                    """Default docs."""
                    return {}

                def _visit(self):
                    return None

                def _hidden(self):
                    return None

            class SharedController(object):
                def index(self):
                    return {}

            class CyclicController(object):
                def __init__(self):
                    self.self_link = self

                def index(self):
                    return {}

            class RootController(object):
                """Root controller docs."""
                secc = SecureController()
                mounted = WSGIAppController()
                _shared = SharedController()
                admin = _shared
                manage = _shared
                cycle = CyclicController()

                def _before(self):
                    return None

                def _lookup(self, *remainder):
                    """Dynamic lookup docs."""
                    return None

                def _default(self, *args, **kw):
                    return {}

                def index(self):
                    """Root index docs."""
                    return {}

                def data(self, name, page=1, **kw):
                    """Data docs."""
                    return {}

                def mako_page(self):
                    return {}

                def jinja_page(self):
                    return {}

                def genshi_page(self):
                    return {}

                def missing_page(self):
                    return {}

                def metadata_side_effects(self):
                    return {}

                @property
                def dynamic_mount(self):
                    DYNAMIC_ACCESSES.append('dynamic_mount')
                    return SecureController()

                def _private(self):
                    return None
        '''))

        self.old_modules = dict(sys.modules)
        self.replaced_modules = {
            name: sys.modules.get(name)
            for name in ('tg', 'paste', 'paste.deploy')
        }
        sys.path.insert(0, str(self.project_root))
        self.root_module = importlib.import_module('sampleapp.controllers.root')
        self._decorate_controllers()

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

    def install_fake_tg(self):
        tg = types.ModuleType('tg')
        self.dotted_finder = FakeDottedFilenameFinder(self.project_root)
        tg.config = {
            'package_name': 'sampleapp',
            'application_root_module': self.root_module,
            'paths': {'templates': [str(self.project_root / 'sampleapp' / 'templates')]},
            'default_renderer': 'kajiki',
            'renderers': ['json', 'kajiki', 'mako', 'jinja', 'genshi'],
            'tg.app_globals': types.SimpleNamespace(dotted_filename_finder=self.dotted_finder),
        }
        sys.modules['tg'] = tg

        paste = types.ModuleType('paste')
        deploy = types.ModuleType('paste.deploy')
        calls = []
        app_requests = []

        def app(environ, start_response):
            app_requests.append((environ, start_response))
            raise AssertionError('tginfo route collection must not invoke the WSGI app')

        def loadapp(config_name, relative_to=None):
            calls.append((config_name, relative_to, os.getcwd(), str(self.project_root) in sys.path))
            return app

        deploy.loadapp = loadapp
        paste.deploy = deploy
        sys.modules['paste'] = paste
        sys.modules['paste.deploy'] = deploy
        return calls, app_requests

    def test_routes_collects_flat_static_object_dispatch_rows(self):
        calls, app_requests = self.install_fake_tg()

        routes = collect_project_routes(str(self.project_root))

        self.assertEqual(calls, [
            ('config:development.ini', str(self.project_root), str(self.project_root), True),
        ])
        self.assertEqual(app_requests, [])
        self.assertEqual(self.root_module.WSGI_APP_CALLS, [])
        self.assertEqual(self.root_module.DYNAMIC_ACCESSES, [])
        expected_row_keys = {
            'path', 'kind', 'controller', 'controller_source', 'controller_doc',
            'controller_allow_only', 'action', 'action_source', 'action_doc',
            'params', 'action_requires', 'validations', 'exposes',
        }
        for row in routes:
            self.assertEqual(set(row), expected_row_keys)
        by_path_action = {(row['path'], row['action']): row for row in routes}
        for row in routes:
            if row['kind'] == 'wsgi_app':
                continue
            with self.subTest(path=row['path'], action=row['action']):
                self.assertTrue(row['action_source'])
                self.assertFalse(os.path.isabs(row['action_source'].rsplit(':', 1)[0]))
        self.assertIn(('/', 'index'), by_path_action)
        self.assertIn(('/data', 'data'), by_path_action)
        self.assertIn(('/secc/', 'index'), by_path_action)
        self.assertIn(('/secc/some_where', 'some_where'), by_path_action)
        self.assertIn(('/mako_page', 'mako_page'), by_path_action)
        self.assertIn(('/jinja_page', 'jinja_page'), by_path_action)
        self.assertIn(('/genshi_page', 'genshi_page'), by_path_action)
        self.assertIn(('/missing_page', 'missing_page'), by_path_action)
        self.assertIn(('/*', '_lookup'), by_path_action)
        self.assertIn(('/secc/*', '_default'), by_path_action)
        self.assertIn(('/mounted/*', '_default'), by_path_action)
        self.assertNotIn(('/*', '_default'), by_path_action)
        self.assertNotIn(('/index', 'index'), by_path_action)
        self.assertNotIn(('/secc/index', 'index'), by_path_action)
        self.assertNotIn(('/_before', '_before'), by_path_action)
        self.assertNotIn(('/secc/_visit', '_visit'), by_path_action)
        self.assertNotIn(('/_private', '_private'), by_path_action)
        self.assertNotIn(('/secc/_hidden', '_hidden'), by_path_action)
        self.assertNotIn(('/mounted/inner', 'inner'), by_path_action)
        self.assertNotIn(('/dynamic_mount/', 'index'), by_path_action)

        root_index = by_path_action[('/', 'index')]
        self.assertEqual(root_index['kind'], 'index')
        self.assertEqual(root_index['controller'], 'sampleapp.controllers.root.RootController')
        self.assertIn('sampleapp/controllers/root.py:', root_index['controller_source'])
        self.assertEqual(root_index['controller_doc'], 'Root controller docs.')
        self.assertEqual(root_index['controller_allow_only'], None)
        self.assertEqual(root_index['action_doc'], 'Root index docs.')
        self.assertEqual(root_index['exposes'], [{
            'renderer': 'kajiki',
            'content_type': 'text/html',
            'template': 'sampleapp.templates.index',
            'template_file': 'sampleapp/templates/index.xhtml',
            'template_resolution': {
                'status': 'resolved',
                'file': 'sampleapp/templates/index.xhtml',
                'reason': None,
            },
        }])

        data = by_path_action[('/data', 'data')]
        data_source = f"sampleapp/controllers/root.py:{inspect.getsourcelines(self.root_module.RootController.data)[1]}"
        self.assertEqual(data['action_source'], data_source)
        self.assertFalse(os.path.isabs(data['action_source'].rsplit(':', 1)[0]))
        self.assertEqual(data['params'], [
            {'name': 'name', 'kind': 'positional_or_keyword', 'required': True},
            {'name': 'page', 'kind': 'positional_or_keyword', 'required': False, 'default': 1},
            {'name': 'kw', 'kind': 'var_keyword', 'required': False},
        ])
        self.assertEqual(data['action_requires'], ['logged in'])
        self.assertEqual(data['validations'], [{
            'validators': "{'name': 'not_empty'}",
            'error_handler': 'handle_error',
            'chain_validation': False,
        }])
        self.assertEqual(data['exposes'], [
            {
                'renderer': 'json',
                'content_type': 'application/json',
                'template': None,
                'template_file': None,
                'template_resolution': {
                    'status': 'not_applicable',
                    'file': None,
                    'reason': 'exposure has no template',
                },
            },
            {
                'renderer': 'kajiki',
                'content_type': 'text/html',
                'template': 'sampleapp.templates.data',
                'template_file': 'sampleapp/templates/data.xhtml',
                'template_resolution': {
                    'status': 'resolved',
                    'file': 'sampleapp/templates/data.xhtml',
                    'reason': None,
                },
            },
            {
                'renderer': 'custom',
                'content_type': 'text/plain',
                'template': 'sampleapp.templates.custom',
                'template_file': None,
                'template_resolution': {
                    'status': 'unresolved',
                    'file': None,
                    'reason': "renderer 'custom' does not expose a standard template filename resolver",
                },
                'custom_format': 'plain',
            },
        ])

        self.assertEqual(by_path_action[('/mako_page', 'mako_page')]['exposes'][0]['template_resolution'], {
            'status': 'resolved',
            'file': 'sampleapp/templates/mako_page.mak',
            'reason': None,
        })
        self.assertEqual(by_path_action[('/jinja_page', 'jinja_page')]['exposes'][0]['template_resolution'], {
            'status': 'resolved',
            'file': 'sampleapp/templates/jinja_page.jinja',
            'reason': None,
        })
        self.assertEqual(by_path_action[('/genshi_page', 'genshi_page')]['exposes'][0]['template_resolution'], {
            'status': 'resolved',
            'file': 'sampleapp/templates/genshi_page.html',
            'reason': None,
        })
        self.assertEqual(by_path_action[('/missing_page', 'missing_page')]['exposes'][0]['template_resolution'], {
            'status': 'unresolved',
            'file': None,
            'reason': 'TurboGears dotted filename finder returned a missing file',
        })
        self.assertIn(('sampleapp.templates.index', '.xhtml'), self.dotted_finder.calls)
        self.assertIn(('sampleapp.templates.mako_page', '.mak'), self.dotted_finder.calls)
        self.assertIn(('sampleapp.templates.jinja_page', '.jinja'), self.dotted_finder.calls)
        self.assertIn(('sampleapp.templates.genshi_page', '.html'), self.dotted_finder.calls)

        secure = by_path_action[('/secc/some_where', 'some_where')]
        self.assertEqual(secure['controller'], 'sampleapp.controllers.root.SecureController')
        self.assertEqual(secure['controller_doc'], 'Secure controller docs.')
        self.assertEqual(secure['controller_allow_only'], 'manage permission')

        lookup = by_path_action[('/*', '_lookup')]
        self.assertEqual(lookup['kind'], 'dynamic_lookup')
        self.assertEqual(lookup['params'], [
            {'name': 'remainder', 'kind': 'var_positional', 'required': False},
        ])
        self.assertEqual(lookup['exposes'], [])

        default = by_path_action[('/secc/*', '_default')]
        default_source = f"sampleapp/controllers/root.py:{inspect.getsourcelines(self.root_module.SecureController._default)[1]}"
        self.assertEqual(default['kind'], 'dynamic_default')
        self.assertEqual(default['action_source'], default_source)
        self.assertFalse(os.path.isabs(default['action_source'].rsplit(':', 1)[0]))
        self.assertEqual(default['action_doc'], 'Default docs.')

        mounted = by_path_action[('/mounted/*', '_default')]
        self.assertEqual(mounted['kind'], 'wsgi_app')
        self.assertEqual(mounted['controller'], 'sampleapp.controllers.root.WSGIAppController')
        json.dumps(routes, sort_keys=True)

    def test_route_metadata_uses_static_attributes_without_calling_descriptors(self):
        side_effects = []

        class NoisyRequirement:
            def __init__(self):
                self.__dict__['predicate'] = 'plain predicate'

            @property
            def predicate(self):
                side_effects.append('requirement.predicate')
                return 'dynamic predicate'

        class NoisyValidation:
            def __init__(self):
                self.__dict__.update({
                    'validators': {'token': 'not_empty'},
                    'validator': 'plain validator',
                    'error_handler': 'plain error handler',
                    'chain_validation': False,
                })

            @property
            def validators(self):
                side_effects.append('validation.validators')
                return {'dynamic': 'validator'}

            @property
            def validator(self):
                side_effects.append('validation.validator')
                return 'dynamic validator'

            @property
            def error_handler(self):
                side_effects.append('validation.error_handler')
                return 'dynamic error handler'

            @property
            def chain_validation(self):
                side_effects.append('validation.chain_validation')
                return True

        class NoisyDecoration:
            def __init__(self):
                self.__dict__.update({
                    '_expositions': [],
                    'engines': {
                        'text/html': ('kajiki', 'sampleapp.templates.index', [], {}),
                    },
                    'custom_engines': {
                        'plain': ('text/plain', 'custom', 'sampleapp.templates.custom', [], {}),
                    },
                    'requirements': [NoisyRequirement()],
                    'validations': [NoisyValidation()],
                })

            @property
            def exposed(self):
                side_effects.append('decoration.exposed')
                return False

            @property
            def _resolve_expositions(self):
                side_effects.append('decoration._resolve_expositions')

                def resolve():
                    side_effects.append('decoration._resolve_expositions()')

                return resolve

            @property
            def engines(self):
                side_effects.append('decoration.engines')
                return {}

            @property
            def custom_engines(self):
                side_effects.append('decoration.custom_engines')
                return {}

            @property
            def requirements(self):
                side_effects.append('decoration.requirements')
                return []

            @property
            def validations(self):
                side_effects.append('decoration.validations')
                return []

        self.root_module.RootController.metadata_side_effects.decoration = NoisyDecoration()
        self.install_fake_tg()

        routes = collect_project_routes(str(self.project_root))

        by_path_action = {(row['path'], row['action']): row for row in routes}
        route = by_path_action[('/metadata_side_effects', 'metadata_side_effects')]
        self.assertEqual(side_effects, [])
        self.assertEqual(route['action_requires'], ['plain predicate'])
        self.assertEqual(route['validations'], [{
            'validators': "{'token': 'not_empty'}",
            'validator': 'plain validator',
            'error_handler': 'plain error handler',
            'chain_validation': False,
        }])
        self.assertEqual(route['exposes'], [
            {
                'renderer': 'kajiki',
                'content_type': 'text/html',
                'template': 'sampleapp.templates.index',
                'template_file': 'sampleapp/templates/index.xhtml',
                'template_resolution': {
                    'status': 'resolved',
                    'file': 'sampleapp/templates/index.xhtml',
                    'reason': None,
                },
            },
            {
                'renderer': 'custom',
                'content_type': 'text/plain',
                'template': 'sampleapp.templates.custom',
                'template_file': None,
                'template_resolution': {
                    'status': 'unresolved',
                    'file': None,
                    'reason': "renderer 'custom' does not expose a standard template filename resolver",
                },
                'custom_format': 'plain',
            },
        ])

    def test_routes_collects_aliased_static_mounts_once_per_path(self):
        calls, app_requests = self.install_fake_tg()

        routes = collect_project_routes(str(self.project_root))

        self.assertEqual(len(calls), 1)
        self.assertEqual(app_requests, [])
        path_actions = [(row['path'], row['action']) for row in routes]
        self.assertEqual(path_actions.count(('/admin/', 'index')), 1)
        self.assertEqual(path_actions.count(('/manage/', 'index')), 1)
        by_path_action = {(row['path'], row['action']): row for row in routes}
        self.assertEqual(
            by_path_action[('/admin/', 'index')]['controller'],
            'sampleapp.controllers.root.SharedController',
        )
        self.assertEqual(
            by_path_action[('/manage/', 'index')]['controller'],
            'sampleapp.controllers.root.SharedController',
        )
        self.assertIn(('/cycle/', 'index'), by_path_action)
        self.assertNotIn(('/cycle/self_link/', 'index'), by_path_action)

    def _decorate_controllers(self):
        root = self.root_module.RootController
        secure = self.root_module.SecureController
        shared = self.root_module.SharedController
        cyclic = self.root_module.CyclicController
        root.index.decoration = FakeDecoration(engines={
            'text/html': ('kajiki', 'sampleapp.templates.index', [], {}),
        })
        root.data.decoration = FakeDecoration(
            engines={
                'application/json': ('json', '', ['tmpl_context'], {}),
                'text/html': ('kajiki', 'sampleapp.templates.data', [], {}),
            },
            custom_engines={
                'plain': ('text/plain', 'custom', 'sampleapp.templates.custom', [], {}),
            },
            requirements=[FakeRequirement('logged in')],
            validations=[FakeValidation()],
        )
        root.mako_page.decoration = FakeDecoration(engines={
            'text/html': ('mako', 'sampleapp.templates.mako_page', [], {}),
        })
        root.jinja_page.decoration = FakeDecoration(engines={
            'text/html': ('jinja', 'sampleapp.templates.jinja_page', [], {}),
        })
        root.genshi_page.decoration = FakeDecoration(engines={
            'text/html': ('genshi', 'sampleapp.templates.genshi_page', [], {}),
        })
        root.missing_page.decoration = FakeDecoration(engines={
            'text/html': ('kajiki', 'sampleapp.templates.missing_page', [], {}),
        })
        secure.index.decoration = FakeDecoration(engines={
            'text/html': ('kajiki', 'sampleapp.templates.index', [], {}),
        })
        secure.some_where.decoration = FakeDecoration(engines={
            'text/html': ('kajiki', 'sampleapp.templates.index', [], {}),
        })
        secure._default.decoration = FakeDecoration(engines={
            'text/html': ('kajiki', 'sampleapp.templates.index', [], {}),
        })
        shared.index.decoration = FakeDecoration(engines={
            'text/html': ('kajiki', 'sampleapp.templates.index', [], {}),
        })
        cyclic.index.decoration = FakeDecoration(engines={
            'text/html': ('kajiki', 'sampleapp.templates.index', [], {}),
        })


class TgInfoRoutesCommandTests(unittest.TestCase):
    def setUp(self):
        self.previous_modules = {
            name: sys.modules.get(name)
            for name in ('gearbox', 'gearbox.command', 'devtools.gearbox.tginfo')
        }
        gearbox = types.ModuleType('gearbox')
        command = types.ModuleType('gearbox.command')

        class Command(object):
            def __init__(self, *args, **kwargs):
                pass

            def get_parser(self, prog_name):
                return argparse.ArgumentParser(prog=prog_name)

        command.Command = Command
        gearbox.command = command
        sys.modules['gearbox'] = gearbox
        sys.modules['gearbox.command'] = command
        sys.modules.pop('devtools.gearbox.tginfo', None)
        self.module = importlib.import_module('devtools.gearbox.tginfo')

    def tearDown(self):
        sys.modules.pop('devtools.gearbox.tginfo', None)
        for name, module in self.previous_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def test_routes_subcommand_prints_json_rows(self):
        command = self.module.TgInfoCommand(None, {})
        opts = command.get_parser('gearbox tginfo').parse_args([
            'routes', '--project', '/project', '--config', 'test.ini', '--json',
        ])
        routes = [{
            'path': '/',
            'kind': 'index',
            'controller': 'sampleapp.controllers.root.RootController',
            'controller_source': 'sampleapp/controllers/root.py:1',
            'controller_doc': None,
            'controller_allow_only': None,
            'action': 'index',
            'action_source': 'sampleapp/controllers/root.py:8',
            'action_doc': None,
            'params': [],
            'action_requires': [],
            'validations': [],
            'exposes': [],
        }]

        with patch.object(self.module, 'collect_project_routes', return_value=routes) as collector:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                command.take_action(opts)

        collector.assert_called_once_with(project='/project', config='test.ini')
        self.assertEqual(json.loads(output.getvalue()), routes)


if __name__ == '__main__':
    unittest.main()
