import json
import os
import re
import sys
import tempfile
from contextlib import redirect_stdout

try:
    import tomllib
except ImportError:  # pragma: no cover - exercised only on Python < 3.11
    tomllib = None

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

_AGENTS_SECTION_HEADING = '## TurboGears DevTools'
_AGENTS_SECTION = (
    f'{_AGENTS_SECTION_HEADING}\n\n'
    'This is a TurboGears project. Use Gearbox as the entrypoint for TurboGears '
    'development commands.\n\n'
    '- Prefer the configured TurboGears MCP tools when available to inspect routes, '
    'controllers, models, templates, and project scaffolds.\n'
    '- When MCP tools are unavailable, use the equivalent `gearbox tginfo ... '
    '--json` inspection commands instead of guessing from files alone.\n'
    '- Use `gearbox scaffold` to create new models, controllers, and templates '
    'from the project\'s scaffold templates, then edit generated code directly as needed.\n'
    '- Use `gearbox tgshell -c development.ini` to run Python code in the fully '
    'loaded application context. This is the preferred way to do runtime checks '
    'and WebTest requests.\n'
    '- Use `gearbox serve -c development.ini` to run the application locally when '
    'browser/manual testing is needed.\n'
    '- Use `gearbox setup-app -c development.ini` only when intentionally '
    'initializing application data/schema for a development or test environment.\n'
    '- Use migration commands such as `gearbox migrate` only when intentionally '
    'creating, inspecting, or applying database migrations.\n'
    '- Do not run `setup-app`, migrations, or other database-mutating commands as '
    'part of routine inspection.\n'
)

_TGMCP_ARGS = ['tgmcp', '--project', '.', '--config', 'development.ini']
_VSCODE_TGMCP_ARGS = ['tgmcp', '--project', '${workspaceFolder}', '--config', 'development.ini']
_CODEX_TGMCP_SECTION = '''[mcp_servers.turbogears]
command = "gearbox"
args = ["tgmcp", "--project", ".", "--config", "development.ini"]
enabled = true
'''

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
        return 'Serve TurboGears MCP over stdio or configure MCP clients'

    def get_parser(self, prog_name):
        parser = super(TgMcpCommand, self).get_parser(prog_name)
        parser.add_argument('--project', default='.', help='project root directory (default: current directory)')
        parser.add_argument('-c', '--config', dest='config_file', default='development.ini',
                            help='application config file to read (default: development.ini)')
        parser.add_argument('action', nargs='?', choices=['init'], help='run `init TARGET` to configure MCP clients')
        parser.add_argument('target', nargs='?', choices=['claude', 'codex', 'vscode', 'pi', 'all'],
                            help='MCP client configuration target for init')
        parser.add_argument('--no-agents-md', action='store_true', dest='no_agents_md',
                            help='skip updating AGENTS.md during init')
        return parser

    def take_action(self, opts):
        project_dir = os.path.realpath(os.path.abspath(os.path.expanduser(opts.project)))
        opts.project = project_dir

        if opts.action == 'init':
            if not opts.target:
                sys.stderr.write('gearbox tgmcp init requires a target: claude, codex, vscode, pi, or all\n')
                raise SystemExit(2)
            try:
                _init_tgmcp_project(project_dir, opts.target, no_agents_md=opts.no_agents_md)
            except _TgMcpInitError as error:
                sys.stderr.write(f'{error}\n')
                raise SystemExit(1)
            return

        config_file = os.path.expanduser(opts.config_file)
        if not os.path.isabs(config_file):
            config_file = os.path.join(project_dir, config_file)
        config_file = os.path.realpath(os.path.abspath(config_file))
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


