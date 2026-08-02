import importlib
import inspect
import json
import os
import sys
from contextlib import contextmanager, redirect_stdout

from gearbox.command import Command


class TgInfoCommand(Command):
    """Inspect TurboGears project facts."""

    def get_description(self):
        return 'Inspect TurboGears project facts'

    def get_parser(self, prog_name):
        parser = super(TgInfoCommand, self).get_parser(prog_name)
        subparsers = parser.add_subparsers(dest='tginfo_command')

        for name, help_text in (
            ('summary', 'Show factual project summary'),
            ('routes', 'Show static controller routes and actions'),
            ('models', 'Show exported project models'),
            ('templates', 'Show recognized project templates'),
            ('scaffolds', 'Show project scaffold templates'),
        ):
            sub = subparsers.add_parser(name, help=help_text)
            sub.add_argument('--project', default='.',
                             help='project root directory (default: current directory)')
            sub.add_argument('-c', '--config', dest='config_file', default='development.ini',
                             help='application config file to read (default: development.ini)')
            sub.add_argument('--json', action='store_true', dest='as_json',
                             help='emit JSON output')

        app_args = getattr(self, 'app_args', None)
        help_args = getattr(app_args, 'cmd', ())
        if getattr(app_args, 'help', False) and help_args:
            return subparsers.choices.get(help_args[0], parser)
        return parser

    def take_action(self, opts):
        subcommand_class = _SUBCOMMAND_CLASSES.get(opts.tginfo_command)
        if subcommand_class is None:
            raise SystemExit(
                'tginfo requires a subcommand: summary, routes, models, templates, or scaffolds'
            )

        subcommand = subcommand_class(opts.project, opts.config_file)
        result = subcommand.collect()
        if opts.as_json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(subcommand.format(result))


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_STANDARD_RENDERERS = {
    'kajiki': ('templating.kajiki.template_extension', '.xhtml'),
    'mako': ('templating.mako.template_extension', '.mak'),
    'jinja': (None, '.jinja'),
    'jinja2': (None, '.jinja'),
    'genshi': (None, '.html'),
}

_MISSING = object()


# ---------------------------------------------------------------------------
# Private subcommand concerns
# ---------------------------------------------------------------------------


