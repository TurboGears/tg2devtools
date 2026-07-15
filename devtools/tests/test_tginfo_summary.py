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
from unittest.mock import patch

from devtools.gearbox.tginfo import (
    collect_project_scaffolds,
    collect_project_summary,
    format_project_scaffolds,
    format_project_summary,
)


class TgInfoSummaryTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tempdir.name)
        (self.project_root / 'development.ini').write_text('[app:main]\n')
        package = self.project_root / 'sampleapp'
        (package / 'controllers').mkdir(parents=True)
        (package / 'model').mkdir()
        (package / 'templates').mkdir()
        (package / '__init__.py').write_text('')
        (package / 'controllers' / '__init__.py').write_text('')
        (package / 'model' / '__init__.py').write_text('')
        (package / 'templates' / 'index.xhtml').write_text('<html />')
        (package / 'controllers' / 'root.py').write_text(textwrap.dedent('''\
            class RootController(object):
                pass
        '''))
        (package / 'controllers' / 'stringroot.py').write_text(textwrap.dedent('''\
            class RootController(object):
                pass
        '''))

        self.old_modules = dict(sys.modules)
        self.replaced_modules = {
            name: sys.modules.get(name)
            for name in ('tg', 'paste', 'paste.deploy')
        }
        sys.path.insert(0, str(self.project_root))
        self.root_module = importlib.import_module('sampleapp.controllers.root')

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

    def install_fake_tg(self, config, startup_stdout=None):
        tg = types.ModuleType('tg')
        tg.config = config
        sys.modules['tg'] = tg

        paste = types.ModuleType('paste')
        deploy = types.ModuleType('paste.deploy')
        calls = []

        def loadapp(config_name, relative_to=None):
            if startup_stdout:
                print(startup_stdout)
            calls.append((config_name, relative_to, os.getcwd(), str(self.project_root) in sys.path))
            return object()

        deploy.loadapp = loadapp
        paste.deploy = deploy
        sys.modules['paste'] = paste
        sys.modules['paste.deploy'] = deploy
        return calls

    def test_summary_collects_factual_project_information_without_requests_or_writes(self):
        calls = self.install_fake_tg({
            'package_name': 'sampleapp',
            'default_renderer': 'kajiki',
            'renderers': ['json', 'kajiki'],
            'application_root_module': self.root_module,
            'paths': {'controllers': 'sampleapp/controllers'},
            'use_sqlalchemy': True,
            'use_ming': False,
            'sa_auth.enabled': True,
        })

        summary = collect_project_summary(str(self.project_root))

        self.assertEqual(calls, [
            ('config:development.ini', str(self.project_root), str(self.project_root), True),
        ])
        self.assertEqual(summary['project_root'], str(self.project_root))
        self.assertEqual(summary['config_file'], str(self.project_root / 'development.ini'))
        self.assertEqual(summary['package_name'], 'sampleapp')
        self.assertEqual(summary['default_renderer'], 'kajiki')
        self.assertEqual(summary['renderers'], ['json', 'kajiki'])
        self.assertEqual(summary['paths']['controllers'], 'sampleapp/controllers')
        self.assertEqual(summary['paths']['model'], 'sampleapp/model')
        self.assertEqual(summary['paths']['templates'], 'sampleapp/templates')
        self.assertEqual(summary['root_controller']['class'], 'sampleapp.controllers.root.RootController')
        self.assertEqual(summary['root_controller']['source'], 'sampleapp/controllers/root.py:1')
        self.assertEqual(summary['database'], {'enabled': True, 'orm': 'sqlalchemy'})
        self.assertEqual(summary['auth'], {'enabled': True})
        self.assertNotIn('counts', summary)
        self.assertNotIn('dependencies', summary)
        self.assertNotIn('recipes', summary)
        self.assertNotIn('next_steps', summary)
        self.assertNotIn('agent_playbook', summary)
        json.dumps(summary, sort_keys=True)

    def test_summary_redirects_startup_stdout_away_from_collector_stdout(self):
        self.install_fake_tg({
            'package_name': 'sampleapp',
            'application_root_module': self.root_module,
        }, startup_stdout='startup banner from app')

        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            summary = collect_project_summary(str(self.project_root))

        self.assertEqual(stdout.getvalue(), '')
        self.assertIn('startup banner from app', stderr.getvalue())
        self.assertEqual(summary['package_name'], 'sampleapp')

    def test_summary_imports_dotted_application_root_module(self):
        self.install_fake_tg({
            'package_name': 'sampleapp',
            'application_root_module': 'sampleapp.controllers.stringroot',
        })

        summary = collect_project_summary(str(self.project_root))

        self.assertEqual(
            summary['root_controller']['class'],
            'sampleapp.controllers.stringroot.RootController',
        )
        self.assertEqual(summary['root_controller']['source'], 'sampleapp/controllers/stringroot.py:1')

    def test_summary_uses_explicit_tg_root_controller_class_or_instance(self):
        RootController = self.root_module.RootController
        for root_controller in (RootController, RootController()):
            with self.subTest(root_controller_type=type(root_controller).__name__):
                self.install_fake_tg({
                    'package_name': 'sampleapp',
                    'tg.root_controller': root_controller,
                    'application_root_module': 'sampleapp.controllers.stringroot',
                })

                summary = collect_project_summary(str(self.project_root))

                self.assertEqual(
                    summary['root_controller']['class'],
                    'sampleapp.controllers.root.RootController',
                )
                self.assertEqual(summary['root_controller']['source'], 'sampleapp/controllers/root.py:1')

    def test_summary_detects_disabled_database_and_auth_when_configured(self):
        self.install_fake_tg({
            'package_name': 'sampleapp',
            'renderers': [],
            'use_sqlalchemy': False,
            'use_ming': False,
            'auth_backend': None,
        })

        summary = collect_project_summary(str(self.project_root), config='development.ini')

        self.assertEqual(summary['database'], {'enabled': False, 'orm': None})
        self.assertEqual(summary['auth'], {'enabled': False})

    def test_human_summary_is_factual_and_omits_agent_playbook_content(self):
        summary = {
            'project_root': '/project',
            'config_file': '/project/development.ini',
            'package_name': 'sampleapp',
            'default_renderer': 'kajiki',
            'renderers': ['json', 'kajiki'],
            'paths': {'controllers': 'sampleapp/controllers', 'model': 'sampleapp/model'},
            'root_controller': {
                'class': 'sampleapp.controllers.root.RootController',
                'source': 'sampleapp/controllers/root.py:1',
            },
            'database': {'enabled': True, 'orm': 'sqlalchemy'},
            'auth': {'enabled': False},
        }

        output = format_project_summary(summary)

        self.assertIn('Project root: /project', output)
        self.assertIn('Configured renderers: json, kajiki', output)
        self.assertIn('Root controller: sampleapp.controllers.root.RootController (sampleapp/controllers/root.py:1)', output)
        self.assertIn('Database: enabled (sqlalchemy)', output)
        self.assertIn('Auth: disabled', output)
        for forbidden in ('count', 'pyproject', 'recipe', 'next step', 'agent playbook'):
            self.assertNotIn(forbidden, output.lower())

    def test_scaffolds_collects_gearbox_discovery_metadata_without_loading_app(self):
        scaffold_dir = self.project_root / 'controllers'
        scaffold_dir.mkdir()
        template_file = scaffold_dir / 'controller.py.template'
        template_file.write_text('controller scaffold')
        calls = []
        load_calls = self.install_fake_tg({'package_name': 'sampleapp'})
        gearbox = types.ModuleType('gearbox')
        scaffolding = types.ModuleType('gearbox.scaffolding')

        def discover_scaffold_templates(lookup):
            calls.append(lookup)
            return (
                types.SimpleNamespace(
                    name='controller',
                    path=str(template_file),
                    relative_dir='controllers',
                    output_extension='.py',
                ),
            )

        scaffolding.discover_scaffold_templates = discover_scaffold_templates
        gearbox.scaffolding = scaffolding

        with patch.dict(sys.modules, {'gearbox': gearbox, 'gearbox.scaffolding': scaffolding}):
            scaffolds = collect_project_scaffolds(str(self.project_root))

        self.assertEqual(calls, [str(self.project_root)])
        self.assertEqual(load_calls, [])
        self.assertEqual(scaffolds, [{
            'name': 'controller',
            'template_path': 'controllers/controller.py.template',
            'relative_dir': 'controllers',
            'output_extension': '.py',
            'default_output_pattern': 'controllers/{target}.py',
        }])

    def test_human_scaffolds_output_is_factual_and_omits_write_advice(self):
        output = format_project_scaffolds([{
            'name': 'controller',
            'template_path': 'controllers/controller.py.template',
            'relative_dir': 'controllers',
            'output_extension': '.py',
            'default_output_pattern': 'controllers/{target}.py',
        }])

        self.assertIn('controller [.py] controllers/controller.py.template -> controllers/{target}.py', output)
        for forbidden in ('mount', 'migration', 'setup-app', 'next step'):
            self.assertNotIn(forbidden, output.lower())