def _init_tgmcp_project(project_dir, target, no_agents_md=False):
    targets = ['claude', 'codex', 'vscode', 'pi'] if target == 'all' else [target]
    destinations = []

    if 'claude' in targets:
        destinations.append((os.path.join(project_dir, '.mcp.json'), 'claude'))
    if 'codex' in targets:
        destinations.append((os.path.join(project_dir, '.codex', 'config.toml'), 'codex'))
    if 'vscode' in targets:
        destinations.append((os.path.join(project_dir, '.vscode', 'mcp.json'), 'vscode'))
    if not no_agents_md:
        destinations.append((os.path.join(project_dir, 'AGENTS.md'), 'pi'))

    _preflight_init_destinations(destinations)

    changes = []
    for path, destination in destinations:
        if destination == 'claude':
            changes.append((path, destination, _json_mcp_config_content(
                path,
                'mcpServers',
                _mcp_server_config(_TGMCP_ARGS),
                destination,
            )))
        elif destination == 'codex':
            changes.append((path, destination, _codex_config_content(path)))
        elif destination == 'vscode':
            changes.append((path, destination, _json_mcp_config_content(
                path,
                'servers',
                _mcp_server_config(_VSCODE_TGMCP_ARGS),
                destination,
            )))
        else:
            content = _agents_md_content(path)
            if content is not None:
                changes.append((path, destination, content))

    _write_init_changes(changes)

    sys.stdout.write(f'Configured TurboGears MCP init target {target} under {project_dir}\n')


class _TgMcpInitError(Exception):
    pass


def _write_init_changes(changes):
    staged = []
    snapshots = {}
    applied = []
    try:
        for path, destination, _content in changes:
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
            except OSError as error:
                raise _TgMcpInitError(_merge_failure(
                    path, destination, f'parent directory cannot be created: {error}'
                ))

        for path, destination, content in changes:
            temp_path = None
            try:
                fd, temp_path = tempfile.mkstemp(prefix='.tgmcp-init-', dir=os.path.dirname(path))
                with os.fdopen(fd, 'w', encoding='utf-8') as output:
                    output.write(content)
            except OSError as error:
                if temp_path is not None:
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
                raise _TgMcpInitError(_merge_failure(path, destination, f'temporary config cannot be written: {error}'))
            staged.append((path, destination, temp_path))

        for path, destination, _temp_path in staged:
            if os.path.exists(path):
                try:
                    with open(path, 'rb') as existing:
                        snapshots[path] = existing.read()
                except OSError as error:
                    raise _TgMcpInitError(_merge_failure(path, destination, f'existing config cannot be read: {error}'))
            else:
                snapshots[path] = None

        for path, destination, temp_path in staged:
            try:
                os.replace(temp_path, path)
            except OSError as error:
                raise _TgMcpInitError(_merge_failure(path, destination, f'destination cannot be written: {error}'))
            applied.append((path, destination))
    except _TgMcpInitError:
        for path, _destination in reversed(applied):
            if snapshots[path] is None:
                try:
                    os.remove(path)
                except OSError:
                    pass
            else:
                try:
                    with open(path, 'wb') as restored:
                        restored.write(snapshots[path])
                except OSError:
                    pass
        for _path, _destination, temp_path in staged:
            try:
                os.remove(temp_path)
            except OSError:
                pass
        raise


def _preflight_init_destinations(destinations):
    for path, destination in destinations:
        parent = os.path.dirname(path)
        ancestor = parent
        while ancestor and not os.path.exists(ancestor):
            next_ancestor = os.path.dirname(ancestor)
            if next_ancestor == ancestor:
                break
            ancestor = next_ancestor
        if ancestor and os.path.exists(ancestor) and not os.path.isdir(ancestor):
            raise _TgMcpInitError(_merge_failure(path, destination, f'parent path is not a directory: {ancestor}'))
        if os.path.isdir(path):
            raise _TgMcpInitError(_merge_failure(path, destination, 'destination is a directory'))


def _mcp_server_config(args):
    return {
        'type': 'stdio',
        'command': 'gearbox',
        'args': args,
    }


