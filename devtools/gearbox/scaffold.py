import io
import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout


_TG_NEXT_STEPS = {
    'controller': 'Mount the controller in RootController if a URL is desired.',
    'model': (
        'Import the model from the model package if it should be exported; '
        'create or review migrations manually if needed.'
    ),
    'template': 'Expose the template from a controller action if it should be reachable.',
}


def scaffold_project(project='.', scaffold_names=None, target=None, lookup=None, path=None,
                     subdir=None, no_package=False, dry_run=False):
    """Run Gearbox scaffold for a project and add minimal TurboGears hints.

    :param str project: Project root directory.
    :param list scaffold_names: Gearbox scaffold template names to run.
    :param str target: Entity for which scaffold files are created.
    :param str lookup: Optional Gearbox template lookup path.
    :param str path: Optional output path.
    :param str subdir: Optional output subdirectory.
    :param bool no_package: Whether Gearbox should avoid package creation when supported.
    :param bool dry_run: Whether Gearbox should plan without writing when supported.
    """
    if not scaffold_names:
        raise ValueError('tg_scaffold requires at least one scaffold name')
    if not target:
        raise ValueError('tg_scaffold requires a target')

    project_root = os.path.realpath(os.path.abspath(os.path.expanduser(project)))
    if isinstance(scaffold_names, str):
        names = [scaffold_names]
    else:
        names = list(scaffold_names)
    if not all(isinstance(name, str) and name for name in names):
        raise ValueError('tg_scaffold requires scaffold names as non-empty strings')

    previous_cwd = os.getcwd()
    previous_sys_path = list(sys.path)
    try:
        os.chdir(project_root)
        sys.path.insert(0, project_root)
        gearbox_result = _run_gearbox_scaffold(
            names, target, lookup=lookup, path=path, subdir=subdir,
            no_package=no_package, dry_run=dry_run,
        )
    finally:
        sys.path[:] = previous_sys_path
        os.chdir(previous_cwd)

    return {
        'gearbox': gearbox_result,
        'next_steps': _next_steps_for_scaffolds(names),
    }


def _run_gearbox_scaffold(scaffold_names, target, lookup=None, path=None, subdir=None,
                          no_package=False, dry_run=False):
    from gearbox.commands.scaffold import ScaffoldCommand

    command = ScaffoldCommand(None, {})
    parser = command.get_parser('gearbox scaffold')
    argv = []

    for option, value in (('--lookup', lookup), ('--path', path), ('--subdir', subdir)):
        if value is not None:
            _require_option(parser, option)
            argv.extend([option, value])

    if no_package:
        _append_boolean_option(parser, argv, '--no-package')

    if dry_run:
        _append_boolean_option(parser, argv, '--dry-run')

    if _option_action(parser, '--json') is not None:
        _append_boolean_option(parser, argv, '--json')

    argv.extend(scaffold_names)
    argv.append(target)
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            opts = parser.parse_args(argv)
            action_result = command.take_action(opts)
    except SystemExit as error:
        message = stderr.getvalue().strip() or stdout.getvalue().strip()
        if not message:
            message = f'Gearbox scaffold exited with status {error.code}'
        raise ValueError(message) from error

    output = stdout.getvalue()
    if action_result is not None:
        return action_result

    try:
        return json.loads(output)
    except ValueError:
        return {
            'target': target,
            'scaffolds': list(scaffold_names),
            'stdout': output,
        }


def _require_option(parser, option):
    action = _option_action(parser, option)
    if action is None:
        raise ValueError(f'Gearbox scaffold does not support {option}')
    return action


def _append_boolean_option(parser, argv, option):
    action = _require_option(parser, option)
    argv.append(option)
    if action.nargs != 0:
        argv.append('true')


def _option_action(parser, option):
    for action in parser._actions:
        if option in action.option_strings:
            return action
    return None


def _next_steps_for_scaffolds(scaffold_names):
    next_steps = []
    seen = set()
    for name in scaffold_names:
        key = os.path.splitext(os.path.basename(name))[0]
        if key in _TG_NEXT_STEPS and key not in seen:
            next_steps.append({'scaffold': key, 'hint': _TG_NEXT_STEPS[key]})
            seen.add(key)
    return next_steps