class TgInfoCommandTests(unittest.TestCase):
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

    def test_tginfo_is_registered_as_gearbox_project_command(self):
        pyproject = Path(__file__).parents[2] / 'pyproject.toml'
        in_project_commands = False
        project_commands = {}
        for raw_line in pyproject.read_text().splitlines():
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('['):
                in_project_commands = line == '[project.entry-points."gearbox.project_commands"]'
                continue
            if not in_project_commands or '=' not in line:
                continue
            name, value = line.split('=', 1)
            project_commands[name.strip()] = value.strip().strip('"')

        self.assertEqual(project_commands.get('tginfo'), 'devtools.gearbox.tginfo:TgInfoCommand')
        module_name, class_name = project_commands['tginfo'].split(':', 1)
        self.assertIs(getattr(importlib.import_module(module_name), class_name), self.module.TgInfoCommand)

    def test_parser_exposes_v1_subcommands_with_shared_options_and_no_all(self):
        parser = self.module.TgInfoCommand(None, {}).get_parser('gearbox tginfo')

        for subcommand in ('summary', 'routes', 'models', 'templates', 'scaffolds'):
            with self.subTest(subcommand=subcommand):
                opts = parser.parse_args([subcommand, '--project', '/project', '--config', 'test.ini', '--json'])
                self.assertEqual(opts.tginfo_command, subcommand)
                self.assertEqual(opts.project, '/project')
                self.assertEqual(opts.config_file, 'test.ini')
                self.assertTrue(opts.as_json)

        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(['all'])

    def test_summary_subcommand_prints_human_output_by_default(self):
        command = self.module.TgInfoCommand(None, {})
        opts = command.get_parser('gearbox tginfo').parse_args(['summary', '--project', '/project'])

        with patch.object(self.module, 'collect_project_summary', return_value={
            'project_root': '/project',
            'config_file': '/project/development.ini',
            'package_name': 'sampleapp',
            'default_renderer': 'kajiki',
            'renderers': ['json', 'kajiki'],
            'paths': {},
            'root_controller': {},
            'database': {'enabled': None, 'orm': None},
            'auth': {'enabled': None},
        }) as collector:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                command.take_action(opts)

        collector.assert_called_once_with(project='/project', config='development.ini')
        self.assertIn('Package: sampleapp', output.getvalue())

    def test_json_summary_uses_real_collector_without_startup_stdout_pollution(self):
        with tempfile.TemporaryDirectory() as tempdir:
            project_root = Path(tempdir)
            (project_root / 'development.ini').write_text('[app:main]\n')
            package = project_root / 'samplecmd'
            (package / 'controllers').mkdir(parents=True)
            (package / '__init__.py').write_text("print('package import banner')\n")
            (package / 'controllers' / '__init__.py').write_text('')
            (package / 'controllers' / 'root.py').write_text(textwrap.dedent('''\
                class RootController(object):
                    pass
            '''))

            old_modules = {
                name: sys.modules.get(name)
                for name in ('tg', 'paste', 'paste.deploy')
            }
            try:
                tg = types.ModuleType('tg')
                tg.config = {
                    'package_name': 'samplecmd',
                    'default_renderer': 'kajiki',
                    'renderers': ['json', 'kajiki'],
                    'application_root_module': 'samplecmd.controllers.root',
                    'use_sqlalchemy': False,
                    'use_ming': False,
                    'auth_backend': None,
                }
                paste = types.ModuleType('paste')
                deploy = types.ModuleType('paste.deploy')

                def loadapp(config_name, relative_to=None):
                    print('startup banner from app')
                    return object()

                deploy.loadapp = loadapp
                paste.deploy = deploy
                sys.modules['tg'] = tg
                sys.modules['paste'] = paste
                sys.modules['paste.deploy'] = deploy

                command = self.module.TgInfoCommand(None, {})
                opts = command.get_parser('gearbox tginfo').parse_args([
                    'summary', '--project', str(project_root), '--json',
                ])
                stdout = io.StringIO()
                stderr = io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    command.take_action(opts)
            finally:
                for name in list(sys.modules):
                    if name == 'samplecmd' or name.startswith('samplecmd.'):
                        sys.modules.pop(name, None)
                for name, module in old_modules.items():
                    if module is None:
                        sys.modules.pop(name, None)
                    else:
                        sys.modules[name] = module

        self.assertNotIn('startup banner from app', stdout.getvalue())
        self.assertNotIn('package import banner', stdout.getvalue())
        self.assertIn('startup banner from app', stderr.getvalue())
        self.assertIn('package import banner', stderr.getvalue())
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload['package_name'], 'samplecmd')
        self.assertEqual(payload['database'], {'enabled': False, 'orm': None})
        self.assertEqual(payload['auth'], {'enabled': False})

    def test_summary_subcommand_prints_json_when_requested(self):
        command = self.module.TgInfoCommand(None, {})
        opts = command.get_parser('gearbox tginfo').parse_args([
            'summary', '--project', '/project', '--config', 'test.ini', '--json',
        ])

        with patch.object(self.module, 'collect_project_summary', return_value={
            'project_root': '/project',
            'config_file': '/project/test.ini',
            'package_name': 'sampleapp',
            'default_renderer': 'kajiki',
            'renderers': ['json', 'kajiki'],
            'paths': {},
            'root_controller': {},
            'database': {'enabled': False, 'orm': None},
            'auth': {'enabled': False},
        }) as collector:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                command.take_action(opts)

        collector.assert_called_once_with(project='/project', config='test.ini')
        payload = json.loads(output.getvalue())
        self.assertEqual(payload['config_file'], '/project/test.ini')
        self.assertEqual(payload['database'], {'enabled': False, 'orm': None})

    def test_scaffolds_subcommand_prints_json_from_shared_collector(self):
        command = self.module.TgInfoCommand(None, {})
        opts = command.get_parser('gearbox tginfo').parse_args([
            'scaffolds', '--project', '/project', '--config', 'test.ini', '--json',
        ])

        with patch.object(self.module, 'collect_project_scaffolds', return_value=[{
            'name': 'controller',
            'template_path': 'controllers/controller.py.template',
            'relative_dir': 'controllers',
            'output_extension': '.py',
            'default_output_pattern': 'controllers/{target}.py',
        }]) as collector:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                command.take_action(opts)

        collector.assert_called_once_with(project='/project', config='test.ini')
        self.assertEqual(json.loads(output.getvalue()), [{
            'name': 'controller',
            'template_path': 'controllers/controller.py.template',
            'relative_dir': 'controllers',
            'output_extension': '.py',
            'default_output_pattern': 'controllers/{target}.py',
        }])


if __name__ == '__main__':
    unittest.main()
