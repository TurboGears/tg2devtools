import io
import os
import shutil
import tempfile
import unittest

from contextlib import redirect_stdout

from devtools.gearbox.quickstart import QuickstartCommand


class TestQuickstartAgentHint(unittest.TestCase):

    def test_quickstart_prints_agent_hint_without_generating_agent_config(self):
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
                        'To enable TurboGears-aware coding agents for this project, run: '
                        'cd %s; gearbox tgmcp init claude # or codex, vscode, pi, all' % hint_dir
                    )
                    self.assertTrue(os.path.isdir(project_dir))
                    self.assertEqual(expected_hint, stdout.getvalue().rstrip().splitlines()[-1])
                    for relative_path in (
                            '.mcp.json', '.codex/config.toml', '.vscode/mcp.json', 'AGENTS.md'):
                        self.assertFalse(os.path.exists(os.path.join(project_dir, relative_path)),
                                         relative_path)
        finally:
            os.chdir(base_dir)
            shutil.rmtree(temp_dir, ignore_errors=True)