class _SummarySubcommand:
    def __init__(self, project, config):
        self.project_root = os.path.realpath(os.path.abspath(os.path.expanduser(project)))
        self.config = config

    def collect(self):
        config_file = self._resolve_config_file(self.config)
        with _project_import_context(self.project_root), redirect_stdout(sys.stderr):
            _load_app(self.project_root, self.config)
            tg_config = _tg_config()
            package_name = tg_config.get('package_name')
            package = importlib.import_module(package_name) if package_name else None
            return {
                'project_root': self.project_root,
                'config_file': config_file,
                'package_name': package_name,
                'default_renderer': tg_config.get('default_renderer'),
                'renderers': list(tg_config.get('renderers', []) or []),
                'paths': self._project_paths(package, tg_config),
                'root_controller': self._root_controller_info(package_name, tg_config),
                'database': self._database_info(tg_config),
                'auth': {'enabled': tg_config.get('sa_auth.enabled')},
            }

    def format(self, summary):
        lines = [
            f"Project root: {summary.get('project_root') or 'unknown'}",
            f"Config file: {summary.get('config_file') or 'unknown'}",
            f"Package: {summary.get('package_name') or 'unknown'}",
            f"Default renderer: {summary.get('default_renderer') or 'unknown'}",
        ]
        renderers = summary.get('renderers') or []
        lines.append('Configured renderers: ' + (', '.join(renderers) if renderers else 'unknown'))
        paths = summary.get('paths') or {}
        if paths:
            lines.append('Paths:')
            for name in ('controllers', 'model', 'templates'):
                value = paths.get(name)
                if not value:
                    continue
                if isinstance(value, list):
                    value = ', '.join(value)
                lines.append(f"  {name.replace('_', ' ').title()}: {value}")
        root = summary.get('root_controller') or {}
        root_text = root.get('class') or 'unknown'
        if root.get('source'):
            root_text = f"{root_text} ({root['source']})"
        lines.append(f'Root controller: {root_text}')
        database = summary.get('database') or {}
        if database.get('enabled') is True:
            database_text = 'enabled'
            if database.get('orm'):
                database_text += f" ({database['orm']})"
        elif database.get('enabled') is False:
            database_text = 'disabled'
        else:
            database_text = 'unknown'
        lines.append(f'Database: {database_text}')
        auth = summary.get('auth') or {}
        auth_text = 'enabled' if auth.get('enabled') is True else 'disabled' if auth.get('enabled') is False else 'unknown'
        lines.append(f'Auth: {auth_text}')
        return '\n'.join(lines)

    def _resolve_config_file(self, config):
        path = os.path.expanduser(config)
        if not os.path.isabs(path):
            path = os.path.join(self.project_root, path)
        return os.path.realpath(os.path.abspath(path))

    def _project_paths(self, package, tg_config):
        paths = {}
        configured = tg_config.get('paths', {}) or {}
        for key in ('controllers', 'templates'):
            value = configured.get(key)
            if value:
                paths[key] = self._relative_path_value(value)

        if package and getattr(package, '__file__', None):
            package_dir = os.path.dirname(os.path.abspath(package.__file__))
            for key, dirname in (('controllers', 'controllers'), ('model', 'model'), ('templates', 'templates')):
                if key not in paths:
                    candidate = os.path.join(package_dir, dirname)
                    if os.path.isdir(candidate):
                        paths[key] = _relative_path(self.project_root, candidate)
        return paths

    def _relative_path_value(self, value):
        if isinstance(value, (list, tuple, set)):
            return [self._relative_path_value(item) for item in value]
        return _relative_path(self.project_root, os.fspath(value))

    def _root_controller_info(self, package_name, tg_config):
        controller_class = _root_controller_class(package_name, tg_config)
        if controller_class is None:
            return {}
        info = {'class': _class_name(controller_class)}
        info.update(_source_info(controller_class, self.project_root))
        return info

    def _database_info(self, tg_config):
        use_sqlalchemy = tg_config.get('use_sqlalchemy')
        use_ming = tg_config.get('use_ming')
        if use_sqlalchemy is True:
            return {'enabled': True, 'orm': 'sqlalchemy'}
        if use_ming is True:
            return {'enabled': True, 'orm': 'ming'}
        if use_sqlalchemy is False and use_ming is False:
            return {'enabled': False, 'orm': None}
        return {'enabled': None, 'orm': None}


class _RoutesSubcommand:
    def __init__(self, project, config):
        self.project_root = os.path.realpath(os.path.abspath(os.path.expanduser(project)))
        self.config = config

    def collect(self):
        with _project_import_context(self.project_root), redirect_stdout(sys.stderr):
            _load_app(self.project_root, self.config)
            tg_config = _tg_config()
            package_name = tg_config.get('package_name')
            root_controller = _root_controller_object(package_name, tg_config)
            if root_controller is None:
                return []
            return _RouteCollector(self.project_root, tg_config).collect(root_controller)

    def format(self, routes):
        if not routes:
            return 'No static routes found.'
        lines = []
        for row in routes:
            target = row.get('controller') or 'unknown controller'
            action = row.get('action')
            if action:
                target = f'{target}.{action}'
            lines.append(f"{row.get('path') or 'unknown'} [{row.get('kind') or 'route'}] {target}")
        return '\n'.join(lines)


