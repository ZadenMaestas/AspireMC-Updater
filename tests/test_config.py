import json
import os

import pytest

import aspireupdater.config as cfg


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """Redirect all config I/O to a temporary directory."""
    monkeypatch.setattr(cfg, "get_config_dir", lambda: str(tmp_path))
    return tmp_path


class TestLoadSaveFolder:
    def test_save_and_load(self, config_dir):
        cfg.save_folder("/path/to/mods")
        assert cfg.load_saved_folder() == "/path/to/mods"

    def test_load_returns_empty_when_missing(self, config_dir):
        assert cfg.load_saved_folder() == ""

    def test_overwrite(self, config_dir):
        cfg.save_folder("/first/path")
        cfg.save_folder("/second/path")
        assert cfg.load_saved_folder() == "/second/path"

    def test_strips_whitespace(self, config_dir):
        # Manually write a file with trailing newline
        (config_dir / "mods_folder.txt").write_text("  /my/mods  \n")
        assert cfg.load_saved_folder() == "/my/mods"


class TestInstalledModpackVersion:
    def test_save_and_load(self, config_dir):
        cfg.save_installed_modpack_version("2.5.0")
        assert cfg.load_installed_modpack_version() == "2.5.0"

    def test_load_returns_none_when_missing(self, config_dir):
        assert cfg.load_installed_modpack_version() is None

    def test_empty_file_returns_none(self, config_dir):
        (config_dir / "installed_modpack_version.txt").write_text("")
        assert cfg.load_installed_modpack_version() is None


class TestAdminConfig:
    def test_save_and_load(self, config_dir):
        data = {"password_hash": "abc", "password_salt": "def", "r2_bucket_name": "bucket"}
        cfg.save_admin_config(data)
        loaded = cfg.load_admin_config()
        assert loaded == data

    def test_load_returns_none_when_missing(self, config_dir):
        assert cfg.load_admin_config() is None

    def test_nested_data_round_trips(self, config_dir):
        data = {"last_upload_manifest": [{"name": "mod.jar", "size": 12345}]}
        cfg.save_admin_config(data)
        loaded = cfg.load_admin_config()
        assert loaded["last_upload_manifest"][0]["size"] == 12345
