"""Gearbox wrapper for Babel i18n commands."""
import argparse
import subprocess
import sys
from pathlib import Path

from gearbox.command import Command

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


class I18nCommand(Command):
    """Run pybabel with TurboGears quickstart defaults from pyproject.toml."""

    def get_description(self):
        return """Provides Babel i18n operations for TurboGears2 projects.

Configuration is read from pyproject.toml [tool.tg.devtools.i18n].

Extract messages from source files::

    $ gearbox i18n extract

Initialize a new message catalog::

    $ gearbox i18n init -l es

Update existing message catalogs::

    $ gearbox i18n update

Compile message catalogs to MO files::

    $ gearbox i18n compile
"""

    def get_parser(self, prog_name):
        parser = super(I18nCommand, self).get_parser(prog_name)
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        subparsers = parser.add_subparsers(dest='command')
        subparsers.add_parser('extract')

        init_parser = subparsers.add_parser('init')
        init_parser.add_argument('-l', '--locale', required=True)

        update_parser = subparsers.add_parser('update')
        update_parser.add_argument('-l', '--locale')

        compile_parser = subparsers.add_parser('compile')
        compile_parser.add_argument('-l', '--locale')

        return parser

    def take_action(self, opts):
        if not opts.command:
            self.get_parser('gearbox i18n').print_help()
            return

        config = self._load_i18n_config()
        if opts.command == 'extract':
            Path(config.get('pot_file', 'messages.pot')).parent.mkdir(
                parents=True, exist_ok=True,
            )
        self._run_babel_command(self._pybabel_command(opts, config))

    def _pybabel_command(self, opts, config):
        cmd = ['pybabel', opts.command]
        domain = config.get('domain', 'messages')
        directory = config.get('directory', 'locale')
        pot_file = config.get('pot_file', 'messages.pot')

        if opts.command == 'extract':
            extract = config.get('extract', {})
            if extract.get('mapping_file'):
                cmd.extend(['-F', extract['mapping_file']])
            cmd.extend(['-o', pot_file])
            keywords = extract.get('keywords', [])
            if isinstance(keywords, str):
                keywords = keywords.split()
            for keyword in keywords:
                cmd.extend(['-k', keyword])
            if extract.get('add_comments'):
                cmd.extend(['-c', extract['add_comments']])
            if extract.get('width'):
                cmd.extend(['-w', str(extract['width'])])
            cmd.append('.')
            return cmd

        if opts.command in ('init', 'update'):
            cmd.extend(['-i', pot_file, '-d', directory, '-D', domain])
        else:
            cmd.extend(['-d', directory, '-D', domain])

        if getattr(opts, 'locale', None):
            cmd.extend(['-l', opts.locale])
        if opts.command == 'update' and config.get('update', {}).get('previous'):
            cmd.append('--previous')
        if opts.command == 'compile' and config.get('compile', {}).get('statistics'):
            cmd.append('--statistics')
        return cmd

    def _load_i18n_config(self):
        pyproject = Path('pyproject.toml')
        if not pyproject.exists():
            return {}

        with pyproject.open('rb') as f:
            return tomllib.load(f).get('tool', {}).get('tg', {}).get('devtools', {}).get('i18n', {})

    def _run_babel_command(self, cmd):
        print('Running: %s' % ' '.join(cmd))
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except FileNotFoundError:
            print("Error: pybabel command not found. Please install Babel in your project.", file=sys.stderr)
            sys.exit(1)

        if result.stdout:
            print(result.stdout, end='')
        if result.stderr:
            print(result.stderr, end='', file=sys.stderr)
        if result.returncode != 0:
            sys.exit(result.returncode)
