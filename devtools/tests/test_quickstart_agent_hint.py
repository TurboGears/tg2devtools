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
            ('Evo 017 Hint Project', 'Evo-017-Hint-Project'),
            (' -myapp', '-myapp'),
        )
        try:
            for project_name, project_dir_name in cases:
                with self.subTest(project_name=project_name):
                    os.chdir(temp_dir)
                    command = QuickstartCommand(None, {})
                    opts = command.get_parser('tg2devtools-test').parse_args([project_name])
                    stdout = io.StringIO()

                    with redirect_stdout(stdout):
                        command.run(opts)

                    project_dir = os.path.join(temp_dir, project_dir_name)
                    self.assertIn(
                        'TurboGears agent skills installed in', stdout.getvalue()
                    )
                    self.assertIn('Target: .agents/skills/', stdout.getvalue())
                    self.assertTrue(os.path.isdir(os.path.join(project_dir, '.agents', 'skills')))
                    self.assertFalse(os.path.exists(os.path.join(project_dir, '.claude')))
                    for skill_name in ('tg-inspect', 'tg-scaffold', 'tg-shell'):
                        skill_path = os.path.join(
                            project_dir, '.agents', 'skills', skill_name
                        )
                        self.assertTrue(os.path.isdir(skill_path), skill_name)
                    self.assertTrue(os.path.exists(os.path.join(project_dir, 'AGENTS.md')))
        finally:
            os.chdir(base_dir)
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_migration_capabilities_match_generated_options(self):
        base_dir = os.getcwd()
        temp_dir = tempfile.mkdtemp()
        try:
            cases = (
                (QuickstartCommand, [], 'MigrationFullSql', True),
                (QuickstartAPICommand, [], 'MigrationApiSql', True),
                (QuickstartCommand, ['--disable-migrations'], 'MigrationNoSql', False),
                (QuickstartAPICommand, ['--disable-migrations'], 'MigrationApiNoSql', False),
                (QuickstartCommand, ['--ming'], 'MigrationFullMing', False),
                (QuickstartAPICommand, ['--ming'], 'MigrationApiMing', False),
            )
            for command_class, args, project_name, migrations in cases:
                with self.subTest(project_name=project_name):
                    os.chdir(temp_dir)
                    command = command_class(None, {})
                    opts = command.get_parser('tg2devtools-test').parse_args(args + [project_name])
                    with redirect_stdout(io.StringIO()):
                        command.run(opts)

                    project_dir = os.path.join(temp_dir, project_name)
                    package_name = project_name.lower().replace('-', '')
                    with open(os.path.join(project_dir, 'pyproject.toml')) as pyproject_file:
                        pyproject = pyproject_file.read()
                    with open(
                        os.path.join(project_dir, package_name, 'websetup', 'schema.py')
                    ) as schema_file:
                        schema = schema_file.read()

                    self.assertEqual(os.path.isdir(os.path.join(project_dir, 'migration')), migrations)
                    self.assertEqual('import alembic' in schema, migrations)
                    if migrations:
                        self.assertIn('alembic', pyproject)
                    else:
                        self.assertNotIn('alembic', pyproject)
        finally:
            os.chdir(base_dir)
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_quickstart_variants_generate_agents_md_and_skills(self):
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
                    stdout = io.StringIO()
                    with redirect_stdout(stdout):
                        command.run(opts)

                    project_dir = os.path.join(temp_dir, project_name.replace(' ', '-'))
                    self.assertTrue(os.path.exists(os.path.join(project_dir, 'AGENTS.md')))
                    self.assertTrue(os.path.isdir(os.path.join(project_dir, '.agents', 'skills')))
                    self.assertFalse(os.path.exists(os.path.join(project_dir, '.claude')))
                    for skill_name in ('tg-inspect', 'tg-scaffold', 'tg-shell'):
                        skill_path = os.path.join(
                            project_dir, '.agents', 'skills', skill_name
                        )
                        self.assertTrue(os.path.isdir(skill_path), skill_name)
                    self.assertIn('Target: .agents/skills/', stdout.getvalue())
        finally:
            os.chdir(base_dir)
            shutil.rmtree(temp_dir, ignore_errors=True)
