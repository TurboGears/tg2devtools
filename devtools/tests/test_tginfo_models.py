import contextlib
import importlib
import io
import json
import os
import sys
import tempfile
import textwrap
import types
import unittest
from pathlib import Path

from devtools.gearbox.tginfo import TgInfoCommand

class TgInfoModelsTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tempdir.name)
        (self.project_root / 'development.ini').write_text('[app:main]\n')
        (self.project_root / 'pyproject.toml').write_text(textwrap.dedent('''\
            [project.entry-points."paste.app_factory"]
            main = "sampleapp.config.application:make_app"
        '''))
        (self.project_root / 'external_models.py').write_text(textwrap.dedent('''\
            class ImportedThing(object):
                pass
        '''))
        package = self.project_root / 'sampleapp'
        model = package / 'model'
        model.mkdir(parents=True)
        (package / '__init__.py').write_text('')
        (model / '__init__.py').write_text(textwrap.dedent('''\
            from external_models import ImportedThing
            from sampleapp.model.auth import User
            from sampleapp.model.docs import WikiPage
            from sampleapp.model.misc import PlainModel, PublicButNotExported

            __all__ = ('User', 'WikiPage', 'PlainModel', 'ImportedThing')

            setting = 'not a model'

            def helper():
                pass
        '''))
        (model / 'auth.py').write_text(textwrap.dedent('''\
            class User(object):
                """User model docs."""
                __table__ = object()
        '''))
        (model / 'docs.py').write_text(textwrap.dedent('''\
            class WikiPage(object):
                """Wiki page docs."""
                class __mongometa__:
                    name = 'wiki_page'
        '''))
        (model / 'misc.py').write_text(textwrap.dedent('''\
            class PlainModel(object):
                """Plain project model docs."""
                pass

            class PublicButNotExported(object):
                pass
        '''))
        (model / 'unexported.py').write_text("raise AssertionError('tginfo must not recursively import model modules')\n")

        self.old_modules = dict(sys.modules)
        self.replaced_modules = {
            name: sys.modules.get(name)
            for name in ('tg', 'paste', 'paste.deploy')
        }

    def tearDown(self):
        for name in list(sys.modules):
            if name not in self.old_modules:
                sys.modules.pop(name, None)
        for name, module in self.replaced_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        self.tempdir.cleanup()

    def take_tginfo(self, subcommand, *args):
        command = TgInfoCommand(None, {})
        opts = command.get_parser('gearbox tginfo').parse_args([
            subcommand, '--project', str(self.project_root), *args,
        ])
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            command.take_action(opts)
        return stdout.getvalue(), stderr.getvalue()

    def run_tginfo(self, subcommand):
        stdout, _ = self.take_tginfo(subcommand, '--json')
        return json.loads(stdout)

    def install_app_loading_sentinels(self):
        tg = types.ModuleType('tg')
        sys.modules['tg'] = tg

        paste = types.ModuleType('paste')
        deploy = types.ModuleType('paste.deploy')
        calls = []

        def loadapp(config_name, relative_to=None):
            calls.append((config_name, relative_to))
            raise AssertionError('model inventory must not initialize the PasteDeploy app')

        deploy.loadapp = loadapp
        paste.deploy = deploy
        sys.modules['paste'] = paste
        sys.modules['paste.deploy'] = deploy
        return calls

    def test_models_lists_exported_sqlalchemy_ming_and_unknown_project_classes(self):
        calls = self.install_app_loading_sentinels()

        models = self.run_tginfo('models')

        self.assertEqual(calls, [])
        expected_row_keys = {'name', 'class', 'module', 'source', 'orm', 'docstring'}
        for row in models:
            self.assertEqual(set(row), expected_row_keys)
            self.assertFalse(os.path.isabs(row['source'].rsplit(':', 1)[0]))
        by_name = {row['name']: row for row in models}
        self.assertEqual(set(by_name), {'PlainModel', 'User', 'WikiPage'})
        self.assertEqual(by_name['User']['class'], 'sampleapp.model.auth.User')
        self.assertEqual(by_name['User']['module'], 'sampleapp.model.auth')
        self.assertEqual(by_name['User']['orm'], 'sqlalchemy')
        self.assertEqual(by_name['User']['docstring'], 'User model docs.')
        self.assertEqual(by_name['WikiPage']['class'], 'sampleapp.model.docs.WikiPage')
        self.assertEqual(by_name['WikiPage']['orm'], 'ming')
        self.assertEqual(by_name['WikiPage']['docstring'], 'Wiki page docs.')
        self.assertEqual(by_name['PlainModel']['class'], 'sampleapp.model.misc.PlainModel')
        self.assertEqual(by_name['PlainModel']['orm'], 'unknown')
        self.assertEqual(by_name['PlainModel']['docstring'], 'Plain project model docs.')
        json.dumps(models, sort_keys=True)

    def test_models_subcommand_prints_human_rows(self):
        self.install_app_loading_sentinels()

        output, _ = self.take_tginfo('models')

        self.assertIn('User [sqlalchemy] sampleapp.model.auth.User (sampleapp/model/auth.py:1)', output)
        self.assertIn('WikiPage [ming] sampleapp.model.docs.WikiPage (sampleapp/model/docs.py:1)', output)
        self.assertTrue(output.endswith('\n'))
        self.assertFalse(output.endswith('\n\n'))

    def write_nested_pyproject_app(self):
        (self.project_root / 'pyproject.toml').write_text(textwrap.dedent('''\
            [project.entry-points."paste.app_factory"]
            main = "company.sample.config.application:make_app"
        '''))
        package = self.project_root / 'company' / 'sample'
        model = package / 'model'
        config = package / 'config'
        model.mkdir(parents=True)
        config.mkdir()
        (package / '__init__.py').write_text('')
        (config / '__init__.py').write_text('')
        (config / 'application.py').write_text(textwrap.dedent('''\
            def make_app(global_conf, **app_conf):
                raise AssertionError("must not load app")
        '''))
        (model / '__init__.py').write_text(textwrap.dedent('''\
            from company.sample.model.things import NestedModel

            __all__ = ('NestedModel',)
        '''))
        (model / 'things.py').write_text(textwrap.dedent('''\
            class NestedModel(object):
                __table__ = object()
        '''))
        (model / 'unexported.py').write_text("raise AssertionError('tginfo must not recursively import nested model modules')\n")

    def test_models_uses_nested_pyproject_app_package(self):
        self.write_nested_pyproject_app()
        calls = self.install_app_loading_sentinels()

        models = self.run_tginfo('models')

        self.assertEqual(calls, [])
        self.assertEqual({row['name'] for row in models}, {'NestedModel'})
        self.assertEqual(models[0]['class'], 'company.sample.model.things.NestedModel')

    def test_models_scan_public_classes_when_model_package_has_no_all(self):
        (self.project_root / 'sampleapp' / 'model' / '__init__.py').write_text(textwrap.dedent('''\
            from external_models import ImportedThing
            from sampleapp.model.auth import User
            from sampleapp.model.docs import WikiPage
            from sampleapp.model.misc import PlainModel, PublicButNotExported
        '''))
        calls = self.install_app_loading_sentinels()

        models = self.run_tginfo('models')

        self.assertEqual(calls, [])
        self.assertEqual(
            {row['name'] for row in models},
            {'PlainModel', 'PublicButNotExported', 'User', 'WikiPage'},
        )

    def test_models_falls_back_to_unique_top_level_model_package(self):
        (self.project_root / 'pyproject.toml').unlink()
        calls = self.install_app_loading_sentinels()

        models = self.run_tginfo('models')

        self.assertEqual(calls, [])
        self.assertEqual({row['name'] for row in models}, {'PlainModel', 'User', 'WikiPage'})

    def test_models_returns_empty_list_when_project_has_no_model_package(self):
        package = self.project_root / 'sampleapp'
        for path in sorted((package / 'model').glob('*'), reverse=True):
            path.unlink()
        (package / 'model').rmdir()
        calls = self.install_app_loading_sentinels()

        models = self.run_tginfo('models')

        self.assertEqual(calls, [])
        self.assertEqual(models, [])




if __name__ == '__main__':
    unittest.main()
