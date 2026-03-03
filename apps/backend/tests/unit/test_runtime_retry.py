import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, call, patch

from services.runtime import _retry_connect


class TestRuntimeRetry(unittest.TestCase):
    def test_retry_connect_retries_with_backoff_and_eventually_succeeds(self) -> None:
        attempts = {"count": 0}

        def connect_fn() -> None:
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise ConnectionError("temporary failure")

        settings = SimpleNamespace(max_startup_retries=5, max_backoff_seconds=3)
        logger = Mock()

        with patch("services.runtime.asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
            asyncio.run(_retry_connect("Virtuoso", connect_fn, settings, logger))

        self.assertEqual(attempts["count"], 3)
        sleep_mock.assert_has_awaits([call(1), call(2)])
        self.assertEqual(logger.warning.call_count, 2)
        logger.info.assert_called_once_with("%s connected.", "Virtuoso")

    def test_retry_connect_raises_last_error_after_max_attempts(self) -> None:
        def connect_fn() -> None:
            raise OSError("still down")

        settings = SimpleNamespace(max_startup_retries=3, max_backoff_seconds=4)
        logger = Mock()

        with patch("services.runtime.asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
            with self.assertRaisesRegex(OSError, "still down"):
                asyncio.run(_retry_connect("Virtuoso", connect_fn, settings, logger))

        sleep_mock.assert_has_awaits([call(1), call(2)])
        self.assertEqual(logger.warning.call_count, 3)
        logger.info.assert_not_called()


if __name__ == "__main__":
    unittest.main()