class _ModelsSubcommand:
    def __init__(self, project, _config):
        self.project_root = os.path.realpath(os.path.abspath(os.path.expanduser(project)))

    def collect(self):
        package_name = self._project_package_for_models()
        if not package_name:
            return []
        with _project_import_context(self.project_root), redirect_stdout(sys.stderr):
            model_package = self._import_project_model_package(f'{package_name}.model')
            if model_package is None:
                return []
            return self._model_rows(model_package)

    def format(self, models):
        if not models:
            return 'No exported models found.'
        lines = []
        for row in models:
            target = row.get('class') or 'unknown class'
            if row.get('source'):
                target = f"{target} ({row['source']})"
            lines.append(f"{row.get('name') or 'unknown'} [{row.get('orm') or 'unknown'}] {target}")
        return '\n'.join(lines)

    def _project_package_for_models(self):
        package_name = self._pyproject_app_package()
        if package_name:
            return package_name
        return self._unique_top_level_model_package()

    def _pyproject_app_package(self):
        pyproject = os.path.join(self.project_root, 'pyproject.toml')
        if not os.path.isfile(pyproject):
            return None
        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib  # type: ignore
        with open(pyproject, 'rb') as handle:
            data = tomllib.load(handle)
        app_factories = (
            data.get('project', {})
            .get('entry-points', {})
            .get('paste.app_factory', {})
        )
        if not isinstance(app_factories, dict):
            return None
        for value in ([app_factories.get('main')] + list(app_factories.values())):
            if not isinstance(value, str):
                continue
            module_name = value.split(':', 1)[0].split('[', 1)[0].strip()
            package_name = self._app_package_containing_model(module_name)
            if package_name:
                return package_name
        return None

    def _app_package_containing_model(self, module_name):
        parts = module_name.split('.')
        if not parts or any(not part.isidentifier() for part in parts):
            return None
        for end in range(len(parts), 0, -1):
            model_init = os.path.join(self.project_root, *parts[:end], 'model', '__init__.py')
            if os.path.isfile(model_init):
                return '.'.join(parts[:end])
        return None

    def _unique_top_level_model_package(self):
        candidates = []
        try:
            entries = os.scandir(self.project_root)
        except OSError:
            return None
        with entries:
            for entry in entries:
                if not entry.is_dir() or not entry.name.isidentifier():
                    continue
                if (
                    os.path.isfile(os.path.join(entry.path, '__init__.py'))
                    and os.path.isfile(os.path.join(entry.path, 'model', '__init__.py'))
                ):
                    candidates.append(entry.name)
        return candidates[0] if len(candidates) == 1 else None

    def _import_project_model_package(self, module_name):
        try:
            return importlib.import_module(module_name)
        except ImportError as error:
            if getattr(error, 'name', None) == module_name:
                return None
            raise

    def _model_rows(self, model_package):
        model_package_name = model_package.__name__
        exports = getattr(model_package, '__all__', _MISSING)
        if exports is _MISSING:
            candidates = ((n, v) for n, v in vars(model_package).items() if not n.startswith('_'))
        else:
            export_names = (exports,) if isinstance(exports, str) else tuple(exports) if hasattr(exports, '__iter__') else ()
            candidates = (
                (n, getattr(model_package, n, _MISSING))
                for n in export_names if isinstance(n, str)
            )
        rows = []
        for name, value in candidates:
            if value is _MISSING or not inspect.isclass(value):
                continue
            module = getattr(value, '__module__', '')
            if module != model_package_name and not module.startswith(f'{model_package_name}.'):
                continue
            source = _source_info(value, self.project_root).get('source')
            rows.append({
                'name': name,
                'class': _class_name(value),
                'module': module,
                'source': source,
                'orm': self._model_orm(value),
                'docstring': inspect.getdoc(value),
            })
        rows.sort(key=lambda row: (row['name'], row['class']))
        return rows

    def _model_orm(self, cls):
        if self._static_attr(cls, '__mongometa__') is not _MISSING:
            return 'ming'
        if self._static_attr(cls, '__mapper__') is not _MISSING or self._static_attr(cls, '__table__') is not _MISSING:
            return 'sqlalchemy'
        if self._static_attr(cls, '__tablename__') is not _MISSING and self._static_attr(cls, 'metadata') is not _MISSING:
            return 'sqlalchemy'
        return 'unknown'

    def _static_attr(self, value, name):
        try:
            return inspect.getattr_static(value, name)
        except AttributeError:
            return _MISSING


