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

    def run_command(self, args):
        command = self.module.TgMcpCommand(None, {})
        opts = command.get_parser('gearbox tgmcp').parse_args(args)
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = 0
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                command.take_action(opts)
            except SystemExit as error:
                code = error.code
        return code, stdout.getvalue(), stderr.getvalue()

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

    def test_init_all_writes_client_configs_and_agents_idempotently(self):
        with tempfile.TemporaryDirectory() as project:
            with open(os.path.join(project, '.mcp.json'), 'w') as config:
                json.dump({
                    'unrelated': True,
                    'mcpServers': {'other': {'command': 'other'}},
                }, config)
            os.mkdir(os.path.join(project, '.codex'))
            with open(os.path.join(project, '.codex', 'config.toml'), 'w') as config:
                config.write('[other]\nvalue = 1\n\n[mcp_servers.other]\ncommand = "other"\n')
            with open(os.path.join(project, 'AGENTS.md'), 'w') as agents:
                agents.write('# Existing project guidance\n')

            code, stdout, stderr = self.run_command(['--project', project, 'init', 'all'])

            self.assertEqual(code, 0)
            self.assertIn('Configured TurboGears MCP init target all', stdout)
            self.assertEqual(stderr, '')
            with open(os.path.join(project, '.mcp.json')) as config:
                claude = json.load(config)
            self.assertTrue(claude['unrelated'])
            self.assertEqual(claude['mcpServers']['other'], {'command': 'other'})
            self.assertEqual(claude['mcpServers']['turbogears'], {
                'type': 'stdio',
                'command': 'gearbox',
                'args': ['tgmcp', '--project', '.', '--config', 'development.ini'],
            })
            with open(os.path.join(project, '.codex', 'config.toml')) as config:
                codex = config.read()
            self.assertIn('[other]\nvalue = 1', codex)
            self.assertIn('[mcp_servers.other]\ncommand = "other"', codex)
            self.assertIn('[mcp_servers.turbogears]', codex)
            self.assertIn('command = "gearbox"', codex)
            self.assertIn('args = ["tgmcp", "--project", ".", "--config", "development.ini"]', codex)
            self.assertIn('enabled = true', codex)
            with open(os.path.join(project, '.vscode', 'mcp.json')) as config:
                vscode = json.load(config)
            self.assertEqual(vscode['servers']['turbogears'], {
                'type': 'stdio',
                'command': 'gearbox',
                'args': ['tgmcp', '--project', '${workspaceFolder}', '--config', 'development.ini'],
            })
            with open(os.path.join(project, 'AGENTS.md')) as agents:
                agents_md = agents.read()
            self.assertIn('# Existing project guidance', agents_md)
            self.assertIn('## TurboGears DevTools', agents_md)

            snapshots = {}
            for relative_path in ('.mcp.json', '.codex/config.toml', '.vscode/mcp.json', 'AGENTS.md'):
                with open(os.path.join(project, relative_path)) as generated:
                    snapshots[relative_path] = generated.read()
            code, stdout, stderr = self.run_command(['--project', project, 'init', 'all'])

            self.assertEqual(code, 0)
            self.assertEqual(stderr, '')
            for relative_path, expected in snapshots.items():
                with open(os.path.join(project, relative_path)) as generated:
                    self.assertEqual(generated.read(), expected)

    def test_init_respects_single_targets_and_no_agents_md(self):
        with tempfile.TemporaryDirectory() as project:
            code, stdout, stderr = self.run_command(['--project', project, 'init', 'claude', '--no-agents-md'])

            self.assertEqual(code, 0)
            self.assertIn('Configured TurboGears MCP init target claude', stdout)
            self.assertEqual(stderr, '')
            self.assertTrue(os.path.exists(os.path.join(project, '.mcp.json')))
            self.assertFalse(os.path.exists(os.path.join(project, 'AGENTS.md')))
            self.assertFalse(os.path.exists(os.path.join(project, '.codex')))
            self.assertFalse(os.path.exists(os.path.join(project, '.vscode')))

        with tempfile.TemporaryDirectory() as project:
            code, stdout, stderr = self.run_command(['--project', project, 'init', 'codex'])

            self.assertEqual(code, 0)
            self.assertIn('Configured TurboGears MCP init target codex', stdout)
            self.assertEqual(stderr, '')
            self.assertTrue(os.path.exists(os.path.join(project, '.codex', 'config.toml')))
            self.assertTrue(os.path.exists(os.path.join(project, 'AGENTS.md')))
            self.assertFalse(os.path.exists(os.path.join(project, '.mcp.json')))
            self.assertFalse(os.path.exists(os.path.join(project, '.vscode')))

        with tempfile.TemporaryDirectory() as project:
            code, stdout, stderr = self.run_command(['--project', project, 'init', 'vscode'])

            self.assertEqual(code, 0)
            self.assertIn('Configured TurboGears MCP init target vscode', stdout)
            self.assertEqual(stderr, '')
            self.assertTrue(os.path.exists(os.path.join(project, '.vscode', 'mcp.json')))
            self.assertTrue(os.path.exists(os.path.join(project, 'AGENTS.md')))
            self.assertFalse(os.path.exists(os.path.join(project, '.mcp.json')))
            self.assertFalse(os.path.exists(os.path.join(project, '.codex')))

        with tempfile.TemporaryDirectory() as project:
            code, stdout, stderr = self.run_command(['--project', project, 'init', 'pi'])

            self.assertEqual(code, 0)
            self.assertIn('Configured TurboGears MCP init target pi', stdout)
            self.assertEqual(stderr, '')
            self.assertTrue(os.path.exists(os.path.join(project, 'AGENTS.md')))
            self.assertFalse(os.path.exists(os.path.join(project, '.mcp.json')))
            self.assertFalse(os.path.exists(os.path.join(project, '.codex')))
            self.assertFalse(os.path.exists(os.path.join(project, '.vscode')))

    def test_init_updates_existing_turbogears_entries_while_preserving_unrelated_config(self):
        with tempfile.TemporaryDirectory() as project:
            with open(os.path.join(project, '.mcp.json'), 'w') as config:
                json.dump({
                    'mcpServers': {
                        'turbogears': {'command': 'old-gearbox', 'args': ['old']},
                        'other': {'command': 'other'},
                    },
                    'unrelated': {'keep': True},
                }, config)
            os.mkdir(os.path.join(project, '.codex'))
            with open(os.path.join(project, '.codex', 'config.toml'), 'w') as config:
                config.write(
                    '[top]\nvalue = 1\n\n'
                    '[mcp_servers.turbogears]\ncommand = "old-gearbox"\nargs = ["old"]\nenabled = false\n\n'
                    '[mcp_servers.other]\ncommand = "other"\n'
                )
            os.mkdir(os.path.join(project, '.vscode'))
            with open(os.path.join(project, '.vscode', 'mcp.json'), 'w') as config:
                json.dump({
                    'servers': {
                        'turbogears': {'command': 'old-gearbox', 'args': ['old']},
                        'other': {'command': 'other'},
                    },
                    'unrelated': True,
                }, config)

            code, stdout, stderr = self.run_command(['--project', project, 'init', 'all', '--no-agents-md'])

            self.assertEqual(code, 0)
            self.assertIn('Configured TurboGears MCP init target all', stdout)
            self.assertEqual(stderr, '')
            with open(os.path.join(project, '.mcp.json')) as config:
                claude = json.load(config)
            self.assertEqual(claude['mcpServers']['other'], {'command': 'other'})
            self.assertEqual(claude['unrelated'], {'keep': True})
            self.assertEqual(claude['mcpServers']['turbogears']['command'], 'gearbox')
            self.assertEqual(claude['mcpServers']['turbogears']['args'], ['tgmcp', '--project', '.', '--config', 'development.ini'])
            with open(os.path.join(project, '.codex', 'config.toml')) as config:
                codex = config.read()
            self.assertIn('[top]\nvalue = 1', codex)
            self.assertIn('[mcp_servers.other]\ncommand = "other"', codex)
            self.assertEqual(codex.count('[mcp_servers.turbogears]'), 1)
            self.assertIn('command = "gearbox"', codex)
            self.assertIn('args = ["tgmcp", "--project", ".", "--config", "development.ini"]', codex)
            self.assertNotIn('old-gearbox', codex)
            with open(os.path.join(project, '.vscode', 'mcp.json')) as config:
                vscode = json.load(config)
            self.assertEqual(vscode['servers']['other'], {'command': 'other'})
            self.assertTrue(vscode['unrelated'])
            self.assertEqual(vscode['servers']['turbogears']['command'], 'gearbox')
            self.assertEqual(vscode['servers']['turbogears']['args'], ['tgmcp', '--project', '${workspaceFolder}', '--config', 'development.ini'])
            self.assertFalse(os.path.exists(os.path.join(project, 'AGENTS.md')))

    def test_init_invalid_existing_config_fails_without_overwrite_and_prints_snippet(self):
        with tempfile.TemporaryDirectory() as project:
            path = os.path.join(project, '.mcp.json')
            with open(path, 'w') as config:
                config.write('{not-json')

            code, stdout, stderr = self.run_command(['--project', project, 'init', 'claude'])

            self.assertEqual(code, 1)
            self.assertEqual(stdout, '')
            self.assertIn('invalid JSON', stderr)
            self.assertIn('"mcpServers"', stderr)
            self.assertIn('"turbogears"', stderr)
            with open(path) as config:
                self.assertEqual(config.read(), '{not-json')

        with tempfile.TemporaryDirectory() as project:
            claude_path = os.path.join(project, '.mcp.json')
            with open(claude_path, 'w') as config:
                config.write('{"mcpServers": {"keep": {"command": "keep"}}}')
            os.mkdir(os.path.join(project, '.codex'))
            path = os.path.join(project, '.codex', 'config.toml')
            with open(path, 'w') as config:
                config.write('[not-valid')

            code, stdout, stderr = self.run_command(['--project', project, 'init', 'all'])

            self.assertEqual(code, 1)
            self.assertEqual(stdout, '')
            if self.module.tomllib is None:
                self.assertIn('TOML parsing is unavailable', stderr)
            else:
                self.assertIn('invalid TOML', stderr)
            self.assertIn('[mcp_servers.turbogears]', stderr)
            with open(path) as config:
                self.assertEqual(config.read(), '[not-valid')
            with open(claude_path) as config:
                self.assertEqual(config.read(), '{"mcpServers": {"keep": {"command": "keep"}}}')
            self.assertFalse(os.path.exists(os.path.join(project, '.vscode')))
            self.assertFalse(os.path.exists(os.path.join(project, 'AGENTS.md')))

    def test_init_valid_but_unsafe_existing_config_fails_without_overwrite(self):
        with tempfile.TemporaryDirectory() as project:
            path = os.path.join(project, '.mcp.json')
            with open(path, 'w') as config:
                config.write('{"mcpServers": "not-an-object", "keep": true}')

            code, stdout, stderr = self.run_command(['--project', project, 'init', 'claude'])

            self.assertEqual(code, 1)
            self.assertEqual(stdout, '')
            self.assertIn('mcpServers is not an object', stderr)
            self.assertIn('"mcpServers"', stderr)
            with open(path) as config:
                self.assertEqual(config.read(), '{"mcpServers": "not-an-object", "keep": true}')

        if self.module.tomllib is not None:
            with tempfile.TemporaryDirectory() as project:
                os.mkdir(os.path.join(project, '.codex'))
                path = os.path.join(project, '.codex', 'config.toml')
                with open(path, 'w') as config:
                    config.write('[mcp_servers]\nturbogears = "not-a-table"\nother = "keep"\n')

                code, stdout, stderr = self.run_command(['--project', project, 'init', 'codex'])

                self.assertEqual(code, 1)
                self.assertEqual(stdout, '')
                self.assertIn('mcp_servers.turbogears is not a table', stderr)
                self.assertIn('[mcp_servers.turbogears]', stderr)
                with open(path) as config:
                    self.assertEqual(config.read(), '[mcp_servers]\nturbogears = "not-a-table"\nother = "keep"\n')

    def test_init_preflights_destinations_before_writing_any_config(self):
        with tempfile.TemporaryDirectory() as project:
            claude_path = os.path.join(project, '.mcp.json')
            with open(claude_path, 'w') as config:
                config.write('{"mcpServers": {"keep": {"command": "keep"}}}')
            with open(os.path.join(project, '.codex'), 'w') as config:
                config.write('not-a-directory')

            code, stdout, stderr = self.run_command(['--project', project, 'init', 'all'])

            self.assertEqual(code, 1)
            self.assertEqual(stdout, '')
            self.assertIn('parent path is not a directory', stderr)
            self.assertIn('[mcp_servers.turbogears]', stderr)
            with open(claude_path) as config:
                self.assertEqual(config.read(), '{"mcpServers": {"keep": {"command": "keep"}}}')
            with open(os.path.join(project, '.codex')) as config:
                self.assertEqual(config.read(), 'not-a-directory')
            self.assertFalse(os.path.exists(os.path.join(project, '.vscode')))
            self.assertFalse(os.path.exists(os.path.join(project, 'AGENTS.md')))

    def test_init_apply_failure_restores_earlier_writes_and_leaves_later_configs_unchanged(self):
        with tempfile.TemporaryDirectory() as project:
            claude_path = os.path.join(project, '.mcp.json')
            codex_dir = os.path.join(project, '.codex')
            codex_path = os.path.join(codex_dir, 'config.toml')
            vscode_dir = os.path.join(project, '.vscode')
            vscode_path = os.path.join(vscode_dir, 'mcp.json')
            agents_path = os.path.join(project, 'AGENTS.md')
            os.mkdir(codex_dir)
            os.mkdir(vscode_dir)
            originals = {
                claude_path: '{"mcpServers": {"keep": {"command": "keep"}}}',
                codex_path: '[mcp_servers.keep]\ncommand = "keep"\n',
                vscode_path: '{"servers": {"keep": {"command": "keep"}}}',
                agents_path: '# Existing agent guidance\n',
            }
            for path, content in originals.items():
                with open(path, 'w') as config:
                    config.write(content)

            real_replace = self.module.os.replace
            replace_calls = []

            def fail_on_codex_replace(source, destination):
                replace_calls.append(destination)
                if destination == codex_path:
                    raise OSError('simulated replace failure')
                return real_replace(source, destination)

            with patch.object(self.module.os, 'replace', side_effect=fail_on_codex_replace):
                code, stdout, stderr = self.run_command(['--project', project, 'init', 'all'])

            self.assertEqual(code, 1)
            self.assertEqual(stdout, '')
            self.assertIn('simulated replace failure', stderr)
            self.assertEqual(replace_calls, [claude_path, codex_path])
            for path, content in originals.items():
                with open(path) as config:
                    self.assertEqual(config.read(), content)
            for directory in (project, codex_dir, vscode_dir):
                self.assertFalse(any(name.startswith('.tgmcp-init-') for name in os.listdir(directory)))

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
