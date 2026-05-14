import argparse
import contextlib
import importlib
import io
import json
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


class TgMcpProtocolTests(unittest.TestCase):
    def setUp(self):
        self.previous_modules = {
            name: sys.modules.get(name)
            for name in (
                'gearbox', 'gearbox.command', 'gearbox.commands',
                'gearbox.commands.scaffold', 'devtools.gearbox.scaffold',
                'devtools.gearbox.tgmcp',
            )
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
        sys.modules.pop('devtools.gearbox.tgmcp', None)
        self.module = importlib.import_module('devtools.gearbox.tgmcp')

    def tearDown(self):
        sys.modules.pop('devtools.gearbox.tgmcp', None)
        for name, module in self.previous_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def serve(self, messages, project='.', config='development.ini'):
        stdin = io.StringIO(''.join(json.dumps(message) + '\n' for message in messages))
        stdout = io.StringIO()
        stderr = io.StringIO()
        self.module._serve_mcp_stdio(stdin, stdout, stderr, project, config)
        return [json.loads(line) for line in stdout.getvalue().splitlines()], stderr.getvalue()

    def install_fake_scaffold_command(self, calls, supports_dry_run=True):
        commands = types.ModuleType('gearbox.commands')
        scaffold = types.ModuleType('gearbox.commands.scaffold')

        class ScaffoldCommand(object):
            def __init__(self, *args, **kwargs):
                pass

            def get_parser(self, prog_name):
                parser = argparse.ArgumentParser(prog=prog_name)
                parser.add_argument('scaffold_name', nargs='+')
                parser.add_argument('target')
                parser.add_argument('--lookup')
                parser.add_argument('--path')
                parser.add_argument('--subdir')
                parser.add_argument('--no-package', dest='nopackage', action='store_true')
                if supports_dry_run:
                    parser.add_argument('--dry-run', dest='dry_run', action='store_true')
                parser.add_argument('--json', dest='as_json', action='store_true')
                return parser

            def take_action(self, opts):
                calls.append({'cwd': os.getcwd(), 'opts': vars(opts)})
                print(json.dumps({
                    'target': opts.target,
                    'scaffolds': opts.scaffold_name,
                    'lookup': opts.lookup,
                    'path': opts.path,
                    'subdir': opts.subdir,
                    'no_package': opts.nopackage,
                    'dry_run': getattr(opts, 'dry_run', False),
                    'json': opts.as_json,
                }))

        scaffold.ScaffoldCommand = ScaffoldCommand
        commands.scaffold = scaffold
        sys.modules['gearbox'].commands = commands
        sys.modules['gearbox.commands'] = commands
        sys.modules['gearbox.commands.scaffold'] = scaffold

    def test_initialize_initialized_tools_list_and_unknown_tool_call(self):
        responses, stderr = self.serve([
            {
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'initialize',
                'params': {'protocolVersion': '2025-03-26'},
            },
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
            {
                'jsonrpc': '2.0',
                'id': 3,
                'method': 'tools/call',
                'params': {'name': 'tg_definitely_not_a_real_tool'},
            },
            {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call'},
        ])

        self.assertEqual(stderr, '')
        self.assertTrue(all(response['jsonrpc'] == '2.0' for response in responses))
        self.assertEqual([response['id'] for response in responses], [1, 2, 3, 4])
        initialize = responses[0]['result']
        self.assertEqual(initialize['protocolVersion'], '2025-03-26')
        self.assertEqual(initialize['capabilities'], {'tools': {}})
        self.assertEqual(initialize['serverInfo']['name'], 'tg.devtools')
        instructions = initialize['instructions']
        self.assertIn('Prefer TurboGears MCP tools', instructions)
        self.assertIn('gearbox scaffold', instructions)
        self.assertNotIn('tg_scaffold', instructions)
        self.assertIn('edit files directly', instructions)
        self.assertIn('Do not run setup-app or migrations unless explicitly asked', instructions)
        self.assertIn('tgshell -c development.ini', instructions)
        self.assertIn('WebTest', instructions)
        tools = responses[1]['result']['tools']
        self.assertEqual(
            [tool['name'] for tool in tools],
            ['tg_project_summary', 'tg_list_routes', 'tg_list_models', 'tg_list_templates', 'tg_list_scaffolds', 'tg_scaffold'],
        )
        for tool in tools:
            self.assertTrue(tool['name'].startswith('tg_'))
            self.assertNotIn('playbook', tool['description'].lower())
            self.assertIn('Use', tool['description'])
            self.assertEqual(tool['inputSchema']['type'], 'object')
            self.assertFalse(tool['inputSchema']['additionalProperties'])
            self.assertEqual(tool['outputSchema']['type'], 'object')
        for tool in tools[:-1]:
            self.assertEqual(tool['inputSchema']['properties'], {})
        scaffold_tool = tools[-1]
        self.assertEqual(scaffold_tool['inputSchema']['required'], ['scaffolds', 'target'])
        self.assertIn('dry_run', scaffold_tool['inputSchema']['properties'])
        self.assertIn('no_package', scaffold_tool['inputSchema']['properties'])
        self.assertNotIn('tg_trace_url', [tool['name'] for tool in tools])
        self.assertNotIn('tg_run_gearbox', [tool['name'] for tool in tools])
        self.assertTrue(responses[2]['result']['isError'])
        self.assertEqual(responses[2]['result']['content'][0]['type'], 'text')
        self.assertIn(
            'Unknown tool: tg_definitely_not_a_real_tool',
            responses[2]['result']['content'][0]['text'],
        )
        self.assertTrue(responses[3]['result']['isError'])
        self.assertIn('Unknown tool: unknown', responses[3]['result']['content'][0]['text'])

    def test_tools_call_returns_structured_results_from_tginfo_collectors(self):
        original_collectors = {
            name: tool['collector']
            for name, tool in self.module._READ_TOOLS_BY_NAME.items()
        }
        calls = []

        def collector(name, value):
            def collect(project='.', config='development.ini'):
                calls.append((name, project, config))
                return value
            return collect

        try:
            self.module._READ_TOOLS_BY_NAME['tg_project_summary']['collector'] = collector(
                'tg_project_summary', {'package_name': 'sample'}
            )
            self.module._READ_TOOLS_BY_NAME['tg_list_routes']['collector'] = collector(
                'tg_list_routes', [{'path': '/', 'kind': 'index'}]
            )
            self.module._READ_TOOLS_BY_NAME['tg_list_models']['collector'] = collector(
                'tg_list_models', [{'name': 'User', 'orm': 'sqlalchemy'}]
            )
            self.module._READ_TOOLS_BY_NAME['tg_list_templates']['collector'] = collector(
                'tg_list_templates', [{'file': 'sample/templates/index.xhtml'}]
            )
            self.module._READ_TOOLS_BY_NAME['tg_list_scaffolds']['collector'] = collector(
                'tg_list_scaffolds', [{'name': 'controller'}]
            )

            responses, stderr = self.serve([
                {
                    'jsonrpc': '2.0',
                    'id': index,
                    'method': 'tools/call',
                    'params': {'name': name, 'arguments': {}},
                }
                for index, name in enumerate([
                    'tg_project_summary',
                    'tg_list_routes',
                    'tg_list_models',
                    'tg_list_templates',
                    'tg_list_scaffolds',
                ], 1)
            ], project='/project', config='/project/development.ini')
        finally:
            for name, collect in original_collectors.items():
                self.module._READ_TOOLS_BY_NAME[name]['collector'] = collect

        self.assertEqual(stderr, '')
        self.assertEqual(calls, [
            ('tg_project_summary', '/project', '/project/development.ini'),
            ('tg_list_routes', '/project', '/project/development.ini'),
            ('tg_list_models', '/project', '/project/development.ini'),
            ('tg_list_templates', '/project', '/project/development.ini'),
            ('tg_list_scaffolds', '/project', '/project/development.ini'),
        ])
        self.assertEqual(responses[0]['result']['structuredContent'], {'summary': {'package_name': 'sample'}})
        self.assertEqual(responses[1]['result']['structuredContent'], {'routes': [{'path': '/', 'kind': 'index'}]})
        self.assertEqual(responses[2]['result']['structuredContent'], {'models': [{'name': 'User', 'orm': 'sqlalchemy'}]})
        self.assertEqual(responses[3]['result']['structuredContent'], {'templates': [{'file': 'sample/templates/index.xhtml'}]})
        self.assertEqual(responses[4]['result']['structuredContent'], {'scaffolds': [{'name': 'controller'}]})
        for response in responses:
            content = response['result']['content']
            self.assertEqual(content[0]['type'], 'text')
            self.assertEqual(json.loads(content[0]['text']), response['result']['structuredContent'])

    def test_tg_scaffold_calls_gearbox_with_options_and_adds_relevant_hints(self):
        calls = []
        self.install_fake_scaffold_command(calls)

        with tempfile.TemporaryDirectory() as project:
            responses, stderr = self.serve([{
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'tools/call',
                'params': {
                    'name': 'tg_scaffold',
                    'arguments': {
                        'scaffolds': ['controller', 'model', 'template', 'custom'],
                        'target': 'photo',
                        'lookup': 'scaffolds',
                        'path': 'generated',
                        'subdir': 'admin',
                        'no_package': True,
                        'dry_run': True,
                    },
                },
            }], project=project, config=os.path.join(project, 'development.ini'))

        self.assertEqual(stderr, '')
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['cwd'], os.path.realpath(project))
        self.assertEqual(calls[0]['opts']['scaffold_name'], ['controller', 'model', 'template', 'custom'])
        self.assertEqual(calls[0]['opts']['target'], 'photo')
        self.assertEqual(calls[0]['opts']['lookup'], 'scaffolds')
        self.assertEqual(calls[0]['opts']['path'], 'generated')
        self.assertEqual(calls[0]['opts']['subdir'], 'admin')
        self.assertTrue(calls[0]['opts']['nopackage'])
        self.assertTrue(calls[0]['opts']['dry_run'])
        self.assertTrue(calls[0]['opts']['as_json'])
        structured = responses[0]['result']['structuredContent']['scaffold']
        self.assertEqual(structured['gearbox']['target'], 'photo')
        self.assertEqual(structured['gearbox']['scaffolds'], ['controller', 'model', 'template', 'custom'])
        self.assertEqual(
            structured['next_steps'],
            [
                {'scaffold': 'controller', 'hint': 'Mount the controller in RootController if a URL is desired.'},
                {'scaffold': 'model', 'hint': 'Import the model from the model package if it should be exported; create or review migrations manually if needed.'},
                {'scaffold': 'template', 'hint': 'Expose the template from a controller action if it should be reachable.'},
            ],
        )
        self.assertEqual(
            json.loads(responses[0]['result']['content'][0]['text']),
            responses[0]['result']['structuredContent'],
        )

    def test_tg_scaffold_does_not_default_to_dry_run_or_hint_for_custom_scaffolds(self):
        calls = []
        self.install_fake_scaffold_command(calls)

        with tempfile.TemporaryDirectory() as project:
            responses, stderr = self.serve([{
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'tools/call',
                'params': {
                    'name': 'tg_scaffold',
                    'arguments': {'scaffolds': ['custom'], 'target': 'photo'},
                },
            }], project=project, config=os.path.join(project, 'development.ini'))

        self.assertEqual(stderr, '')
        self.assertFalse(calls[0]['opts']['dry_run'])
        structured = responses[0]['result']['structuredContent']['scaffold']
        self.assertFalse(structured['gearbox']['dry_run'])
        self.assertEqual(structured['next_steps'], [])

    def test_tg_scaffold_reports_unsupported_dry_run_as_tool_error_without_calling_gearbox(self):
        calls = []
        self.install_fake_scaffold_command(calls, supports_dry_run=False)

        responses, stderr = self.serve([{
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {
                'name': 'tg_scaffold',
                'arguments': {'scaffolds': ['controller'], 'target': 'photo', 'dry_run': True},
            },
        }])

        self.assertEqual(stderr, '')
        self.assertEqual(calls, [])
        self.assertTrue(responses[0]['result']['isError'])
        self.assertIn('Gearbox scaffold does not support --dry-run', responses[0]['result']['content'][0]['text'])

    def test_tg_scaffold_parser_error_returns_tool_error_without_calling_gearbox(self):
        calls = []
        self.install_fake_scaffold_command(calls)

        responses, stderr = self.serve([{
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {
                'name': 'tg_scaffold',
                'arguments': {'scaffolds': ['--bad'], 'target': 'photo'},
            },
        }])

        self.assertEqual(stderr, '')
        self.assertEqual(calls, [])
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]['jsonrpc'], '2.0')
        self.assertTrue(responses[0]['result']['isError'])
        self.assertIn('tg_scaffold failed:', responses[0]['result']['content'][0]['text'])
        self.assertIn('gearbox scaffold: error:', responses[0]['result']['content'][0]['text'])

    def test_protocol_errors_are_json_rpc_messages(self):
        stdin = io.StringIO('not-json\n[]\n' + json.dumps({'jsonrpc': '2.0'}) + '\n' + json.dumps({
            'jsonrpc': '2.0', 'id': 'missing', 'method': 'tg/missing',
        }) + '\n')
        stdout = io.StringIO()
        stderr = io.StringIO()

        self.module._serve_mcp_stdio(stdin, stdout, stderr)

        self.assertEqual(stderr.getvalue(), '')
        responses = [json.loads(line) for line in stdout.getvalue().splitlines()]
        self.assertTrue(all(response['jsonrpc'] == '2.0' for response in responses))
        self.assertEqual(responses[0]['error']['code'], -32700)
        self.assertEqual(responses[0]['id'], None)
        self.assertEqual(responses[1]['error']['code'], -32600)
        self.assertEqual(responses[1]['id'], None)
        self.assertEqual(responses[2]['error']['code'], -32600)
        self.assertEqual(responses[2]['id'], None)
        self.assertEqual(responses[3]['error']['code'], -32601)
        self.assertEqual(responses[3]['id'], 'missing')

    def test_command_enters_project_context_and_serves_real_stdio(self):
        command = self.module.TgMcpCommand(None, {})
        previous_cwd = os.getcwd()
        previous_sys_path = list(sys.path)

        class ObservingStdin(object):
            def __init__(self):
                self.cwd_during_read = None
                self.path_during_read = None

            def __iter__(self):
                self.cwd_during_read = os.getcwd()
                self.path_during_read = sys.path[0]
                yield json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}) + '\n'

        with tempfile.TemporaryDirectory() as base:
            home = os.path.join(base, 'home')
            project = os.path.join(base, 'real-project')
            configs = os.path.join(base, 'real-configs')
            os.mkdir(home)
            os.mkdir(project)
            os.mkdir(configs)
            os.symlink(project, os.path.join(home, 'project-link'))
            os.symlink(configs, os.path.join(project, 'configs'))
            opts = command.get_parser('gearbox tgmcp').parse_args([
                '--project', '~/project-link',
                '--config', 'configs/test.ini',
            ])
            stdin = ObservingStdin()
            stdout = io.StringIO()
            stderr = io.StringIO()

            with patch.dict(os.environ, {'HOME': home}), patch.object(sys, 'stdin', stdin):
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    command.take_action(opts)

            project_dir = os.path.realpath(project)
            self.assertEqual(stdin.cwd_during_read, project_dir)
            self.assertEqual(stdin.path_during_read, project_dir)
            self.assertEqual(opts.project, project_dir)
            self.assertEqual(opts.config_file, os.path.join(configs, 'test.ini'))

        self.assertEqual(os.getcwd(), previous_cwd)
        self.assertEqual(sys.path, previous_sys_path)
        responses = [json.loads(line) for line in stdout.getvalue().splitlines()]
        self.assertEqual(responses[0]['jsonrpc'], '2.0')
        self.assertEqual(responses[0]['id'], 1)
        self.assertEqual(
            [tool['name'] for tool in responses[0]['result']['tools']],
            ['tg_project_summary', 'tg_list_routes', 'tg_list_models', 'tg_list_templates', 'tg_list_scaffolds', 'tg_scaffold'],
        )
        self.assertEqual(stderr.getvalue(), '')

    def test_command_normalizes_absolute_config_with_user_and_realpath(self):
        command = self.module.TgMcpCommand(None, {})
        previous_cwd = os.getcwd()
        previous_sys_path = list(sys.path)

        with tempfile.TemporaryDirectory() as base:
            home = os.path.join(base, 'home')
            project = os.path.join(base, 'project')
            config = os.path.join(base, 'config.ini')
            os.mkdir(home)
            os.mkdir(project)
            open(config, 'w').close()
            os.symlink(config, os.path.join(home, 'config-link.ini'))
            opts = command.get_parser('gearbox tgmcp').parse_args([
                '--project', project,
                '--config', '~/config-link.ini',
            ])

            with patch.dict(os.environ, {'HOME': home}), patch.object(sys, 'stdin', io.StringIO('')):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    command.take_action(opts)

            self.assertEqual(opts.config_file, config)

        self.assertEqual(os.getcwd(), previous_cwd)
        self.assertEqual(sys.path, previous_sys_path)


if __name__ == '__main__':
    unittest.main()
