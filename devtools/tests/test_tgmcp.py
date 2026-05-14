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
            for name in ('gearbox', 'gearbox.command', 'devtools.gearbox.tgmcp')
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

    def serve(self, messages):
        stdin = io.StringIO(''.join(json.dumps(message) + '\n' for message in messages))
        stdout = io.StringIO()
        stderr = io.StringIO()
        self.module._serve_mcp_stdio(stdin, stdout, stderr)
        return [json.loads(line) for line in stdout.getvalue().splitlines()], stderr.getvalue()

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
        self.assertIn('edit files directly', instructions)
        self.assertIn('Do not run setup-app or migrations unless explicitly asked', instructions)
        self.assertIn('tgshell -c development.ini', instructions)
        self.assertIn('WebTest', instructions)
        self.assertEqual(responses[1]['result'], {'tools': []})
        self.assertTrue(responses[2]['result']['isError'])
        self.assertEqual(responses[2]['result']['content'][0]['type'], 'text')
        self.assertIn(
            'Unknown tool: tg_definitely_not_a_real_tool',
            responses[2]['result']['content'][0]['text'],
        )
        self.assertTrue(responses[3]['result']['isError'])
        self.assertIn('Unknown tool: unknown', responses[3]['result']['content'][0]['text'])

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
        self.assertEqual(responses, [{'jsonrpc': '2.0', 'id': 1, 'result': {'tools': []}}])
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
