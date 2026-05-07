import os
import sys

import pytest
from unittest.mock import patch

from aspireupdater.launcher import (
    detect_mods_folder,
    find_aspiremc_prism_instance,
    instance_matches_version,
    instance_mods_dir,
)


class TestInstanceMatchesVersion:
    def test_matches_by_directory_name(self, tmp_path):
        idir = tmp_path / "mc-26.1.2-fabric"
        idir.mkdir()
        assert instance_matches_version(str(idir), "26.1.2") is True

    def test_matches_by_config_file(self, tmp_path):
        idir = tmp_path / "my-instance"
        idir.mkdir()
        (idir / "instance.cfg").write_text("intendedVersion=26.1.2\n")
        assert instance_matches_version(str(idir), "26.1.2") is True

    def test_no_match_dirname(self, tmp_path):
        idir = tmp_path / "other-instance"
        idir.mkdir()
        assert instance_matches_version(str(idir), "26.1.2") is False

    def test_no_match_wrong_version_in_config(self, tmp_path):
        idir = tmp_path / "my-instance"
        idir.mkdir()
        (idir / "instance.cfg").write_text("intendedVersion=1.20.1\n")
        assert instance_matches_version(str(idir), "26.1.2") is False

    def test_config_file_unreadable_falls_through(self, tmp_path):
        idir = tmp_path / "my-instance"
        idir.mkdir()
        cfg = idir / "instance.cfg"
        cfg.write_text("intendedVersion=26.1.2\n")
        # Make unreadable — skip on Windows where chmod 0 doesn't reliably block reads
        import sys
        if sys.platform != "win32":
            os.chmod(str(cfg), 0o000)
            assert instance_matches_version(str(idir), "26.1.2") is False
            os.chmod(str(cfg), 0o644)


class TestInstanceModsDir:
    def test_finds_dotminecraft(self, tmp_path):
        mc = tmp_path / ".minecraft"
        mc.mkdir()
        result = instance_mods_dir(str(tmp_path))
        assert result == str(mc / "mods")

    def test_finds_minecraft(self, tmp_path):
        mc = tmp_path / "minecraft"
        mc.mkdir()
        result = instance_mods_dir(str(tmp_path))
        assert result == str(mc / "mods")

    def test_prefers_dotminecraft_over_minecraft(self, tmp_path):
        (tmp_path / ".minecraft").mkdir()
        (tmp_path / "minecraft").mkdir()
        result = instance_mods_dir(str(tmp_path))
        assert ".minecraft" in result

    def test_defaults_to_dotminecraft_when_neither_exists(self, tmp_path):
        result = instance_mods_dir(str(tmp_path))
        assert result == str(tmp_path / ".minecraft" / "mods")


