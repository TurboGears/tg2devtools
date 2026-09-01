import io
import os
import shutil
import sys
import tempfile
import unittest

from contextlib import redirect_stderr, redirect_stdout


class TestTgSkillsCommand(unittest.TestCase):
    """Test the gearbox tgskills command."""

    def setUp(self):
        self.base_dir = os.getcwd()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        os.chdir(self.base_dir)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_tgskills_installs_skills_in_agents_dir_by_default(self):
        """The default target is the project-local .agents/skills directory."""
        # Create a test project directory
        project_dir = os.path.join(self.temp_dir, 'testproject')
        os.makedirs(project_dir)
        os.chdir(project_dir)

        # Import and run the command
        from devtools.gearbox.tgskills import TgSkillsCommand, SKILL_NAMES

        command = TgSkillsCommand(None, {})
        opts = command.get_parser('gearbox tgskills').parse_args([])

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            command.run(opts)

        full_target = os.path.join(project_dir, '.agents', 'skills')
        self.assertTrue(os.path.isdir(full_target))
        self.assertFalse(os.path.exists(os.path.join(project_dir, '.claude')))
        self.assertIn('Target: .agents/skills/', stdout.getvalue())
        for skill_name in SKILL_NAMES:
            skill_path = os.path.join(full_target, skill_name)
            self.assertTrue(os.path.exists(skill_path), skill_path)
            self.assertTrue(os.path.islink(skill_path) or os.path.isdir(skill_path))

    def test_tgskills_help_describes_claude_target(self):
        from devtools.gearbox.tgskills import TgSkillsCommand

        help_text = TgSkillsCommand(None, {}).get_parser('gearbox tgskills').format_help()

        self.assertIn('--claude', help_text)
        self.assertIn('.claude/skills/', help_text)
        self.assertIn('.agents/skills/', help_text)

    def test_tgskills_does_not_overwrite_existing_skill_directory(self):
        """Test that tgskills does not overwrite an existing non-symlink skill directory."""
        project_dir = os.path.join(self.temp_dir, 'testproject')
        os.makedirs(project_dir)
        
        # Create a hand-written skill directory
        agents_skills_dir = os.path.join(project_dir, '.agents', 'skills')
        os.makedirs(agents_skills_dir)
        custom_skill_dir = os.path.join(agents_skills_dir, 'tg-inspect')
        os.makedirs(custom_skill_dir)
        with open(os.path.join(custom_skill_dir, 'SKILL.md'), 'w') as f:
            f.write('---\nname: tg-inspect\ndescription: Custom skill\n---\n# Custom')
        
        os.chdir(project_dir)

        from devtools.gearbox.tgskills import TgSkillsCommand

        command = TgSkillsCommand(None, {})
        opts = command.get_parser('gearbox tgskills').parse_args([])

        stderr_capture = io.StringIO()
        # Capture stderr
        old_stderr = sys.stderr
        sys.stderr = stderr_capture
        try:
            with redirect_stdout(io.StringIO()):
                command.take_action(opts)
        finally:
            sys.stderr = old_stderr

        # The custom skill should still exist and be unchanged
        self.assertTrue(os.path.exists(custom_skill_dir))
        with open(os.path.join(custom_skill_dir, 'SKILL.md')) as f:
            content = f.read()
        self.assertIn('Custom skill', content)

    def test_tgskills_with_project_argument(self):
        """Test that tgskills respects the --project argument."""
        project_dir = os.path.join(self.temp_dir, 'myproject')
        os.makedirs(project_dir)
        
        # Run from a different directory
        other_dir = os.path.join(self.temp_dir, 'other')
        os.makedirs(other_dir)
        os.chdir(other_dir)

        from devtools.gearbox.tgskills import TgSkillsCommand, SKILL_NAMES

        command = TgSkillsCommand(None, {})
        opts = command.get_parser('gearbox tgskills').parse_args([
            '--project', project_dir
        ])

        with redirect_stdout(io.StringIO()):
            command.take_action(opts)

        # Check that skills were installed in the specified project directory
        full_target = os.path.join(project_dir, '.agents', 'skills')
        self.assertTrue(os.path.isdir(full_target))
        self.assertFalse(os.path.exists(os.path.join(project_dir, '.claude')))
        for skill_name in SKILL_NAMES:
            skill_path = os.path.join(full_target, skill_name)
            self.assertTrue(os.path.exists(skill_path), skill_path)

    def test_tgskills_claude_flag_installs_only_claude_dir(self):
        project_dir = os.path.join(self.temp_dir, 'claude-project')
        os.makedirs(project_dir)
        os.chdir(self.temp_dir)

        from devtools.gearbox.tgskills import TgSkillsCommand, SKILL_NAMES

        command = TgSkillsCommand(None, {})
        opts = command.get_parser('gearbox tgskills').parse_args([
            '--project', project_dir, '--claude'
        ])
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            command.run(opts)

        full_target = os.path.join(project_dir, '.claude', 'skills')
        self.assertTrue(os.path.isdir(full_target))
        self.assertFalse(os.path.exists(os.path.join(project_dir, '.agents')))
        self.assertIn('Target: .claude/skills/', stdout.getvalue())
        for skill_name in SKILL_NAMES:
            self.assertTrue(os.path.exists(os.path.join(full_target, skill_name)))

    def test_tgskills_rejects_agents_symlink_outside_project(self):
        project_dir = os.path.join(self.temp_dir, 'agents-project')
        outside_dir = os.path.join(self.temp_dir, 'outside-agents')
        os.makedirs(project_dir)
        os.makedirs(outside_dir)
        os.symlink(outside_dir, os.path.join(project_dir, '.agents'))
        os.chdir(self.temp_dir)

        from devtools.gearbox.tgskills import TgSkillsCommand

        command = TgSkillsCommand(None, {})
        opts = command.get_parser('gearbox tgskills').parse_args([
            '--project', project_dir
        ])
        stderr = io.StringIO()
        with self.assertRaises(SystemExit) as failure:
            with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
                command.take_action(opts)

        self.assertEqual(failure.exception.code, 1)
        self.assertIn('outside project directory', stderr.getvalue())
        self.assertTrue(os.path.islink(os.path.join(project_dir, '.agents')))
        self.assertFalse(os.path.exists(os.path.join(outside_dir, 'skills')))

    def test_tgskills_rejects_claude_symlink_outside_project(self):
        project_dir = os.path.join(self.temp_dir, 'claude-project')
        outside_dir = os.path.join(self.temp_dir, 'outside-claude')
        os.makedirs(project_dir)
        os.makedirs(outside_dir)
        os.symlink(outside_dir, os.path.join(project_dir, '.claude'))
        os.chdir(self.temp_dir)

        from devtools.gearbox.tgskills import TgSkillsCommand

        command = TgSkillsCommand(None, {})
        opts = command.get_parser('gearbox tgskills').parse_args([
            '--project', project_dir, '--claude'
        ])
        stderr = io.StringIO()
        with self.assertRaises(SystemExit) as failure:
            with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
                command.take_action(opts)

        self.assertEqual(failure.exception.code, 1)
        self.assertIn('outside project directory', stderr.getvalue())
        self.assertTrue(os.path.islink(os.path.join(project_dir, '.claude')))
        self.assertFalse(os.path.exists(os.path.join(outside_dir, 'skills')))

    def test_tgskills_rejects_nested_agents_skills_symlink_outside_project(self):
        project_dir = os.path.join(self.temp_dir, 'agents-project')
        outside_dir = os.path.join(self.temp_dir, 'outside-agents-skills')
        os.makedirs(os.path.join(project_dir, '.agents'))
        os.makedirs(outside_dir)
        os.symlink(outside_dir, os.path.join(project_dir, '.agents', 'skills'))
        os.chdir(self.temp_dir)

        from devtools.gearbox.tgskills import TgSkillsCommand

        command = TgSkillsCommand(None, {})
        opts = command.get_parser('gearbox tgskills').parse_args([
            '--project', project_dir
        ])
        stderr = io.StringIO()
        with self.assertRaises(SystemExit) as failure:
            with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
                command.take_action(opts)

        self.assertEqual(failure.exception.code, 1)
        self.assertIn('outside project directory', stderr.getvalue())
        self.assertTrue(os.path.islink(os.path.join(project_dir, '.agents', 'skills')))
        self.assertEqual([], os.listdir(outside_dir))

    def test_tgskills_rejects_nested_claude_skills_symlink_outside_project(self):
        project_dir = os.path.join(self.temp_dir, 'claude-project')
        outside_dir = os.path.join(self.temp_dir, 'outside-claude-skills')
        os.makedirs(os.path.join(project_dir, '.claude'))
        os.makedirs(outside_dir)
        os.symlink(outside_dir, os.path.join(project_dir, '.claude', 'skills'))
        os.chdir(self.temp_dir)

        from devtools.gearbox.tgskills import TgSkillsCommand

        command = TgSkillsCommand(None, {})
        opts = command.get_parser('gearbox tgskills').parse_args([
            '--project', project_dir, '--claude'
        ])
        stderr = io.StringIO()
        with self.assertRaises(SystemExit) as failure:
            with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
                command.take_action(opts)

        self.assertEqual(failure.exception.code, 1)
        self.assertIn('outside project directory', stderr.getvalue())
        self.assertTrue(os.path.islink(os.path.join(project_dir, '.claude', 'skills')))
        self.assertEqual([], os.listdir(outside_dir))


if __name__ == '__main__':
    unittest.main()
