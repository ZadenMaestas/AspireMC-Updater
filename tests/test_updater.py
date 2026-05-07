import os
import zipfile
from unittest.mock import MagicMock, patch

import pytest

from aspireupdater.updater import download_modpack, smart_update, standard_update


def _make_zip(path, files):
    """Create a zip at path containing {filename: content_str} entries."""
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)


class TestSmartUpdate:
    def test_extracts_new_files(self, tmp_path):
        mods_dir = tmp_path / "mods"
        mods_dir.mkdir()
        zip_path = str(tmp_path / "mods.zip")
        _make_zip(zip_path, {"new_mod.jar": "content"})

        updated, total = smart_update(zip_path, str(mods_dir))

        assert total == 1
        assert updated == 1
        assert (mods_dir / "new_mod.jar").exists()

    def test_skips_unchanged_files(self, tmp_path):
        mods_dir = tmp_path / "mods"
        mods_dir.mkdir()
        (mods_dir / "existing.jar").write_bytes(b"content")

        zip_path = str(tmp_path / "mods.zip")
        _make_zip(zip_path, {"existing.jar": "content"})  # same size

        updated, total = smart_update(zip_path, str(mods_dir))

        assert total == 1
        assert updated == 0

    def test_updates_size_changed_files(self, tmp_path):
        mods_dir = tmp_path / "mods"
        mods_dir.mkdir()
        (mods_dir / "mod.jar").write_bytes(b"old")

        zip_path = str(tmp_path / "mods.zip")
        _make_zip(zip_path, {"mod.jar": "new longer content here"})

        updated, total = smart_update(zip_path, str(mods_dir))

        assert updated == 1

    def test_mixed_new_and_unchanged(self, tmp_path):
        mods_dir = tmp_path / "mods"
        mods_dir.mkdir()
        (mods_dir / "same.jar").write_bytes(b"same")

        zip_path = str(tmp_path / "mods.zip")
        _make_zip(zip_path, {"same.jar": "same", "new.jar": "brand new"})

        updated, total = smart_update(zip_path, str(mods_dir))

        assert total == 2
        assert updated == 1
        assert (mods_dir / "new.jar").exists()

    def test_calls_on_progress(self, tmp_path):
        mods_dir = tmp_path / "mods"
        mods_dir.mkdir()
        zip_path = str(tmp_path / "mods.zip")
        _make_zip(zip_path, {"a.jar": "a", "b.jar": "b", "c.jar": "c"})

        calls = []
        smart_update(zip_path, str(mods_dir), on_progress=lambda p, l: calls.append(p))

        assert len(calls) == 3
        assert calls[-1] == 100


class TestStandardUpdate:
    def test_removes_existing_files(self, tmp_path):
        mods_dir = tmp_path / "mods"
        mods_dir.mkdir()
        (mods_dir / "old.jar").write_bytes(b"old")

        zip_path = str(tmp_path / "mods.zip")
        _make_zip(zip_path, {"new.jar": "new"})

        deleted, extracted = standard_update(zip_path, str(mods_dir))

        assert deleted == 1
        assert not (mods_dir / "old.jar").exists()

    def test_extracts_all_files(self, tmp_path):
        mods_dir = tmp_path / "mods"
        mods_dir.mkdir()
        zip_path = str(tmp_path / "mods.zip")
        _make_zip(zip_path, {"a.jar": "a", "b.jar": "b", "c.jar": "c"})

        deleted, extracted = standard_update(zip_path, str(mods_dir))

        assert extracted == 3
        assert (mods_dir / "a.jar").exists()
        assert (mods_dir / "b.jar").exists()
        assert (mods_dir / "c.jar").exists()

    def test_empty_mods_folder(self, tmp_path):
        mods_dir = tmp_path / "mods"
        mods_dir.mkdir()
        zip_path = str(tmp_path / "mods.zip")
        _make_zip(zip_path, {"mod.jar": "content"})

        deleted, extracted = standard_update(zip_path, str(mods_dir))

        assert deleted == 0
        assert extracted == 1

    def test_calls_on_log_for_delete_failure(self, tmp_path):
        mods_dir = tmp_path / "mods"
        mods_dir.mkdir()
        locked = mods_dir / "locked.jar"
        locked.write_bytes(b"data")

        zip_path = str(tmp_path / "mods.zip")
        _make_zip(zip_path, {"new.jar": "content"})

        log_messages = []

        # Simulate an OSError on removal
        original_remove = os.remove

        def fake_remove(path):
            if "locked.jar" in path:
                raise OSError("permission denied")
            original_remove(path)

        with patch("aspireupdater.updater.os.remove", side_effect=fake_remove):
            standard_update(zip_path, str(mods_dir), on_log=lambda m: log_messages.append(m))

        assert any("locked.jar" in m for m in log_messages)

    def test_calls_on_progress(self, tmp_path):
        mods_dir = tmp_path / "mods"
        mods_dir.mkdir()
        zip_path = str(tmp_path / "mods.zip")
        _make_zip(zip_path, {"a.jar": "a", "b.jar": "b"})

        calls = []
        standard_update(zip_path, str(mods_dir), on_progress=lambda p, l: calls.append(p))

        assert len(calls) >= 2
        assert calls[-1] == 100


class TestDownloadModpack:
    def _mock_response(self, content: bytes):
        mock = MagicMock()
        mock.__enter__ = lambda s: s
        mock.__exit__ = MagicMock(return_value=False)
        mock.headers = {"content-length": str(len(content))}
        mock.iter_content = lambda chunk_size: [content]
        mock.raise_for_status = MagicMock()
        return mock

    def test_writes_content_to_file(self, tmp_path):
        dest = str(tmp_path / "mods.zip")
        content = b"fake zip bytes"

        with patch("aspireupdater.updater.requests.get", return_value=self._mock_response(content)):
            download_modpack("http://example.com/mods.zip", dest)

        assert os.path.exists(dest)
        assert open(dest, "rb").read() == content

    def test_calls_on_progress(self, tmp_path):
        dest = str(tmp_path / "mods.zip")
        content = b"some data"

        calls = []
        with patch("aspireupdater.updater.requests.get", return_value=self._mock_response(content)):
            download_modpack("http://example.com/mods.zip", dest,
                             on_progress=lambda p, l: calls.append(p))

        assert len(calls) > 0
        assert calls[-1] == 100

    def test_no_content_length_uses_fifty_percent(self, tmp_path):
        dest = str(tmp_path / "mods.zip")
        mock = self._mock_response(b"data")
        mock.headers = {}  # no content-length

        calls = []
        with patch("aspireupdater.updater.requests.get", return_value=mock):
            download_modpack("http://example.com/mods.zip", dest,
                             on_progress=lambda p, l: calls.append(p))

        assert all(p == 50 for p in calls)