class _TemplatesSubcommand:
    def __init__(self, project, config):
        self.project_root = os.path.realpath(os.path.abspath(os.path.expanduser(project)))
        self.config = config

    def collect(self):
        with _project_import_context(self.project_root), redirect_stdout(sys.stderr):
            _load_app(self.project_root, self.config)
            tg_config = _tg_config()
            package_name = tg_config.get('package_name')
            root_controller = _root_controller_object(package_name, tg_config)
            routes = _RouteCollector(self.project_root, tg_config).collect(root_controller) if root_controller is not None else []
            return self._template_rows(tg_config, routes)

    def format(self, templates):
        if not templates:
            return 'No recognized templates found.'
        lines = []
        for row in templates:
            name = row.get('name') or 'unknown dotted name'
            exposed_by = row.get('exposed_by') or []
            backlinks = ', '.join(exposed_by) if exposed_by else 'not exposed by static routes'
            lines.append(
                f"{row.get('file') or 'unknown file'} [{row.get('renderer') or 'unknown'}] "
                f"{name} exposed by {backlinks}"
            )
        return '\n'.join(lines)

    def _template_rows(self, tg_config, routes):
        extensions = self._recognized_template_extensions(tg_config)
        exposed_by_file = {}
        exposed_by_name_extension = {}
        for route in routes:
            for expose in route.get('exposes') or []:
                path = expose.get('template_file')
                if path:
                    exposed_by_file.setdefault(path, set()).add(route['path'])
                    continue
                name = expose.get('template')
                if not name:
                    continue
                for extension in self._template_fallback_extensions(tg_config, expose.get('renderer')):
                    exposed_by_name_extension.setdefault((name, extension), set()).add(route['path'])

        rows = []
        seen = set()
        for template_root in self._template_paths(tg_config):
            for dirname, _, filenames in os.walk(template_root):
                for filename in filenames:
                    extension = os.path.splitext(filename)[1]
                    renderer = extensions.get(extension)
                    if renderer is None:
                        continue
                    path = os.path.join(dirname, filename)
                    relative_file = _relative_path(self.project_root, path)
                    if relative_file in seen:
                        continue
                    seen.add(relative_file)
                    name = self._template_dotted_name(path)
                    exposed_by = set(exposed_by_file.get(relative_file, ()))
                    if name:
                        exposed_by.update(exposed_by_name_extension.get((name, extension), ()))
                    rows.append({
                        'name': name,
                        'file': relative_file,
                        'renderer': renderer,
                        'exposed_by': sorted(exposed_by),
                    })
        rows.sort(key=lambda row: row['file'])
        return rows

    def _template_paths(self, tg_config):
        configured = (tg_config.get('paths', {}) or {}).get('templates')
        if configured:
            values = configured if isinstance(configured, (list, tuple, set)) else (configured,)
            return [self._absolute_path(value) for value in values]
        package_name = tg_config.get('package_name')
        if not package_name:
            return []
        package = importlib.import_module(package_name)
        if not package or not getattr(package, '__file__', None):
            return []
        return [os.path.join(os.path.dirname(os.path.abspath(package.__file__)), 'templates')]

    def _recognized_template_extensions(self, tg_config):
        extensions = {}
        configured_renderers = tg_config.get('renderers') or []
        standard_renderers = [r for r in configured_renderers if r in _STANDARD_RENDERERS]
        if not standard_renderers:
            standard_renderers = list(_STANDARD_RENDERERS)
        for renderer in standard_renderers:
            extensions.setdefault(_template_extension(tg_config, renderer), renderer)
        return extensions

    def _template_fallback_extensions(self, tg_config, renderer):
        renderer = renderer or tg_config.get('default_renderer')
        if not renderer:
            return tuple(self._recognized_template_extensions(tg_config))
        renderer = str(renderer).lower()
        if renderer in _STANDARD_RENDERERS:
            return (_template_extension(tg_config, renderer),)
        return ()

    def _template_dotted_name(self, path):
        relative = _relative_path(self.project_root, os.path.splitext(path)[0])
        if os.path.isabs(relative):
            return None
        parts = relative.split('/')
        if not parts or any(not part.isidentifier() for part in parts):
            return None
        return '.'.join(parts)

    def _absolute_path(self, path):
        path = os.fspath(path)
        if not os.path.isabs(path):
            path = os.path.join(self.project_root, path)
        return os.path.realpath(os.path.abspath(path))


class _ScaffoldsSubcommand:
    def __init__(self, project, _config):
        self.project_root = os.path.realpath(os.path.abspath(os.path.expanduser(project)))

    def collect(self):
        rows = []
        for directory, _, filenames in os.walk(self.project_root):
            for filename in filenames:
                if not filename.endswith('.template'):
                    continue
                template_name = filename[:-len('.template')]
                name, output_extension = os.path.splitext(template_name)
                path = os.path.join(directory, filename)
                relative_dir = _relative_path(self.project_root, directory)
                default_output_pattern = (
                    f'{relative_dir}/{{target}}{output_extension}' if relative_dir != '.'
                    else f'{{target}}{output_extension}'
                )
                rows.append({
                    'name': name,
                    'template_path': _relative_path(self.project_root, path),
                    'relative_dir': relative_dir,
                    'output_extension': output_extension,
                    'default_output_pattern': default_output_pattern,
                })
        return sorted(rows, key=lambda row: row['template_path'])

    def format(self, scaffolds):
        if not scaffolds:
            return 'No scaffold templates found.'
        lines = []
        for row in scaffolds:
            path = row.get('template_path') or 'unknown template'
            pattern = row.get('default_output_pattern') or 'unknown output'
            lines.append(
                f"{row.get('name') or 'unknown'} [{row.get('output_extension') or 'no extension'}] "
                f"{path} -> {pattern}"
            )
        return '\n'.join(lines)


