"""TurboGears Agent Skills installation command."""

import os
import sys

from gearbox.command import Command


# Skill names to install
SKILL_NAMES = ['tg-inspect', 'tg-scaffold', 'tg-shell']

# Target directories for skills
TARGET_DIRS = ['.agents/skills', '.claude/skills']


class TgSkillsCommand(Command):
    """Install TurboGears agent skills for AI coding assistants."""

    def get_description(self):
        return 'Install TurboGears agent skills'

    def get_parser(self, prog_name):
        parser = super(TgSkillsCommand, self).get_parser(prog_name)
        parser.add_argument(
            '--project', default='.',
            help='project root directory (default: current directory)'
        )
        return parser

    def take_action(self, opts):
        project_dir = os.path.realpath(
            os.path.abspath(os.path.expanduser(opts.project))
        )

        # Find the skills source directory (relative to this package)
        skills_pkg_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'skills'
        )

        if not os.path.isdir(skills_pkg_path):
            sys.stderr.write(
                f'Cannot find skills source directory at {skills_pkg_path}\n'
            )
            sys.exit(1)

        # Create target directories and install skills
        for target_dir in TARGET_DIRS:
            install_dir = os.path.join(project_dir, target_dir)
            _install_skills(skills_pkg_path, install_dir, project_dir)

        sys.stdout.write(
            f'TurboGears agent skills installed in {project_dir}\n'
        )
        sys.stdout.write(
            f'  - .agents/skills/ (Codex, VS Code, Pi, etc.)\n'
        )
        sys.stdout.write(
            f'  - .claude/skills/ (Claude Code)\n'
        )
        sys.stdout.write(
            'Skills: tg-inspect, tg-scaffold, tg-shell\n'
        )


def _install_skills(source_skills_dir, target_dir, project_dir):
    """Install skills from source to target directory.
    
    Creates symlinks to the skill directories. If symlinks cannot be created
    (e.g., on Windows without permissions), falls back to copying.
    """
    # Create target directory if it doesn't exist
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)

    # Check if target_dir is actually a directory
    if not os.path.isdir(target_dir):
        sys.stderr.write(
            f'Target path {target_dir} exists but is not a directory\n'
        )
        sys.exit(1)

    installed = []
    for skill_name in SKILL_NAMES:
        source_skill = os.path.join(source_skills_dir, skill_name)
        target_skill = os.path.join(target_dir, skill_name)

        # Check if source exists
        if not os.path.isdir(source_skill):
            sys.stderr.write(
                f'Source skill {skill_name} not found at {source_skill}\n'
            )
            continue

        # Check if target already exists as a non-symlink directory (user-created)
        if os.path.exists(target_skill):
            if os.path.islink(target_skill):
                # Already a symlink, check if it points to our source
                existing_target = os.path.realpath(target_skill)
                expected_target = os.path.realpath(source_skill)
                if existing_target == expected_target:
                    # Already installed correctly
                    installed.append(skill_name)
                    continue
                else:
                    # Symlink points somewhere else - this might be user-created
                    sys.stderr.write(
                        f'Skill {skill_name} already exists at {target_skill} '
                        f'(symlink to {existing_target}) - not overwriting\n'
                    )
                    continue
            else:
                # Non-symlink directory exists - user-created, don't overwrite
                sys.stderr.write(
                    f'Skill {skill_name} directory already exists at {target_skill} '
                    f'- not overwriting (remove it first if you want to reinstall)\n'
                )
                continue

        # Create relative symlink from target to source
        # Calculate relative path from target_dir to source_skill
        rel_source = os.path.relpath(source_skill, os.path.dirname(target_skill))

        try:
            os.symlink(rel_source, target_skill)
            installed.append(skill_name)
        except OSError as e:
            # Symlink failed, try copying
            sys.stderr.write(
                f'Warning: could not create symlink for {skill_name}: {e}\n'
            )
            try:
                _copy_skill(source_skill, target_skill)
                installed.append(skill_name)
                sys.stderr.write(
                    f'  Copied {skill_name} instead of symlinking\n'
                )
            except OSError as copy_error:
                sys.stderr.write(
                    f'  Failed to copy {skill_name}: {copy_error}\n'
                )

    return installed


def _copy_skill(source, target):
    """Recursively copy a skill directory."""
    import shutil
    shutil.copytree(source, target)