def _json_mcp_config_content(path, top_key, server_config, target):
    config = {}
    if os.path.exists(path):
        try:
            with open(path, encoding='utf-8') as existing:
                config = json.load(existing)
        except OSError as error:
            raise _TgMcpInitError(_merge_failure(path, target, f'existing config cannot be read: {error}'))
        except ValueError as error:
            raise _TgMcpInitError(_merge_failure(path, target, f'invalid JSON: {error}'))
        if not isinstance(config, dict):
            raise _TgMcpInitError(_merge_failure(path, target, 'top-level JSON value is not an object'))

    servers = config.setdefault(top_key, {})
    if not isinstance(servers, dict):
        raise _TgMcpInitError(_merge_failure(path, target, f'{top_key} is not an object'))
    servers['turbogears'] = server_config
    return json.dumps(config, indent=2, sort_keys=True) + '\n'


def _codex_config_content(path):
    if not os.path.exists(path):
        return _CODEX_TGMCP_SECTION
    if tomllib is None:
        raise _TgMcpInitError(_merge_failure(path, 'codex', 'TOML parsing is unavailable on this Python'))
    try:
        with open(path, 'rb') as existing:
            raw_text = existing.read()
    except OSError as error:
        raise _TgMcpInitError(_merge_failure(path, 'codex', f'existing config cannot be read: {error}'))
    try:
        text = raw_text.decode('utf-8')
        config = tomllib.loads(text)
    except Exception as error:
        raise _TgMcpInitError(_merge_failure(path, 'codex', f'invalid TOML: {error}'))
    mcp_servers = config.get('mcp_servers', {})
    if not isinstance(mcp_servers, dict):
        raise _TgMcpInitError(_merge_failure(path, 'codex', 'mcp_servers is not a table'))
    if 'turbogears' in mcp_servers and not isinstance(mcp_servers['turbogears'], dict):
        raise _TgMcpInitError(_merge_failure(path, 'codex', 'mcp_servers.turbogears is not a table'))

    pattern = r'(?ms)^[ \t]*\[mcp_servers\.turbogears\][ \t]*(?:#.*)?\n.*?(?=^[ \t]*\[|\Z)'
    if re.search(pattern, text):
        return re.sub(pattern, _CODEX_TGMCP_SECTION, text, count=1)
    if 'turbogears' in mcp_servers:
        raise _TgMcpInitError(_merge_failure(path, 'codex', 'existing turbogears entry is not a replaceable table'))
    return text.rstrip() + '\n\n' + _CODEX_TGMCP_SECTION


def _agents_md_content(path):
    if os.path.exists(path):
        try:
            with open(path, encoding='utf-8') as existing:
                content = existing.read()
        except OSError as error:
            raise _TgMcpInitError(_merge_failure(path, 'pi', f'existing AGENTS.md cannot be read: {error}'))
        if re.search(r'(?m)^## TurboGears DevTools[ \t]*$', content):
            return None
        if not content:
            return _AGENTS_SECTION
        separator = '' if content.endswith('\n\n') else '\n' if content.endswith('\n') else '\n\n'
        return content + separator + _AGENTS_SECTION
    return _AGENTS_SECTION


def _merge_failure(path, target, reason):
    return (
        f'Could not safely update {path} for tgmcp init {target}: {reason}.\n'
        'No changes were written for that file. Add or repair this snippet manually:\n'
        f'{_init_snippet(target)}'
    )


def _init_snippet(target):
    if target == 'claude':
        return json.dumps({'mcpServers': {'turbogears': _mcp_server_config(_TGMCP_ARGS)}}, indent=2, sort_keys=True)
    if target == 'vscode':
        return json.dumps({'servers': {'turbogears': _mcp_server_config(_VSCODE_TGMCP_ARGS)}}, indent=2, sort_keys=True)
    if target == 'codex':
        return _CODEX_TGMCP_SECTION.rstrip()
    return _AGENTS_SECTION.rstrip()


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
