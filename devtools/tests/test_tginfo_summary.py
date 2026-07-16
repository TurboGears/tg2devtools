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

        summary = self.run_tginfo('summary')

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

    def test_summary_action_loads_config_parsed_from_command_line(self):
        calls = self.install_fake_tg({})

        self.take_tginfo('summary', '--config', 'test.ini')

        self.assertEqual(calls, [
            ('config:test.ini', str(self.project_root), str(self.project_root), True),
        ])

    def test_summary_redirects_startup_stdout_away_from_collector_stdout(self):
        self.install_fake_tg({
            'package_name': 'sampleapp',
            'application_root_module': self.root_module,
        }, startup_stdout='startup banner from app')

        stdout, stderr = self.take_tginfo('summary', '--json')

        self.assertNotIn('startup banner from app', stdout)
        self.assertIn('startup banner from app', stderr)
        self.assertEqual(json.loads(stdout)['package_name'], 'sampleapp')

    def test_summary_imports_dotted_application_root_module(self):
        self.install_fake_tg({
            'package_name': 'sampleapp',
            'application_root_module': 'sampleapp.controllers.stringroot',
        })

        summary = self.run_tginfo('summary')

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

                summary = self.run_tginfo('summary')

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

        summary = self.run_tginfo('summary')

        self.assertEqual(summary['database'], {'enabled': False, 'orm': None})
        self.assertEqual(summary['auth'], {'enabled': False})

    def test_human_summary_is_factual_and_omits_agent_playbook_content(self):
        self.install_fake_tg({
            'package_name': 'sampleapp',
            'default_renderer': 'kajiki',
            'renderers': ['json', 'kajiki'],
            'application_root_module': self.root_module,
            'use_sqlalchemy': True,
            'use_ming': False,
            'auth_backend': None,
        })

        output, _ = self.take_tginfo('summary')

        self.assertIn(f'Project root: {self.project_root}', output)
        self.assertIn('Configured renderers: json, kajiki', output)
        self.assertIn('Root controller: sampleapp.controllers.root.RootController (sampleapp/controllers/root.py:1)', output)
        self.assertIn('Database: enabled (sqlalchemy)', output)
        self.assertIn('Auth: disabled', output)
        self.assertTrue(output.endswith('\n'))
        self.assertFalse(output.endswith('\n\n'))
        for forbidden in ('count', 'pyproject', 'recipe', 'next step', 'agent playbook'):
            self.assertNotIn(forbidden, output.lower())

    def test_scaffolds_lists_project_templates_without_loading_app(self):
        scaffold_dir = self.project_root / 'controllers'
        scaffold_dir.mkdir()
        template_file = scaffold_dir / 'controller.py.template'
        template_file.write_text('controller scaffold')
        load_calls = self.install_fake_tg({'package_name': 'sampleapp'})

        scaffolds = self.run_tginfo('scaffolds')
        output, _ = self.take_tginfo('scaffolds')

        self.assertEqual(load_calls, [])
        self.assertEqual(scaffolds, [{
            'name': 'controller',
            'template_path': 'controllers/controller.py.template',
            'relative_dir': 'controllers',
            'output_extension': '.py',
            'default_output_pattern': 'controllers/{target}.py',
        }])
        self.assertIn('controller [.py] controllers/controller.py.template -> controllers/{target}.py', output)
        self.assertTrue(output.endswith('\n'))
        self.assertFalse(output.endswith('\n\n'))
        for forbidden in ('mount', 'migration', 'setup-app', 'next step'):
            self.assertNotIn(forbidden, output.lower())


class TgInfoCommandTests(unittest.TestCase):
    def test_parser_exposes_subcommands_with_shared_options(self):
        parser = TgInfoCommand(None, {}).get_parser('gearbox tginfo')

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

    def test_gearbox_help_returns_the_requested_subcommand_parser(self):
        app_args = types.SimpleNamespace(help=True, cmd=['summary'])
        parser = TgInfoCommand(None, app_args).get_parser('gearbox tginfo')
        help_text = parser.format_help()

        self.assertIn('usage: gearbox tginfo summary', help_text)
        self.assertIn('--project PROJECT', help_text)
        self.assertIn('--config CONFIG_FILE', help_text)
        self.assertIn('--json', help_text)





if __name__ == '__main__':
    unittest.main()
