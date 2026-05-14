import json
import os
import sys
from contextlib import redirect_stdout

from gearbox.command import Command

from devtools.gearbox.scaffold import scaffold_project
from devtools.gearbox.tginfo_summary import (
    collect_project_models,
    collect_project_routes,
    collect_project_scaffolds,
    collect_project_summary,
    collect_project_templates,
)


SERVER_INSTRUCTIONS = (
    'Prefer TurboGears MCP tools for static inspection of routes, controllers, '
    'models, templates, and scaffolds. Use gearbox scaffold to create '
    'framework-conventional structure, then edit files directly. Do not run '
    'setup-app or migrations unless explicitly asked. For runtime request '
    'debugging, use gearbox tgshell -c development.ini with WebTest requests.'
)

_READ_TOOLS = [
    {
        'name': 'tg_project_summary',
        'description': (
            'Use to get factual TurboGears project basics: package, renderers, '
            'paths, root controller, database, and auth state.'
        ),
        'result_key': 'summary',
        'collector': collect_project_summary,
        'output_type': 'object',
    },
    {
        'name': 'tg_list_routes',
        'description': (
            'Use to inspect the static TurboGears object-dispatch route map, '
            'exposed actions, params, requirements, validations, and templates.'
        ),
        'result_key': 'routes',
        'collector': collect_project_routes,
        'output_type': 'array',
    },
    {
        'name': 'tg_list_models',
        'description': (
            'Use to list models exported by the project model package, including '
            'ORM kind, source, and docstrings when available.'
        ),
        'result_key': 'models',
        'collector': collect_project_models,
        'output_type': 'array',
    },
    {
        'name': 'tg_list_templates',
        'description': (
            'Use to inventory recognized template files and see which static '
            'routes expose each template.'
        ),
        'result_key': 'templates',
        'collector': collect_project_templates,
        'output_type': 'array',
    },
    {
        'name': 'tg_list_scaffolds',
        'description': (
            'Use to discover available Gearbox scaffold templates before '
            'creating conventional project structure.'
        ),
        'result_key': 'scaffolds',
        'collector': collect_project_scaffolds,
        'output_type': 'array',
    },
]

_SCAFFOLD_TOOL = {
    'name': 'tg_scaffold',
    'description': (
        'Use to create conventional project files through Gearbox scaffold. '
        'Pass dry_run only when you want Gearbox dry-run behavior and the '
        'installed Gearbox supports it.'
    ),
    'result_key': 'scaffold',
}

_READ_TOOLS_BY_NAME = {tool['name']: tool for tool in _READ_TOOLS}


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
            _serve_mcp_stdio(sys.stdin, sys.stdout, sys.stderr, project_dir, config_file)
        finally:
            sys.path[:] = previous_sys_path
            os.chdir(previous_cwd)


def _serve_mcp_stdio(stdin, stdout, stderr, project='.', config='development.ini'):
    server = _McpServer(stdout, stderr, project, config)
    for raw_line in stdin:
        line = raw_line.strip()
        if not line:
            continue
        server.handle_line(line)


class _McpServer:
    def __init__(self, stdout, stderr, project, config):
        self.stdout = stdout
        self.stderr = stderr
        self.project = project
        self.config = config

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
            self._write_result(request_id, {'tools': self._tool_definitions()})
        elif method == 'tools/call':
            self._write_result(request_id, self._call_tool(message.get('params') or {}))
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

    def _tool_definitions(self):
        tools = []
        for tool in _READ_TOOLS:
            result_key = tool['result_key']
            tools.append({
                'name': tool['name'],
                'description': tool['description'],
                'inputSchema': {
                    'type': 'object',
                    'properties': {},
                    'additionalProperties': False,
                },
                'outputSchema': {
                    'type': 'object',
                    'properties': {
                        result_key: {'type': tool['output_type']},
                    },
                    'required': [result_key],
                    'additionalProperties': False,
                },
            })
        tools.append({
            'name': _SCAFFOLD_TOOL['name'],
            'description': _SCAFFOLD_TOOL['description'],
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'scaffolds': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'minItems': 1,
                    },
                    'target': {'type': 'string'},
                    'lookup': {'type': 'string'},
                    'path': {'type': 'string'},
                    'subdir': {'type': 'string'},
                    'no_package': {'type': 'boolean'},
                    'dry_run': {'type': 'boolean'},
                },
                'required': ['scaffolds', 'target'],
                'additionalProperties': False,
            },
            'outputSchema': {
                'type': 'object',
                'properties': {
                    _SCAFFOLD_TOOL['result_key']: {'type': 'object'},
                },
                'required': [_SCAFFOLD_TOOL['result_key']],
                'additionalProperties': False,
            },
        })
        return tools

    def _call_tool(self, params):
        name = params.get('name') if isinstance(params, dict) else None
        tool = _READ_TOOLS_BY_NAME.get(name)
        if tool is not None:
            try:
                with redirect_stdout(self.stderr):
                    result = tool['collector'](project=self.project, config=self.config)
            except Exception as error:
                return self._tool_execution_error(f"{name} failed: {error}")
            return self._tool_result(tool['result_key'], result)

        if name == _SCAFFOLD_TOOL['name']:
            return self._call_scaffold_tool(params.get('arguments') if isinstance(params, dict) else None)

        return self._tool_execution_error(f"Unknown tool: {name or 'unknown'}")

    def _call_scaffold_tool(self, arguments):
        if not isinstance(arguments, dict):
            return self._tool_execution_error('tg_scaffold requires object arguments')

        scaffolds = arguments.get('scaffolds')
        target = arguments.get('target')
        if not isinstance(scaffolds, list) or not scaffolds or not all(isinstance(item, str) for item in scaffolds):
            return self._tool_execution_error('tg_scaffold requires scaffolds as a non-empty array of strings')
        if not isinstance(target, str) or not target:
            return self._tool_execution_error('tg_scaffold requires target as a non-empty string')
        for option in ('lookup', 'path', 'subdir'):
            if arguments.get(option) is not None and not isinstance(arguments.get(option), str):
                return self._tool_execution_error(f'tg_scaffold requires {option} as a string')
        for option in ('no_package', 'dry_run'):
            if option in arguments and not isinstance(arguments.get(option), bool):
                return self._tool_execution_error(f'tg_scaffold requires {option} as a boolean')

        try:
            with redirect_stdout(self.stderr):
                result = scaffold_project(
                    project=self.project,
                    scaffold_names=scaffolds,
                    target=target,
                    lookup=arguments.get('lookup'),
                    path=arguments.get('path'),
                    subdir=arguments.get('subdir'),
                    no_package=bool(arguments.get('no_package', False)),
                    dry_run=bool(arguments.get('dry_run', False)),
                )
        except Exception as error:
            return self._tool_execution_error(f"tg_scaffold failed: {error}")
        return self._tool_result(_SCAFFOLD_TOOL['result_key'], result)

    def _tool_result(self, result_key, result):
        structured = {result_key: result}
        return {
            'content': [{
                'type': 'text',
                'text': json.dumps(structured, indent=2, sort_keys=True),
            }],
            'structuredContent': structured,
        }

    def _tool_execution_error(self, message):
        return {
            'content': [{'type': 'text', 'text': message}],
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
