import io
import os
import shutil
import tempfile
import unittest

from contextlib import redirect_stdout

from devtools.gearbox.quickstart import QuickstartCommand


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