_SUBCOMMAND_CLASSES = {
    'summary': _SummarySubcommand,
    'routes': _RoutesSubcommand,
    'models': _ModelsSubcommand,
    'templates': _TemplatesSubcommand,
    'scaffolds': _ScaffoldsSubcommand,
}


# ---------------------------------------------------------------------------
# Project context and app loading
# ---------------------------------------------------------------------------


@contextmanager
def _project_import_context(project_root):
    old_cwd = os.getcwd()
    old_path = list(sys.path)
    os.chdir(project_root)
    if sys.path[:1] != [project_root]:
        sys.path.insert(0, project_root)
    try:
        yield
    finally:
        os.chdir(old_cwd)
        sys.path[:] = old_path


def _load_app(project_root, config):
    from paste.deploy import loadapp
    loadapp(f'config:{os.path.expanduser(config)}', relative_to=project_root)


# ---------------------------------------------------------------------------
# Summary helpers
# ---------------------------------------------------------------------------


def _tg_config():
    import tg
    return tg.config


def _root_controller_class(package_name, tg_config):
    root_controller = tg_config.get('tg.root_controller')
    if root_controller is not None:
        return root_controller if inspect.isclass(root_controller) else root_controller.__class__

    root_module = _root_controller_module(package_name, tg_config)
    return root_module.RootController if root_module is not None else None


def _root_controller_object(package_name, tg_config):
    root_controller = tg_config.get('tg.root_controller')
    if root_controller is not None:
        return root_controller

    root_module = _root_controller_module(package_name, tg_config)
    if root_module is None:
        return None
    root_controller = root_module.RootController
    return root_controller() if inspect.isclass(root_controller) else root_controller


def _root_controller_module(package_name, tg_config):
    root_module = tg_config.get('application_root_module')
    if isinstance(root_module, str):
        return importlib.import_module(root_module)
    if root_module is not None:
        return root_module
    if package_name:
        return importlib.import_module(f'{package_name}.controllers.root')
    return None


# ---------------------------------------------------------------------------
# Route collection
# ---------------------------------------------------------------------------


