"""Tests for the i18n command."""
import fnmatch
import importlib
import os
import sys
import tempfile
import types
import unittest
from io import StringIO
from unittest.mock import MagicMock, patch

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


class MockCommand:
    def get_parser(self, prog_name):
        import argparse
        return argparse.ArgumentParser(prog=prog_name)


_MISSING = object()


class TestI18nCommand(unittest.TestCase):
    def setUp(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
            self.addCleanup(sys.path.remove, repo_root)

        self._original_i18n_module = sys.modules.get('devtools.gearbox.i18n', _MISSING)
        sys.modules.pop('devtools.gearbox.i18n', None)
        self.addCleanup(self._restore_i18n_module)

        gearbox_module = types.ModuleType('gearbox')
        command_module = types.ModuleType('gearbox.command')
        command_module.Command = MockCommand
        gearbox_module.command = command_module

        with patch.dict(sys.modules, {'gearbox': gearbox_module, 'gearbox.command': command_module}):
            self.I18nCommand = importlib.import_module('devtools.gearbox.i18n').I18nCommand

    def _restore_i18n_module(self):
        if self._original_i18n_module is _MISSING:
            sys.modules.pop('devtools.gearbox.i18n', None)
        else:
            sys.modules['devtools.gearbox.i18n'] = self._original_i18n_module

        gearbox_package = sys.modules.get('devtools.gearbox')
        if gearbox_package is not None:
            if self._original_i18n_module is _MISSING:
                try:
                    delattr(gearbox_package, 'i18n')
                except AttributeError:
                    pass
            else:
                gearbox_package.i18n = self._original_i18n_module

    def test_parser_subcommands_and_required_init_locale(self):
        parser = self.I18nCommand().get_parser('gearbox i18n')

        self.assertEqual(parser.parse_args(['extract']).command, 'extract')
        self.assertEqual(parser.parse_args(['update']).command, 'update')
        self.assertEqual(parser.parse_args(['compile']).command, 'compile')

        init = parser.parse_args(['init', '-l', 'es'])
        self.assertEqual(init.command, 'init')
        self.assertEqual(init.locale, 'es')
        self.assertFalse(hasattr(init, 'babel_path'))
        self.assertFalse(hasattr(init, 'config'))

        with patch('sys.stderr', new_callable=StringIO):
            with self.assertRaises(SystemExit):
                parser.parse_args(['init'])

    def test_commands_are_built_from_pyproject_i18n_defaults(self):
        commands = []

        def record_run(cmd, **kwargs):
            commands.append(cmd)
            return MagicMock(returncode=0, stdout='', stderr='')

        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            try:
                with open('pyproject.toml', 'w') as f:
                    f.write('''[tool.tg.devtools.i18n]
domain = "myapp"
directory = "myapp/i18n"
pot_file = "myapp/i18n/myapp.pot"

[tool.tg.devtools.i18n.extract]
mapping_file = "pyproject.toml"
keywords = ["l_", "N_"]
add_comments = "TRANSLATORS:"
width = 80

[tool.tg.devtools.i18n.update]
previous = true

[tool.tg.devtools.i18n.compile]
statistics = true
''')
                with open('development.ini', 'w') as f:
                    f.write('[app:main]\ni18n.domain = wrong\ni18n.locale_dir = wrong\n')

                cmd = self.I18nCommand()
                parser = cmd.get_parser('gearbox i18n')
                with patch('subprocess.run', side_effect=record_run):
                    with patch('sys.stdout', new_callable=StringIO):
                        for args in [
                            ['extract'],
                            ['init', '-l', 'es'],
                            ['update', '-l', 'es'],
                            ['compile', '-l', 'es'],
                        ]:
                            cmd.take_action(parser.parse_args(args))
            finally:
                os.chdir(old_cwd)

        self.assertEqual(commands, [
            [
                'pybabel', 'extract', '-F', 'pyproject.toml',
                '-o', 'myapp/i18n/myapp.pot', '-k', 'l_', '-k', 'N_',
                '-c', 'TRANSLATORS:', '-w', '80', '.',
            ],
            [
                'pybabel', 'init', '-i', 'myapp/i18n/myapp.pot',
                '-d', 'myapp/i18n', '-D', 'myapp', '-l', 'es',
            ],
            [
                'pybabel', 'update', '-i', 'myapp/i18n/myapp.pot',
                '-d', 'myapp/i18n', '-D', 'myapp', '-l', 'es', '--previous',
            ],
            [
                'pybabel', 'compile', '-d', 'myapp/i18n', '-D', 'myapp',
                '-l', 'es', '--statistics',
            ],
        ])

    def test_no_command_shows_help_without_running_pybabel(self):
        cmd = self.I18nCommand()
        opts = MagicMock(command=None)

        with patch('subprocess.run') as run:
            with patch('sys.stdout', new_callable=StringIO) as stdout:
                cmd.take_action(opts)

        self.assertIn('usage:', stdout.getvalue().lower())
        run.assert_not_called()

    def test_quickstart_template_has_i18n_defaults_and_valid_babel_mappings(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        template_dir = os.path.join(repo_root, 'devtools', 'gearbox', 'quickstart', 'template')

        with open(os.path.join(template_dir, 'pyproject.toml_tmpl')) as f:
            template = f.read()

        rendered = template.replace('{{package}}', 'myapp').replace('{{project}}', 'myapp')
        rendered = '\n'.join(
            line for line in rendered.splitlines()
            if not line.strip().startswith('{{')
        )
        pyproject = tomllib.loads(rendered)

        i18n = pyproject['tool']['tg']['devtools']['i18n']
        self.assertEqual(i18n['domain'], 'myapp')
        self.assertEqual(i18n['directory'], 'myapp/i18n')
        self.assertEqual(i18n['pot_file'], 'myapp/i18n/myapp.pot')
        self.assertEqual(i18n['extract'], {
            'mapping_file': 'pyproject.toml',
            'keywords': ['l_'],
            'add_comments': 'TRANSLATORS:',
            'width': 80,
        })
        self.assertTrue(i18n['update']['previous'])
        self.assertTrue(i18n['compile']['statistics'])
        self.assertEqual(set(pyproject['tool']['babel'].keys()), {'mappings'})

        mappings = {mapping['method']: mapping for mapping in pyproject['tool']['babel']['mappings']}
        self.assertEqual(set(mappings), {'python', 'ignore', 'kajiki'})
        self.assertEqual(mappings['python']['pattern'], '**.py')
        self.assertEqual(mappings['ignore']['pattern'], 'public/**')
        self.assertEqual(mappings['kajiki']['pattern'], '**/templates/**.xhtml')
        self.assertTrue(fnmatch.fnmatchcase('myapp/templates/demo/index.xhtml', mappings['kajiki']['pattern']))
        self.assertFalse(mappings['kajiki']['strip_text'])
        self.assertTrue(mappings['kajiki']['extract_python'])
        self.assertNotIn('options', mappings['kajiki'])
        self.assertNotIn('[tool.babel.mappings.options]', template)


if __name__ == '__main__':
    unittest.main()
