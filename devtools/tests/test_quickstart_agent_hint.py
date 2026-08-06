import io
import os
import shutil
import tempfile
import unittest

from contextlib import redirect_stdout

from devtools.gearbox.quickstart import QuickstartAPICommand, QuickstartCommand


class TestQuickstartAgentHint(unittest.TestCase):

    def test_quickstart_generates_agents_md_and_prints_hint(self):
        base_dir = os.getcwd()
        temp_dir = tempfile.mkdtemp()
        cases = (
            ('Evo 017 Hint Project', 'Evo-017-Hint-Project', 'Evo-017-Hint-Project'),
            (' -myapp', '-myapp', './-myapp'),
        )
        try:
            for project_name, project_dir_name, hint_dir in cases:
                with self.subTest(project_name=project_name):
                    os.chdir(temp_dir)
                    command = QuickstartCommand(None, {})
                    opts = command.get_parser('tg2devtools-test').parse_args([project_name])
                    stdout = io.StringIO()

                    with redirect_stdout(stdout):
                        command.run(opts)

                    project_dir = os.path.join(temp_dir, project_dir_name)
                    expected_hint = (
                        'To enable TurboGears-aware coding agents for this project, run:\n'
                        'cd %s; gearbox tgskills' % hint_dir
                    )
                    output_lines = stdout.getvalue().rstrip().splitlines()
                    self.assertEqual(expected_hint, '\n'.join(output_lines[-2:]))
                    
                    # AGENTS.md should be generated from template
                    agents_md_path = os.path.join(project_dir, 'AGENTS.md')
                    self.assertTrue(os.path.exists(agents_md_path), 'AGENTS.md should be generated')
                    
                    # Check AGENTS.md content
                    with open(agents_md_path) as f:
                        content = f.read()
                    self.assertIn('gearbox tgskills', content)
                    self.assertIn('tg-inspect', content)
                    self.assertIn('tg-scaffold', content)
                    self.assertIn('tg-shell', content)
        finally:
            os.chdir(base_dir)
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_quickstart_variants_generate_profile_and_inspection_guidance(self):
        base_dir = os.getcwd()
        temp_dir = tempfile.mkdtemp()
        try:
            for command_class, project_name in (
                (QuickstartCommand, 'Guidance Full'),
                (QuickstartAPICommand, 'Guidance API'),
            ):
                with self.subTest(command_class=command_class):
                    os.chdir(temp_dir)
                    command = command_class(None, {})
                    opts = command.get_parser('tg2devtools-test').parse_args([project_name])
                    command.run(opts)

                    project_dir = os.path.join(temp_dir, project_name.replace(' ', '-'))
                    with open(os.path.join(project_dir, 'README.rst')) as readme_file:
                        readme = readme_file.read()
                    with open(os.path.join(project_dir, 'AGENTS.md')) as agents_file:
                        agents = agents_file.read()

                    self.assertIn('development.ini', readme)
                    self.assertIn('test.ini', readme)
                    self.assertIn('does not generate ``production.ini``', readme)
                    self.assertIn(
                        'gearbox tginfo summary --project . --config development.ini --json',
                        readme,
                    )
                    self.assertIn('python -m pytest --collect-only -q', readme)

                    for command in (
                        'gearbox tginfo summary --project . --config development.ini --json',
                        'gearbox tginfo routes --project . --config development.ini --json',
                        'gearbox tginfo models --project . --config development.ini --json',
                        'gearbox tginfo templates --project . --config development.ini --json',
                        'gearbox tginfo scaffolds --project . --config development.ini --json',
                    ):
                        self.assertIn(command, agents)
                    self.assertIn('python -m pytest --collect-only -q', agents)
                    self.assertIn('gearbox migrate -c development.ini db_version', agents)
                    self.assertIn('gearbox tgshell -c development.ini', agents)
                    self.assertIn('does not generate `production.ini`', agents)
                    self.assertIn('import, startup, and request-hook code', agents)
        finally:
            os.chdir(base_dir)
            shutil.rmtree(temp_dir, ignore_errors=True)
