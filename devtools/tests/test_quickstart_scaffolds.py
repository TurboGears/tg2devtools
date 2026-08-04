import argparse

import pytest

from devtools.gearbox.quickstart import QuickstartCommand
from devtools.gearbox.quickstart.command import QuickstartAPICommand, safe_name
from gearbox.commands.scaffold import ScaffoldCommand


@pytest.mark.parametrize(
    ("command_class", "scaffolds", "paths"),
    [
        (
            QuickstartCommand,
            ("controller", "controller_test", "model", "template"),
            (
                "scaffoldfull/controllers/articles.py",
                "scaffoldfull/tests/functional/test_articles.py",
                "scaffoldfull/model/articles.py",
                "scaffoldfull/templates/articles.xhtml",
            ),
        ),
        (
            QuickstartAPICommand,
            ("api_controller", "controller_test", "model"),
            (
                "scaffoldapi/controllers/api/articles.py",
                "scaffoldapi/tests/functional/test_articles.py",
                "scaffoldapi/model/articles.py",
            ),
        ),
    ],
)
def test_quickstart_scaffolds_create_rendered_files(
    tmp_path, monkeypatch, command_class, scaffolds, paths
):
    monkeypatch.chdir(tmp_path)
    command = command_class(None, {})
    project_name = (
        "Scaffold Full" if command_class is QuickstartCommand else "Scaffold API"
    )
    options = command.get_parser("gearbox quickstart").parse_args([project_name])

    assert command.run(options) in (None, 0)

    project_dir = tmp_path / safe_name(project_name)
    monkeypatch.chdir(project_dir)
    scaffold = ScaffoldCommand(None, {})
    scaffold.take_action(
        argparse.Namespace(
            scaffold_name=scaffolds,
            target="articles",
            lookup=None,
            path=None,
            subdir=None,
            nopackage=False,
            force=False,
            dry_run=False,
        )
    )

    for relative_path in paths:
        generated_file = project_dir / relative_path
        assert generated_file.is_file()
        content = generated_file.read_text()
        assert "{{" not in content
        if generated_file.suffix == ".py":
            compile(content, str(generated_file), "exec")


@pytest.mark.parametrize(
    ("command_class", "database_option", "project_name"),
    [
        (QuickstartCommand, "--sqlalchemy", "No Auth Full SQLAlchemy"),
        (QuickstartAPICommand, "--sqlalchemy", "No Auth API SQLAlchemy"),
        (QuickstartCommand, "--ming", "No Auth Full Ming"),
        (QuickstartAPICommand, "--ming", "No Auth API Ming"),
    ],
)
def test_no_auth_model_scaffolds_do_not_reference_users(
    tmp_path, monkeypatch, command_class, database_option, project_name
):
    monkeypatch.chdir(tmp_path)
    command = command_class(None, {})
    options = command.get_parser("gearbox quickstart").parse_args(
        [database_option, "--noauth", project_name]
    )

    assert command.run(options) in (None, 0)

    project_dir = tmp_path / safe_name(project_name)
    monkeypatch.chdir(project_dir)
    ScaffoldCommand(None, {}).take_action(
        argparse.Namespace(
            scaffold_name=("model",),
            target="articles",
            lookup=None,
            path=None,
            subdir=None,
            nopackage=False,
            force=False,
            dry_run=False,
        )
    )

    model_file = project_dir / options.package / "model" / "articles.py"
    content = model_file.read_text()
    assert "User" not in content
    assert "tg_user" not in content
    compile(content, str(model_file), "exec")


def test_no_database_quickstarts_do_not_offer_model_scaffolds(
    tmp_path, monkeypatch
):
    for command_class, project_name in (
        (QuickstartCommand, "No Database Full"),
        (QuickstartAPICommand, "No Database API"),
    ):
        monkeypatch.chdir(tmp_path)
        command = command_class(None, {})
        options = command.get_parser("gearbox quickstart").parse_args(
            ["--nosa", project_name]
        )

        assert command.run(options) in (None, 0)

        project_dir = tmp_path / safe_name(project_name)
        model_scaffold = project_dir / options.package / "model" / "model.py.template"
        assert not model_scaffold.exists()