class _RouteCollector:
    _DISPATCH_PRIVATE_NAMES = {'_lookup', '_default'}
    _IGNORED_PRIVATE_NAMES = {'_before', '_after', '_visit'}

    def __init__(self, project_root, tg_config):
        self.project_root = project_root
        self.template_resolver = _TemplateResolver(project_root, tg_config)
        self.rows = []

    def collect(self, root_controller):
        self._walk(root_controller, [], set())
        self.rows.sort(key=lambda row: (row['path'], row['kind'], row.get('action') or ''))
        return self.rows

    def _walk(self, controller, segments, active):
        if controller is None:
            return

        identity = id(controller)
        if identity in active:
            return
        active.add(identity)
        try:
            if self._is_wsgi_controller(controller):
                self.rows.append(self._row(controller, self._dispatch_path(segments), 'wsgi_app', '_default'))
                return

            for name, value in self._dispatch_members(controller):
                if name in self._IGNORED_PRIVATE_NAMES:
                    continue

                if name == '_lookup':
                    if callable(value):
                        self.rows.append(self._row(controller, self._dispatch_path(segments), 'dynamic_lookup', name, value))
                    continue

                if name == '_default':
                    if callable(value) and self._is_exposed(value):
                        self.rows.append(self._row(controller, self._dispatch_path(segments), 'dynamic_default', name, value))
                    continue

                if name.startswith('_'):
                    continue

                if self._is_wsgi_controller(value):
                    self.rows.append(self._row(value, self._dispatch_path(segments + [name]), 'wsgi_app', '_default'))
                    continue

                if self._is_controller(value):
                    self._walk(value, segments + [name], active)
                    continue

                if callable(value) and self._is_exposed(value):
                    kind = 'index' if name == 'index' else 'action'
                    self.rows.append(self._row(controller, self._action_path(segments, name), kind, name, value))
        finally:
            active.remove(identity)

    def _row(self, controller, path, kind, action_name, action=None):
        controller_class = controller if inspect.isclass(controller) else controller.__class__
        controller_source = _source_info(controller_class, self.project_root).get('source')
        controller_allow_only = self._plain_static_member(controller, 'allow_only')
        if controller_allow_only is _MISSING:
            controller_allow_only = None
        action_source = _source_info(action, self.project_root).get('source') if action is not None else None
        decoration = self._decoration(action)
        return {
            'path': path,
            'kind': kind,
            'controller': _class_name(controller_class),
            'controller_source': controller_source,
            'controller_doc': inspect.getdoc(controller_class),
            'controller_allow_only': _safe_text(controller_allow_only) if controller_allow_only is not None else None,
            'action': action_name,
            'action_source': action_source,
            'action_doc': inspect.getdoc(action) if action is not None else None,
            'params': self._params(action),
            'action_requires': self._requirements(decoration),
            'validations': self._validations(decoration),
            'exposes': self._exposes(decoration),
        }

    def _dispatch_members(self, controller):
        seen = set()
        members = []
        try:
            for name, value in vars(controller).items():
                seen.add(name)
                members.append((name, value))
        except TypeError:
            pass

        for cls in controller.__class__.mro():
            for name, value in vars(cls).items():
                if name in seen:
                    continue
                seen.add(name)
                if inspect.isfunction(value):
                    members.append((name, value.__get__(controller, cls)))
                elif isinstance(value, (staticmethod, classmethod)):
                    members.append((name, value.__get__(controller, cls)))
                elif not hasattr(value, '__get__'):
                    members.append((name, value))
        return members

    def _is_controller(self, value):
        if value is None or isinstance(value, (str, bytes, bytearray, int, float, bool, tuple, list, dict, set)):
            return False
        if self._is_wsgi_controller(value):
            return True
        for name, member in self._dispatch_members(value):
            if name in self._DISPATCH_PRIVATE_NAMES and callable(member):
                return True
            if not name.startswith('_') and callable(member) and self._is_exposed(member):
                return True
        return False

    def _is_wsgi_controller(self, value):
        return (
            value is not None
            and value.__class__.__name__ == 'WSGIAppController'
            and self._plain_static_member(value, 'app') is not _MISSING
        )

    def _plain_static_member(self, value, name):
        if value is None:
            return _MISSING
        try:
            if name in vars(value):
                return vars(value)[name]
        except TypeError:
            pass
        for cls in value.__class__.mro():
            if name not in vars(cls):
                continue
            member = inspect.getattr_static(value, name, _MISSING)
            if member is _MISSING or inspect.getattr_static(member, '__get__', _MISSING) is not _MISSING:
                return _MISSING
            return member
        return _MISSING

    def _is_exposed(self, value):
        decoration = self._decoration(value)
        if decoration is None:
            return False
        methods = ('exposed', '_expositions', 'engines', 'custom_engines')
        return any(self._plain_static_member(decoration, m) is not _MISSING and self._plain_static_member(decoration, m)
                   for m in methods)

    def _decoration(self, value):
        if value is None:
            return None
        value = getattr(value, '__func__', value)
        decoration = self._plain_static_member(value, 'decoration')
        if decoration is _MISSING:
            return None
        return decoration

    def _action_path(self, segments, name):
        if name == 'index':
            return '/' if not segments else '/' + '/'.join(segments) + '/'
        return '/' + '/'.join(segments + [name])

    def _dispatch_path(self, segments):
        return '/*' if not segments else '/' + '/'.join(segments) + '/*'

    def _params(self, action):
        if action is None:
            return []
        signature = inspect.signature(action)
        params = []
        for param in signature.parameters.values():
            if param.name == 'self':
                continue
            item = {'name': param.name, 'kind': param.kind.name.lower()}
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                item['required'] = False
            elif param.default is inspect.Parameter.empty:
                item['required'] = True
            else:
                item['required'] = False
                item['default'] = _safe_text(param.default)
            params.append(item)
        return params

    def _requirements(self, decoration):
        if decoration is None:
            return []
        values = self._plain_static_member(decoration, 'requirements')
        return [
            _safe_text(self._plain_static_member(r, 'predicate') if self._plain_static_member(r, 'predicate') is not _MISSING else r)
            for r in ((values if values is not _MISSING else []) or [])
        ]

    def _validations(self, decoration):
        if decoration is None:
            return []
        validations = []
        values = self._plain_static_member(decoration, 'validations')
        for validation in ((values if values is not _MISSING else []) or []):
            item = {}
            for source_name, output_name in (
                ('validators', 'validators'), ('validator', 'validator'),
                ('error_handler', 'error_handler'), ('chain_validation', 'chain_validation'),
            ):
                value = self._plain_static_member(validation, source_name)
                if value is not _MISSING:
                    item[output_name] = _validation_text(value)
            validations.append(item or {'value': _safe_text(validation)})
        return validations

    def _exposes(self, decoration):
        if decoration is None:
            return []
        exposes = []
        engines = self._plain_static_member(decoration, 'engines')
        for content_type, values in ((engines if engines is not _MISSING else {}) or {}).items():
            engine, template = (tuple(values) + (None, None))[:2]
            exposes.append(self._expose(engine, content_type, template))
        custom_engines = self._plain_static_member(decoration, 'custom_engines')
        for custom_format, values in ((custom_engines if custom_engines is not _MISSING else {}) or {}).items():
            content_type, engine, template = (tuple(values) + (None, None, None))[:3]
            expose = self._expose(engine, content_type, template)
            expose['custom_format'] = custom_format
            exposes.append(expose)
        return exposes

    def _expose(self, engine, content_type, template):
        template = template or None
        resolution = self.template_resolver.resolve(engine, template)
        return {
            'renderer': engine,
            'content_type': content_type,
            'template': template,
            'template_file': resolution['file'],
            'template_resolution': resolution,
        }


