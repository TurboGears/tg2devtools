import importlib
import inspect
import os
import sys
from contextlib import contextmanager, redirect_stdout


def collect_project_summary(project='.', config='development.ini'):
    """Collect factual read-only facts about a TurboGears project.

    :param str project: Project root directory.
    :param str config: PasteDeploy config file, relative to project when not absolute.
    """
    project_root = os.path.realpath(os.path.abspath(os.path.expanduser(project)))
    config_file = _resolve_config_file(project_root, config)

    with _project_import_context(project_root), redirect_stdout(sys.stderr):
        _load_app(project_root, config)
        tg_config = _tg_config()
        package_name = _config_get(tg_config, 'package_name')
        package = _import_optional(package_name) if package_name else None

        summary = {
            'project_root': project_root,
            'config_file': config_file,
            'package_name': package_name,
            'default_renderer': _config_get(tg_config, 'default_renderer'),
            'renderers': list(_config_get(tg_config, 'renderers', []) or []),
            'paths': _project_paths(project_root, package, tg_config),
            'root_controller': _root_controller_info(project_root, package_name, tg_config),
            'database': _database_info(tg_config),
            'auth': _auth_info(tg_config),
        }
    return summary


def format_project_summary(summary):
    """Format a project summary for humans without adding advice or counts.

    :param dict summary: Summary returned by :func:`collect_project_summary`.
    """
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
    if auth.get('enabled') is True:
        auth_text = 'enabled'
    elif auth.get('enabled') is False:
        auth_text = 'disabled'
    else:
        auth_text = 'unknown'
    lines.append(f'Auth: {auth_text}')

    return '\n'.join(lines) + '\n'


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


def _tg_config():
    import tg

    return tg.config


def _resolve_config_file(project_root, config):
    path = os.path.expanduser(config)
    if not os.path.isabs(path):
        path = os.path.join(project_root, path)
    return os.path.realpath(os.path.abspath(path))


def _project_paths(project_root, package, tg_config):
    paths = {}
    configured = _config_get(tg_config, 'paths', {}) or {}
    for key in ('controllers', 'templates'):
        value = _mapping_get(configured, key)
        if value:
            paths[key] = _relative_path_value(project_root, value)

    if package and getattr(package, '__file__', None):
        package_dir = os.path.dirname(os.path.abspath(package.__file__))
        for key, dirname in (('controllers', 'controllers'), ('model', 'model'), ('templates', 'templates')):
            if key not in paths:
                candidate = os.path.join(package_dir, dirname)
                if os.path.isdir(candidate):
                    paths[key] = _relative_path(project_root, candidate)
    return paths


def _root_controller_info(project_root, package_name, tg_config):
    root_controller = _config_get(tg_config, 'tg.root_controller')
    if root_controller is None:
        root_controller = _config_get(tg_config, 'root_controller')

    if root_controller is not None:
        if inspect.isclass(root_controller):
            controller_class = root_controller
        else:
            controller_class = root_controller.__class__
    else:
        root_module = _config_get(tg_config, 'application_root_module')
        if isinstance(root_module, str):
            root_module = _import_optional(root_module)
        if root_module is None and package_name:
            root_module = _import_optional(f'{package_name}.controllers.root')
        controller_class = getattr(root_module, 'RootController', None) if root_module else None

    if controller_class is None:
        return {}

    info = {'class': _class_name(controller_class)}
    info.update(_source_info(controller_class, project_root))
    return info


def _database_info(tg_config):
    use_sqlalchemy = _as_bool(_config_get(tg_config, 'use_sqlalchemy'))
    use_ming = _as_bool(_config_get(tg_config, 'use_ming'))
    if use_sqlalchemy is True:
        return {'enabled': True, 'orm': 'sqlalchemy'}
    if use_ming is True:
        return {'enabled': True, 'orm': 'ming'}
    if use_sqlalchemy is False and use_ming is False:
        return {'enabled': False, 'orm': None}
    if _config_get(tg_config, 'sqlalchemy.url'):
        return {'enabled': True, 'orm': 'sqlalchemy'}
    if _config_get(tg_config, 'ming.url'):
        return {'enabled': True, 'orm': 'ming'}
    if _config_get(tg_config, 'DBSession') is not None:
        return {'enabled': True, 'orm': 'unknown'}
    return {'enabled': None, 'orm': None}


def _auth_info(tg_config):
    enabled = _as_bool(_config_get(tg_config, 'sa_auth.enabled'))
    if enabled is None:
        auth_backend = _config_get(tg_config, 'auth_backend')
        if auth_backend is None and _config_contains(tg_config, 'auth_backend'):
            enabled = False
        elif auth_backend is not None:
            enabled = True
        elif _config_get(tg_config, 'sa_auth.authmetadata') is not None:
            enabled = True
    return {'enabled': enabled}


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


def _relative_path_value(project_root, value):
    if isinstance(value, (list, tuple, set)):
        return [_relative_path_value(project_root, item) for item in value]
    return _relative_path(project_root, os.fspath(value))


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


def _config_get(config, key, default=None):
    try:
        return config.get(key, default)
    except AttributeError:
        return getattr(config, key, default)


def _config_contains(config, key):
    try:
        return key in config
    except TypeError:
        return hasattr(config, key)


def _mapping_get(mapping, key, default=None):
    try:
        return mapping.get(key, default)
    except AttributeError:
        return default


def _import_optional(module_name):
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


def _class_name(cls):
    module = getattr(cls, '__module__', None)
    name = getattr(cls, '__qualname__', getattr(cls, '__name__', None))
    return f'{module}.{name}' if module else name


def _as_bool(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ('true', 'yes', 'on', '1'):
            return True
        if lowered in ('false', 'no', 'off', '0', 'none'):
            return False
    return bool(value)
