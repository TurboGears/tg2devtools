import io
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch
import zipfile

from devtools.gearbox.tgdocs import TgDocsCommand, _documentation_version


class TestTgDocsCommand(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.cache_home = Path(self.temp_dir) / "cache"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _run_command(self):
        command = TgDocsCommand(None, {})
        opts = command.get_parser("gearbox tgdocs").parse_args([])
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch.dict(os.environ, {"XDG_CACHE_HOME": str(self.cache_home)}):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = command.run(opts)
        return status, stdout.getvalue(), stderr.getvalue()

    def _cache_path(self, version):
        return self.cache_home / "turbogears" / "tg2docs" / version

    def test_global_command_entry_point_loads_tgdocs_command(self):
        project = (
            Path(__file__).parent.parent.parent / "pyproject.toml"
        ).read_text(encoding="utf-8")

        self.assertIn('[project.entry-points."gearbox.commands"]', project)
        self.assertIn(
            'tgdocs = "devtools.gearbox.tgdocs:TgDocsCommand"',
            project,
        )
        self.assertIs(TgDocsCommand, TgDocsCommand)

    def test_orphan_generation_is_recovered_without_publishing_parent(self):
        cache_path = self._cache_path("2.5.1")
        cache_path.mkdir(parents=True)
        older_path = cache_path / "docs-older"
        newer_path = cache_path / "docs-newer"
        older_path.mkdir()
        newer_path.mkdir()
        (older_path / "index.txt").write_text("old", encoding="utf-8")
        (newer_path / "index.txt").write_text("new", encoding="utf-8")
        os.utime(older_path, (1, 1))
        os.utime(newer_path, (2, 2))

        with (
            patch(
                "devtools.gearbox.tgdocs.importlib.metadata.version",
                return_value="2.5.1",
            ),
            patch("devtools.gearbox.tgdocs.urllib.request.urlretrieve") as download,
        ):
            status, stdout, stderr = self._run_command()

        self.assertEqual(0, status)
        self.assertEqual(
            f"TurboGears documentation in .txt format available at:\n{newer_path}\n",
            stdout,
        )
        self.assertEqual("", stderr)
        download.assert_not_called()
        self.assertFalse((cache_path / "current").exists())
        self.assertEqual("new", (newer_path / "index.txt").read_text(encoding="utf-8"))

    def test_pointer_parent_path_is_not_an_active_generation(self):
        cache_path = self._cache_path("2.5.1")
        cache_path.mkdir(parents=True)
        (cache_path / "current").write_text("..", encoding="utf-8")

        with (
            patch(
                "devtools.gearbox.tgdocs.importlib.metadata.version",
                return_value="2.5.1",
            ),
            patch(
                "devtools.gearbox.tgdocs.urllib.request.urlretrieve",
                side_effect=OSError("offline"),
            ),
        ):
            command = TgDocsCommand(None, {})
            opts = command.get_parser("gearbox tgdocs").parse_args([])
            stdout = io.StringIO()
            stderr = io.StringIO()
            with self.assertRaises(SystemExit) as failure:
                with patch.dict(os.environ, {"XDG_CACHE_HOME": str(self.cache_home)}):
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        command.run(opts)

        self.assertEqual(1, failure.exception.code)
        self.assertEqual("", stdout.getvalue())
        self.assertIn("Error:", stderr.getvalue())

    def test_current_symlink_outside_cache_is_not_used_or_modified(self):
        cache_path = self._cache_path("development")
        outside_path = Path(self.temp_dir) / "outside-current"
        cache_path.mkdir(parents=True)
        outside_path.write_text("docs-outside", encoding="utf-8")
        os.symlink(outside_path, cache_path / "current")

        def download(_url, destination):
            with zipfile.ZipFile(destination, "w") as archive:
                archive.writestr("index.txt", "new")

        with (
            patch(
                "devtools.gearbox.tgdocs.importlib.metadata.version",
                return_value="2.5.1dev1",
            ),
            patch(
                "devtools.gearbox.tgdocs.urllib.request.urlretrieve",
                side_effect=download,
            ),
        ):
            status, stdout, stderr = self._run_command()

        cached_path = Path(stdout.strip().split("\n")[-1])
        self.assertEqual(0, status)
        self.assertEqual("", stderr)
        self.assertNotEqual(outside_path, cached_path)
        self.assertEqual(cache_path.parent, cache_path.parent)
        self.assertEqual("docs-outside", outside_path.read_text(encoding="utf-8"))
        self.assertFalse((cache_path / "current").is_symlink())

    def test_symlinked_generation_is_not_active(self):
        cache_path = self._cache_path("2.5.1")
        outside_path = Path(self.temp_dir) / "outside"
        cache_path.mkdir(parents=True)
        outside_path.mkdir()
        (outside_path / "index.txt").write_text("outside", encoding="utf-8")
        os.symlink(outside_path, cache_path / "docs-linked")
        (cache_path / "current").write_text("docs-linked", encoding="utf-8")

        with (
            patch(
                "devtools.gearbox.tgdocs.importlib.metadata.version",
                return_value="2.5.1",
            ),
            patch(
                "devtools.gearbox.tgdocs.urllib.request.urlretrieve",
                side_effect=OSError("offline"),
            ),
        ):
            command = TgDocsCommand(None, {})
            opts = command.get_parser("gearbox tgdocs").parse_args([])
            stdout = io.StringIO()
            stderr = io.StringIO()
            with self.assertRaises(SystemExit) as failure:
                with patch.dict(os.environ, {"XDG_CACHE_HOME": str(self.cache_home)}):
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        command.run(opts)

        self.assertEqual(1, failure.exception.code)
        self.assertEqual("", stdout.getvalue())
        self.assertIn("Error:", stderr.getvalue())

    def test_corrupt_pointer_uses_stale_generation(self):
        cache_path = self._cache_path("development")
        active_path = cache_path / "docs-existing"
        cache_path.mkdir(parents=True)
        active_path.mkdir()
        (active_path / "index.txt").write_text("old", encoding="utf-8")
        (cache_path / "current").write_bytes(b"\xff")

        with (
            patch(
                "devtools.gearbox.tgdocs.importlib.metadata.version",
                return_value="2.5.1dev1",
            ),
            patch(
                "devtools.gearbox.tgdocs.urllib.request.urlretrieve",
                side_effect=OSError("offline"),
            ),
        ):
            status, stdout, stderr = self._run_command()

        self.assertEqual(0, status)
        self.assertEqual(
            f"TurboGears documentation in .txt format available at:\n{active_path}\n",
            stdout,
        )
        self.assertIn("stale copy", stderr)
        self.assertEqual(b"\xff", (cache_path / "current").read_bytes())
        self.assertEqual("old", (active_path / "index.txt").read_text(encoding="utf-8"))

    def test_version_mapping_uses_development_for_dev_metadata(self):
        with patch(
            "devtools.gearbox.tgdocs.importlib.metadata.version",
            return_value="2.5.1dev1",
        ):
            self.assertEqual("development", _documentation_version())
        with patch(
            "devtools.gearbox.tgdocs.importlib.metadata.version", return_value="2.5.1"
        ):
            self.assertEqual("2.5.1", _documentation_version())

    def test_stable_cache_reuse_does_not_download(self):
        cache_path = self._cache_path("2.5.1")
        cache_path.mkdir(parents=True)
        (cache_path / "index.txt").write_text("cached", encoding="utf-8")

        with (
            patch(
                "devtools.gearbox.tgdocs.importlib.metadata.version",
                return_value="2.5.1",
            ),
            patch("devtools.gearbox.tgdocs.urllib.request.urlretrieve") as download,
        ):
            status, stdout, stderr = self._run_command()

        self.assertEqual(0, status)
        self.assertEqual(
            f"TurboGears documentation in .txt format available at:\n{cache_path}\n",
            stdout,
        )
        self.assertEqual("", stderr)
        download.assert_not_called()
        self.assertEqual(
            "cached", (cache_path / "index.txt").read_text(encoding="utf-8")
        )

    def test_development_cache_always_refreshes(self):
        cache_path = self._cache_path("development")
        cache_path.mkdir(parents=True)
        (cache_path / "index.txt").write_text("old", encoding="utf-8")

        def download(url, destination):
            self.assertEqual(
                "https://turbogears.github.io/tg2docs/development/tg2docs.txt.zip", url
            )
            with zipfile.ZipFile(destination, "w") as archive:
                archive.writestr("index.txt", "new")

        with (
            patch(
                "devtools.gearbox.tgdocs.importlib.metadata.version",
                return_value="2.5.1dev1",
            ),
            patch(
                "devtools.gearbox.tgdocs.urllib.request.urlretrieve",
                side_effect=download,
            ) as mocked,
        ):
            status, stdout, stderr = self._run_command()

        cached_path = Path(stdout.strip().split("\n")[-1])
        self.assertEqual(0, status)
        self.assertEqual("", stderr)
        self.assertEqual(1, mocked.call_count)
        self.assertNotEqual(cache_path, cached_path)
        self.assertEqual("new", (cached_path / "index.txt").read_text(encoding="utf-8"))
        self.assertEqual("old", (cache_path / "index.txt").read_text(encoding="utf-8"))

    def test_development_skips_download_when_etag_unchanged(self):
        cache_path = self._cache_path("development")
        active_path = cache_path / "docs-existing"
        cache_path.mkdir(parents=True)
        active_path.mkdir()
        (active_path / "index.txt").write_text("cached", encoding="utf-8")
        (cache_path / "current").write_text("docs-existing", encoding="utf-8")
        (cache_path / "current.etag").write_text('"abc123"', encoding="utf-8")

        def mock_fetch_etag(cache_dir):
            return '"abc123"'

        with (
            patch(
                "devtools.gearbox.tgdocs.importlib.metadata.version",
                return_value="2.5.1dev1",
            ),
            patch(
                "devtools.gearbox.tgdocs._fetch_etag",
                side_effect=mock_fetch_etag,
            ),
            patch(
                "devtools.gearbox.tgdocs.urllib.request.urlretrieve",
                side_effect=OSError("should not be called"),
            ),
        ):
            status, stdout, stderr = self._run_command()

        self.assertEqual(0, status)
        self.assertEqual(
            f"TurboGears documentation in .txt format available at:\n{active_path}\n",
            stdout,
        )
        self.assertEqual("", stderr)

    def test_download_and_extraction_prints_extracted_path(self):
        def download(url, destination):
            self.assertEqual(
                "https://turbogears.github.io/tg2docs/2.5.1/tg2docs.txt.zip", url
            )
            with zipfile.ZipFile(destination, "w") as archive:
                archive.writestr("turbogears/starting.txt", "Start here")

        with (
            patch(
                "devtools.gearbox.tgdocs.importlib.metadata.version",
                return_value="2.5.1",
            ),
            patch(
                "devtools.gearbox.tgdocs.urllib.request.urlretrieve",
                side_effect=download,
            ),
        ):
            status, stdout, stderr = self._run_command()

        cached_path = Path(stdout.strip().split("\n")[-1])
        cache_path = self._cache_path("2.5.1")
        self.assertEqual(0, status)
        self.assertEqual("", stderr)
        self.assertEqual(
            "Start here",
            (cached_path / "turbogears" / "starting.txt").read_text(encoding="utf-8"),
        )
        self.assertEqual([], list(cache_path.glob(".2.5.1-*")))

    def test_public_publication_writes_pointer_and_stable_reuses_it(self):
        def download(_url, destination):
            with zipfile.ZipFile(destination, "w") as archive:
                archive.writestr("index.txt", "published")

        with (
            patch(
                "devtools.gearbox.tgdocs.importlib.metadata.version",
                return_value="2.5.1",
            ),
            patch(
                "devtools.gearbox.tgdocs.urllib.request.urlretrieve",
                side_effect=download,
            ) as mocked,
        ):
            first_status, first_stdout, first_stderr = self._run_command()
            cache_path = self._cache_path("2.5.1")
            pointer_path = cache_path / "current"
            generation_name = pointer_path.read_text(encoding="utf-8")
            first_cached_path = Path(first_stdout.strip().split("\n")[-1])

            second_status, second_stdout, second_stderr = self._run_command()

        self.assertEqual(0, first_status)
        self.assertEqual("", first_stderr)
        self.assertTrue(generation_name.startswith("docs-"))
        self.assertEqual(generation_name, first_cached_path.name)
        self.assertEqual(first_cached_path, cache_path / generation_name)
        self.assertEqual(
            "published", (first_cached_path / "index.txt").read_text(encoding="utf-8")
        )
        self.assertEqual(0, second_status)
        self.assertEqual(first_stdout, second_stdout)
        self.assertEqual("", second_stderr)
        self.assertEqual(1, mocked.call_count)

    def test_unsafe_archive_paths_fail_without_publishing_cache(self):
        for member_name in (
            "../escape.txt",
            "/escape.txt",
            "..\\escape.txt",
            "nested/../../escape.txt",
        ):
            with self.subTest(member_name=member_name):

                def download(_url, destination):
                    with zipfile.ZipFile(destination, "w") as archive:
                        archive.writestr(member_name, "should not extract")

                with (
                    patch(
                        "devtools.gearbox.tgdocs.importlib.metadata.version",
                        return_value="2.5.1",
                    ),
                    patch(
                        "devtools.gearbox.tgdocs.urllib.request.urlretrieve",
                        side_effect=download,
                    ),
                ):
                    command = TgDocsCommand(None, {})
                    opts = command.get_parser("gearbox tgdocs").parse_args([])
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with self.assertRaises(SystemExit) as failure:
                        with patch.dict(
                            os.environ, {"XDG_CACHE_HOME": str(self.cache_home)}
                        ):
                            with redirect_stdout(stdout), redirect_stderr(stderr):
                                command.run(opts)

                cache_path = self._cache_path("2.5.1")
                self.assertEqual(1, failure.exception.code)
                self.assertEqual("", stdout.getvalue())
                self.assertIn("unsafe ZIP member path", stderr.getvalue())
                self.assertFalse((cache_path / "current").exists())
                self.assertEqual([], list(cache_path.glob("docs-*")))
                self.assertFalse((self.cache_home / "escape.txt").exists())

    def test_symlink_archive_member_uses_stale_active_cache(self):
        cache_path = self._cache_path("development")
        active_path = cache_path / "docs-existing"
        cache_path.mkdir(parents=True)
        active_path.mkdir()
        (active_path / "index.txt").write_text("old", encoding="utf-8")
        (cache_path / "current").write_text("docs-existing", encoding="utf-8")

        def download(_url, destination):
            member = zipfile.ZipInfo("link")
            member.create_system = 3
            member.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(destination, "w") as archive:
                archive.writestr(member, "../outside.txt")

        with (
            patch(
                "devtools.gearbox.tgdocs.importlib.metadata.version",
                return_value="2.5.1dev1",
            ),
            patch(
                "devtools.gearbox.tgdocs.urllib.request.urlretrieve",
                side_effect=download,
            ),
        ):
            status, stdout, stderr = self._run_command()

        self.assertEqual(0, status)
        self.assertEqual(
            f"TurboGears documentation in .txt format available at:\n{active_path}\n",
            stdout,
        )
        self.assertIn("unsafe ZIP symbolic link", stderr)
        self.assertEqual(
            "docs-existing", (cache_path / "current").read_text(encoding="utf-8")
        )
        self.assertEqual("old", (active_path / "index.txt").read_text(encoding="utf-8"))
        self.assertEqual(
            [active_path],
            [path for path in cache_path.iterdir() if path.name.startswith("docs-")],
        )
        self.assertEqual([], list(cache_path.glob(".development-*")))

    def test_refresh_failure_uses_stale_cache(self):
        cache_path = self._cache_path("development")
        cache_path.mkdir(parents=True)
        (cache_path / "index.txt").write_text("old", encoding="utf-8")

        with (
            patch(
                "devtools.gearbox.tgdocs.importlib.metadata.version",
                return_value="2.5.1dev1",
            ),
            patch(
                "devtools.gearbox.tgdocs.urllib.request.urlretrieve",
                side_effect=OSError("offline"),
            ),
        ):
            status, stdout, stderr = self._run_command()

        self.assertEqual(0, status)
        self.assertEqual(
            f"TurboGears documentation in .txt format available at:\n{cache_path}\n",
            stdout,
        )
        self.assertIn("Warning:", stderr)
        self.assertIn("stale copy", stderr)
        self.assertEqual("old", (cache_path / "index.txt").read_text(encoding="utf-8"))

    def test_replacement_failure_keeps_existing_cache_active(self):
        cache_path = self._cache_path("development")
        cache_path.mkdir(parents=True)
        active_path = cache_path / "docs-existing"
        active_path.mkdir()
        (active_path / "index.txt").write_text("old", encoding="utf-8")
        (cache_path / "current").write_text("docs-existing", encoding="utf-8")

        def download(_url, destination):
            with zipfile.ZipFile(destination, "w") as archive:
                archive.writestr("index.txt", "new")

        real_replace = os.replace

        def fail_pointer_publish(source, destination):
            if Path(destination).name == "current":
                raise OSError("pointer publish failed")
            return real_replace(source, destination)

        with (
            patch(
                "devtools.gearbox.tgdocs.importlib.metadata.version",
                return_value="2.5.1dev1",
            ),
            patch(
                "devtools.gearbox.tgdocs.urllib.request.urlretrieve",
                side_effect=download,
            ),
            patch(
                "devtools.gearbox.tgdocs.os.replace", side_effect=fail_pointer_publish
            ),
        ):
            status, stdout, stderr = self._run_command()

        self.assertEqual(0, status)
        self.assertEqual(
            f"TurboGears documentation in .txt format available at:\n{active_path}\n",
            stdout,
        )
        self.assertIn("stale copy", stderr)
        self.assertEqual(
            "docs-existing", (cache_path / "current").read_text(encoding="utf-8")
        )
        self.assertEqual("old", (active_path / "index.txt").read_text(encoding="utf-8"))
        self.assertEqual(
            [active_path],
            [path for path in cache_path.iterdir() if path.name.startswith("docs-")],
        )
        self.assertEqual([], list(cache_path.glob(".current-*")))

    def test_cache_directory_failure_is_reported(self):
        invalid_cache_home = Path(self.temp_dir) / "not-a-directory"
        invalid_cache_home.write_text("not a directory", encoding="utf-8")
        command = TgDocsCommand(None, {})
        opts = command.get_parser("gearbox tgdocs").parse_args([])
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch(
                "devtools.gearbox.tgdocs.importlib.metadata.version",
                return_value="2.5.1",
            ),
            patch.dict(os.environ, {"XDG_CACHE_HOME": str(invalid_cache_home)}),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            with self.assertRaises(SystemExit) as failure:
                command.run(opts)

        self.assertEqual(1, failure.exception.code)
        self.assertEqual("", stdout.getvalue())
        self.assertIn("Error: unable to fetch TurboGears docs", stderr.getvalue())

    def test_failure_without_cache_is_nonzero(self):
        with (
            patch(
                "devtools.gearbox.tgdocs.importlib.metadata.version",
                return_value="2.5.1",
            ),
            patch(
                "devtools.gearbox.tgdocs.urllib.request.urlretrieve",
                side_effect=OSError("offline"),
            ),
        ):
            command = TgDocsCommand(None, {})
            opts = command.get_parser("gearbox tgdocs").parse_args([])
            stdout = io.StringIO()
            stderr = io.StringIO()
            with self.assertRaises(SystemExit) as failure:
                with patch.dict(os.environ, {"XDG_CACHE_HOME": str(self.cache_home)}):
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        command.run(opts)

        self.assertEqual(1, failure.exception.code)
        self.assertEqual("", stdout.getvalue())
        self.assertIn("Error:", stderr.getvalue())
        self.assertIn("offline", stderr.getvalue())
        self.assertEqual([], list(self._cache_path("2.5.1").glob(".2.5.1-*")))


if __name__ == "__main__":
    unittest.main()
