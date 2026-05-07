import sys
from unittest.mock import patch

import pytest

from aspireupdater.version import get_release_asset_name, next_version, parse_version


class TestParseVersion:
    def test_normal(self):
        assert parse_version("1.2.3") == (1, 2, 3)

    def test_v_prefix(self):
        assert parse_version("v1.2.3") == (1, 2, 3)

    def test_dash_suffix_stripped(self):
        assert parse_version("1.2.3-beta") == (1, 2, 3)

    def test_two_parts(self):
        assert parse_version("1.6") == (1, 6)

    def test_invalid_returns_zeros(self):
        assert parse_version("abc") == (0, 0, 0)

    def test_int_input(self):
        assert parse_version(1) == (1,)

    def test_version_ordering(self):
        assert parse_version("1.6.0") > parse_version("1.5.9")
        assert parse_version("2.0.0") > parse_version("1.99.99")
        assert parse_version("1.0.0") == parse_version("1.0.0")


class TestNextVersion:
    def test_increments_patch(self):
        assert next_version("1.2.3") == "1.2.4"

    def test_increments_minor(self):
        assert next_version("1.2") == "1.3"

    def test_increments_single(self):
        assert next_version("1") == "2"

    def test_zero_increments(self):
        assert next_version("0.0.0") == "0.0.1"

    def test_preserves_leading_parts(self):
        result = next_version("2.5.10")
        assert result == "2.5.11"


class TestGetReleaseAssetName:
    def test_windows(self):
        with patch("sys.platform", "win32"):
            assert get_release_asset_name() == "AspireMC-Updater.exe"

    def test_darwin(self):
        with patch("sys.platform", "darwin"):
            assert get_release_asset_name() == "AspireMC-Updater-macos"

    def test_linux(self):
        with patch("sys.platform", "linux"):
            assert get_release_asset_name() == "AspireMC-Updater-linux"