class _TemplateResolver:
    def __init__(self, project_root, tg_config):
        self.project_root = project_root
        self.tg_config = tg_config
        self.finder = tg_config.get('tg.app_globals').dotted_filename_finder

    def resolve(self, engine, template):
        if not template:
            return {'status': 'not_applicable', 'file': None, 'reason': 'exposure has no template'}
        renderer = (engine or '').lower()
        if renderer not in _STANDARD_RENDERERS:
            return self._unresolved(f"renderer {engine!r} does not expose a standard template filename resolver")
        path = self.finder.get_dotted_filename(template, _template_extension(self.tg_config, renderer))
        if os.path.isfile(path):
            return {'status': 'resolved', 'file': _relative_path(self.project_root, path), 'reason': None}
        return self._unresolved('TurboGears dotted filename finder returned a missing file')

    def _unresolved(self, reason):
        return {'status': 'unresolved', 'file': None, 'reason': reason}


# ---------------------------------------------------------------------------
# Template resolution
# ---------------------------------------------------------------------------


def _template_extension(tg_config, renderer):
    config_key, default = _STANDARD_RENDERERS[renderer]
    extension = tg_config.get(config_key, default) if config_key else default
    if not extension:
        extension = default
    return extension if str(extension).startswith('.') else f'.{extension}'


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def _source_info(value, project_root):
    try:
        filename = inspect.getsourcefile(value) or inspect.getfile(value)
    except (OSError, TypeError):
        return {}
    info = {'file': _relative_path(project_root, filename)}
    try:
        _, line = inspect.getsourcelines(value)
    except (OSError, TypeError):
        line = None
    if line is not None:
        info['line'] = line
        info['source'] = f"{info['file']}:{line}"
    else:
        info['source'] = info['file']
    return info


def _relative_path(project_root, path):
    if not os.path.isabs(path):
        path = os.path.join(project_root, path)
    try:
        relative = os.path.relpath(os.path.realpath(os.path.abspath(path)), project_root)
    except ValueError:
        return os.path.realpath(os.path.abspath(path))
    if relative == os.curdir:
        return '.'
    if relative.startswith(os.pardir + os.path.sep) or relative == os.pardir:
        return os.path.realpath(os.path.abspath(path))
    return relative.replace(os.path.sep, '/')


def _class_name(cls):
    module = getattr(cls, '__module__', None)
    name = getattr(cls, '__qualname__', getattr(cls, '__name__', None))
    return f'{module}.{name}' if module else name


def _validation_text(value):
    if callable(value):
        module = getattr(value, '__module__', None)
        qualname = getattr(value, '__qualname__', None)
        if module and qualname:
            return f'{module}.{qualname}'
        return f'<{type(value).__module__}.{type(value).__name__}>'
    return _safe_text(value)


def _safe_text(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return repr(value)
    except Exception:
        return f'<{value.__class__.__module__}.{value.__class__.__name__}>'