class TestDetectModsFolder:
    def test_finds_matching_instance(self, tmp_path):
        instances_dir = tmp_path / "instances"
        instances_dir.mkdir()
        idir = instances_dir / "mc-26.1.2"
        idir.mkdir()
        mc_dir = idir / ".minecraft"
        mc_dir.mkdir()

        with patch(
            "aspireupdater.launcher.get_launcher_instance_dirs",
            return_value=[("TestLauncher", str(instances_dir))],
        ):
            launcher, mods_path = detect_mods_folder("26.1.2")

        assert launcher == "TestLauncher"
        assert mods_path == str(mc_dir / "mods")

    def test_returns_none_when_no_match(self, tmp_path):
        instances_dir = tmp_path / "instances"
        instances_dir.mkdir()
        (instances_dir / "mc-1.20.1").mkdir()

        with patch(
            "aspireupdater.launcher.get_launcher_instance_dirs",
            return_value=[("TestLauncher", str(instances_dir))],
        ):
            launcher, mods_path = detect_mods_folder("26.1.2")

        assert launcher is None
        assert mods_path is None

    def test_skips_missing_instances_dir(self, tmp_path):
        with patch(
            "aspireupdater.launcher.get_launcher_instance_dirs",
            return_value=[("Ghost", str(tmp_path / "nonexistent"))],
        ):
            launcher, mods_path = detect_mods_folder("26.1.2")

        assert launcher is None

    def test_returns_first_match(self, tmp_path):
        inst_a = tmp_path / "launcher_a" / "instances"
        inst_b = tmp_path / "launcher_b" / "instances"
        inst_a.mkdir(parents=True)
        inst_b.mkdir(parents=True)

        (inst_a / "mc-26.1.2").mkdir()
        (inst_b / "mc-26.1.2").mkdir()

        with patch(
            "aspireupdater.launcher.get_launcher_instance_dirs",
            return_value=[
                ("LauncherA", str(inst_a)),
                ("LauncherB", str(inst_b)),
            ],
        ):
            launcher, _ = detect_mods_folder("26.1.2")

        assert launcher == "LauncherA"

    def test_flatpak_path_included_on_linux(self):
        from aspireupdater.launcher import get_launcher_instance_dirs
        with patch("sys.platform", "linux"):
            dirs = get_launcher_instance_dirs()
        names = [name for name, _ in dirs]
        paths = [path for _, path in dirs]
        assert "Prism Launcher (Flatpak)" in names
        flatpak_path = next(p for n, p in zip(names, paths) if n == "Prism Launcher (Flatpak)")
        assert "org.prismlauncher.PrismLauncher" in flatpak_path

    def test_flatpak_not_included_on_windows(self):
        from aspireupdater.launcher import get_launcher_instance_dirs
        with patch("sys.platform", "win32"):
            dirs = get_launcher_instance_dirs()
        names = [name for name, _ in dirs]
        assert "Prism Launcher (Flatpak)" not in names


@pytest.mark.skipif(sys.platform == "win32", reason="Unix paths only")
class TestFindAspireMCPrismInstance:
    def test_finds_native_instance(self, tmp_path):
        prism_dir = tmp_path / "native" / "PrismLauncher" / "instances"
        prism_dir.mkdir(parents=True)
        idir = prism_dir / "AspireMC"
        idir.mkdir()

        flatpak_dir = tmp_path / "flatpak_missing"

        with patch("aspireupdater.launcher.os.path.expanduser", return_value=str(tmp_path)), \
             patch("aspireupdater.launcher.os.environ.get",
                   side_effect=lambda k, d="": {
                       "XDG_DATA_HOME": str(tmp_path / "native"),
                   }.get(k, d)):
            result_idir, result_mods = find_aspiremc_prism_instance()

        assert result_idir is not None
        assert "AspireMC" in result_idir

    def test_falls_back_to_flatpak(self, tmp_path):
        flatpak_instances = (
            tmp_path / ".var" / "app" / "org.prismlauncher.PrismLauncher"
            / "data" / "PrismLauncher" / "instances"
        )
        flatpak_instances.mkdir(parents=True)
        (flatpak_instances / "AspireMC").mkdir()

        with patch("aspireupdater.launcher.os.path.expanduser", return_value=str(tmp_path)), \
             patch("aspireupdater.launcher.os.environ.get",
                   side_effect=lambda k, d="": {}.get(k, d)):
            result_idir, _ = find_aspiremc_prism_instance()

        assert result_idir is not None
        assert "AspireMC" in result_idir

    def test_returns_none_when_no_aspiremc_instance(self, tmp_path):
        prism_dir = tmp_path / "native" / "PrismLauncher" / "instances"
        prism_dir.mkdir(parents=True)
        (prism_dir / "SomeOtherPack").mkdir()

        with patch("aspireupdater.launcher.os.path.expanduser", return_value=str(tmp_path)), \
             patch("aspireupdater.launcher.os.environ.get",
                   side_effect=lambda k, d="": {
                       "XDG_DATA_HOME": str(tmp_path / "native"),
                   }.get(k, d)):
            result_idir, result_mods = find_aspiremc_prism_instance()

        assert result_idir is None
        assert result_mods is None
