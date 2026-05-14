import json
import os
import sys

from gearbox.command import Command


SERVER_INSTRUCTIONS = (
    'Prefer TurboGears MCP tools for static inspection of routes, controllers, '
    'models, templates, and scaffolds. Use tg_scaffold or gearbox scaffold to '
    'create framework-conventional structure, then edit files directly. Do not '
    'run setup-app or migrations unless explicitly asked. For runtime request '
    'debugging, use gearbox tgshell -c development.ini with WebTest requests.'
)


class TgMcpCommand(Command):
    """Serve TurboGears MCP over JSON-RPC stdio."""

    def get_description(self):
        return 'Serve TurboGears MCP over stdio'

    def get_parser(self, prog_name):
        parser = super(TgMcpCommand, self).get_parser(prog_name)
        parser.add_argument('--project', default='.', help='project root directory (default: current directory)')
        parser.add_argument('-c', '--config', dest='config_file', default='development.ini',
                            help='application config file to read (default: development.ini)')
        return parser

    def take_action(self, opts):
        project_dir = os.path.realpath(os.path.abspath(os.path.expanduser(opts.project)))
        config_file = os.path.expanduser(opts.config_file)
        if not os.path.isabs(config_file):
            config_file = os.path.join(project_dir, config_file)
        config_file = os.path.realpath(os.path.abspath(config_file))
        opts.project = project_dir
        opts.config_file = config_file

        previous_cwd = os.getcwd()
        previous_sys_path = list(sys.path)
        try:
            os.chdir(project_dir)
            sys.path.insert(0, project_dir)
            _serve_mcp_stdio(sys.stdin, sys.stdout, sys.stderr)
        finally:
            sys.path[:] = previous_sys_path
            os.chdir(previous_cwd)


def _serve_mcp_stdio(stdin, stdout, stderr):
    server = _McpServer(stdout, stderr)
    for raw_line in stdin:
        line = raw_line.strip()
        if not line:
            continue
        server.handle_line(line)


class _McpServer:
    def __init__(self, stdout, stderr):
        self.stdout = stdout
        self.stderr = stderr

    def handle_line(self, line):
        try:
            message = json.loads(line)
        except ValueError:
            self._write_error(None, -32700, 'Parse error')
            return

        if not isinstance(message, dict):
            self._write_error(None, -32600, 'Invalid Request')
            return

        request_id = message.get('id')
        is_notification = 'id' not in message
        if message.get('jsonrpc') != '2.0' or not isinstance(message.get('method'), str):
            self._write_error(request_id if 'id' in message else None, -32600, 'Invalid Request')
            return

        method = message['method']
        if method == 'notifications/initialized':
            return

        if is_notification:
            return

        if method == 'initialize':
            self._write_result(request_id, self._initialize_result(message.get('params') or {}))
        elif method == 'tools/list':
            self._write_result(request_id, {'tools': []})
        elif method == 'tools/call':
            self._write_result(request_id, self._tool_execution_error(message.get('params') or {}))
        else:
            self._write_error(request_id, -32601, 'Method not found')

    def _initialize_result(self, params):
        protocol_version = '2024-11-05'
        if isinstance(params, dict) and isinstance(params.get('protocolVersion'), str):
            protocol_version = params['protocolVersion']
        return {
            'protocolVersion': protocol_version,
            'capabilities': {'tools': {}},
            'serverInfo': {'name': 'tg.devtools', 'version': '2.5.1dev1'},
            'instructions': SERVER_INSTRUCTIONS,
        }

    def _tool_execution_error(self, params):
        name = params.get('name') if isinstance(params, dict) else None
        if not name:
            name = 'unknown'
        return {
            'content': [{'type': 'text', 'text': 'Unknown tool: %s' % name}],
            'isError': True,
        }

    def _write_result(self, request_id, result):
        self._write({'jsonrpc': '2.0', 'id': request_id, 'result': result})

    def _write_error(self, request_id, code, message):
        self._write({'jsonrpc': '2.0', 'id': request_id, 'error': {'code': code, 'message': message}})

    def _write(self, message):
        json.dump(message, self.stdout, separators=(',', ':'), sort_keys=True)
        self.stdout.write('\n')
        self.stdout.flush()
