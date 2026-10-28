import os
import unittest
from unittest.mock import patch

from core.settings import load_settings


class TestSettingsApiFilePaths(unittest.TestCase):
    def setUp(self) -> None:
        self._keys = (
            "API_INFO_FILE_PATH",
            "API_DESCRIPTION_FILE_PATH",
            "DESCRIPTION_FILE_PATH",
        )
        self._backup = {key: os.environ.get(key) for key in self._keys}
        for key in self._keys:
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        for key in self._keys:
            os.environ.pop(key, None)
        for key, value in self._backup.items():
            if value is not None:
                os.environ[key] = value

    def test_prefers_new_api_file_env_vars(self) -> None:
        with patch.dict(
            os.environ,
            {
                "API_INFO_FILE_PATH": "/tmp/custom_api_info.json",
                "API_DESCRIPTION_FILE_PATH": "/tmp/custom_api_description.md",
                "DESCRIPTION_FILE_PATH": "/tmp/legacy_value_should_not_win.json",
            },
            clear=False,
        ):
            settings = load_settings()

        self.assertEqual(settings.api_info_file, "/tmp/custom_api_info.json")
        self.assertEqual(settings.api_description_file, "/tmp/custom_api_description.md")

    def test_ignores_legacy_description_file_path_for_api_info(self) -> None:
        with patch.dict(
            os.environ,
            {
                "DESCRIPTION_FILE_PATH": "/tmp/legacy_api_info.json",
            },
            clear=False,
        ):
            settings = load_settings()

        self.assertNotEqual(settings.api_info_file, "/tmp/legacy_api_info.json")
        self.assertTrue(settings.api_info_file.endswith("api_info.json"))

    def test_uses_default_paths_when_no_env_overrides(self) -> None:
        settings = load_settings()
        self.assertTrue(settings.api_info_file.endswith("api_info.json"))
        self.assertTrue(settings.api_description_file.endswith("api_description.md"))


if __name__ == "__main__":
    unittest.main()
