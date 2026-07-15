import io
import os
import shutil
import sys
import tempfile
import unittest

from contextlib import redirect_stdout


class TestTgSkillsCommand(unittest.TestCase):
    """Test the gearbox tgskills command."""

    def setUp(self):
        self.base_dir = os.getcwd()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        os.chdir(self.base_dir)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_tgskills_installs_skills_in_agents_and_claude_dirs(self):
        """Test that tgskills installs symlinks in both .agents/skills and .claude/skills."""
        # Create a test project directory
        project_dir = os.path.join(self.temp_dir, 'testproject')
        os.makedirs(project_dir)
        os.chdir(project_dir)

        # Import and run the command
        from devtools.gearbox.tgskills import TgSkillsCommand, SKILL_NAMES, TARGET_DIRS

        command = TgSkillsCommand(None, {})
        opts = command.get_parser('gearbox tgskills').parse_args([])

        with redirect_stdout(io.StringIO()):
            command.take_action(opts)

        # Check that both target directories were created
        for target_dir in TARGET_DIRS:
            full_target = os.path.join(project_dir, target_dir)
            self.assertTrue(
                os.path.isdir(full_target),
                f'Target directory {target_dir} should exist'
            )

        # Check that all skills are installed in both directories
        for target_dir in TARGET_DIRS:
            full_target = os.path.join(project_dir, target_dir)
            for skill_name in SKILL_NAMES:
                skill_path = os.path.join(full_target, skill_name)
                self.assertTrue(
                    os.path.exists(skill_path),
                    f'Skill {skill_name} should exist in {target_dir}'
                )
                # Should be a symlink or directory
                self.assertTrue(
                    os.path.islink(skill_path) or os.path.isdir(skill_path),
                    f'Skill {skill_name} should be a symlink or directory'
                )

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

        from devtools.gearbox.tgskills import TgSkillsCommand, TARGET_DIRS, SKILL_NAMES

        command = TgSkillsCommand(None, {})
        opts = command.get_parser('gearbox tgskills').parse_args([
            '--project', project_dir
        ])

        with redirect_stdout(io.StringIO()):
            command.take_action(opts)

        # Check that skills were installed in the specified project directory
        for target_dir in TARGET_DIRS:
            full_target = os.path.join(project_dir, target_dir)
            self.assertTrue(
                os.path.isdir(full_target),
                f'Target directory {target_dir} should exist in {project_dir}'
            )
            for skill_name in SKILL_NAMES:
                skill_path = os.path.join(full_target, skill_name)
                self.assertTrue(
                    os.path.exists(skill_path),
                    f'Skill {skill_name} should exist in {full_target}'
                )


if __name__ == '__main__':
    unittest.main()
