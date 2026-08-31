import importlib.metadata
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
import zipfile

from gearbox.command import Command


class TgDocsCommand(Command):
    """Fetch the plain-text TurboGears documentation for the installed version."""

    def get_description(self):
        return "Fetch plain-text TurboGears documentation for the installed version"

    def get_parser(self, prog_name):
        return super(TgDocsCommand, self).get_parser(prog_name)

    def take_action(self, opts):
        del opts
        version = _documentation_version()
        cache_directory = _cache_directory(version)
        cached_path = _active_cache_path(cache_directory)

        if version != "development" and cached_path is not None:
            print(
                f"TurboGears documentation in .txt format available at:\n{cached_path}"
            )
            return

        # For development, check if docs have changed before redownloading
        if version == "development" and cached_path is not None:
            if _docs_unchanged(cache_directory):
                print(
                    f"TurboGears documentation in .txt format available at:\n{cached_path}"
                )
                return

        try:
            cache_directory.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix=f".{version}-", dir=cache_directory
            ) as temporary_dir:
                archive_path = Path(temporary_dir) / "tg2docs.txt.zip"
                urllib.request.urlretrieve(_archive_url(version), archive_path)
                extracted_path = Path(temporary_dir) / "docs"
                extracted_path.mkdir()
                extraction_root = extracted_path.resolve()
                with zipfile.ZipFile(archive_path) as archive:
                    for member in archive.infolist():
                        member_name = member.filename.replace("\\", "/")
                        destination = (extraction_root / member_name).resolve()
                        if (
                            destination != extraction_root
                            and extraction_root not in destination.parents
                        ):
                            raise ValueError(
                                f"unsafe ZIP member path: {member.filename!r}"
                            )
                        if stat.S_ISLNK(member.external_attr >> 16):
                            raise ValueError(
                                f"unsafe ZIP symbolic link: {member.filename!r}"
                            )
                    archive.extractall(extracted_path)
                cached_path = _replace_cache(extracted_path, cache_directory)
                _update_etag(cache_directory)
        except Exception as error:
            cached_path = _active_cache_path(cache_directory)
            if cached_path is not None:
                print(
                    f"Warning: unable to refresh TurboGears docs ({error}); "
                    f"using stale copy at {cached_path}",
                    file=sys.stderr,
                )
                print(
                    f"TurboGears documentation in .txt format available at:\n{cached_path}"
                )
                return
            print(f"Error: unable to fetch TurboGears docs: {error}", file=sys.stderr)
            raise SystemExit(1)

        print(f"TurboGears documentation in .txt format available at:\n{cached_path}")


def _documentation_version():
    version = importlib.metadata.version("TurboGears2")
    return "development" if "dev" in version.lower() else version


def _cache_directory(version):
    cache_root = os.environ.get("XDG_CACHE_HOME")
    if cache_root:
        cache_root = Path(cache_root)
    else:
        cache_root = Path.home() / ".cache"
    return cache_root / "turbogears" / "tg2docs" / version


def _active_cache_path(cache_directory):
    if not cache_directory.is_dir():
        return None

    try:
        cache_root = cache_directory.resolve()
        entries = list(cache_directory.iterdir())
    except OSError:
        return None

    pointer_path = cache_directory / "current"
    if not pointer_path.is_symlink() and pointer_path.is_file():
        try:
            generation_name = pointer_path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            generation_name = ""
        if (
            generation_name.startswith("docs-")
            and len(generation_name) > len("docs-")
            and Path(generation_name).name == generation_name
        ):
            generation_path = cache_directory / generation_name
            resolved_path = generation_path.resolve()
            if (
                generation_path.is_dir()
                and not generation_path.is_symlink()
                and cache_root in resolved_path.parents
            ):
                return generation_path

    generations = []
    for path in entries:
        if (
            not path.name.startswith("docs-")
            or len(path.name) == len("docs-")
            or not path.is_dir()
            or path.is_symlink()
        ):
            continue
        try:
            resolved_path = path.resolve()
            if cache_root not in resolved_path.parents:
                continue
            generations.append((path.stat().st_mtime_ns, path))
        except OSError:
            continue
    if generations:
        return max(generations, key=lambda item: item[0])[1]

    if any(
        path.name not in ("current", "current.etag")
        and not path.name.startswith(".")
        and not path.name.startswith("docs-")
        for path in entries
    ):
        return cache_directory
    return None


def _archive_url(version):
    return f"https://turbogears.github.io/tg2docs/{version}/tg2docs.txt.zip"


def _etag_path(cache_directory):
    return cache_directory / "current.etag"


def _docs_unchanged(cache_directory):
    """Check if development docs have not changed by comparing ETags."""
    stored_etag = _read_etag(cache_directory)
    if stored_etag is None:
        return False
    current_etag = _fetch_etag(cache_directory)
    if current_etag is None:
        return False
    return stored_etag == current_etag


def _read_etag(cache_directory):
    """Read stored ETag from metadata file."""
    etag_path = _etag_path(cache_directory)
    if not etag_path.is_file():
        return None
    try:
        return etag_path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None


def _fetch_etag(cache_directory):
    """Fetch current ETag from the server using HEAD request."""
    version = _documentation_version()
    url = _archive_url(version)
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.headers.get("ETag")
    except urllib.error.HTTPError as error:
        error.close()
        return None
    except Exception:
        return None


def _update_etag(cache_directory):
    """Update stored ETag after successful download."""
    current_etag = _fetch_etag(cache_directory)
    if current_etag is None:
        return
    etag_path = _etag_path(cache_directory)
    try:
        etag_path.write_text(current_etag, encoding="utf-8")
    except OSError:
        pass


def _replace_cache(staged_path, cache_directory):
    generation_name = f"docs-{uuid.uuid4().hex}"
    generation_path = cache_directory / generation_name
    pointer_path = cache_directory / "current"
    temporary_pointer = cache_directory / f".current-{uuid.uuid4().hex}"

    try:
        os.replace(staged_path, generation_path)
        temporary_pointer.write_text(generation_name, encoding="utf-8")
        # Publish the completed generation without changing the active pointer first.
        os.replace(temporary_pointer, pointer_path)
    except Exception:
        temporary_pointer.unlink(missing_ok=True)
        if generation_path.exists():
            shutil.rmtree(generation_path)
        raise

    return generation_path
