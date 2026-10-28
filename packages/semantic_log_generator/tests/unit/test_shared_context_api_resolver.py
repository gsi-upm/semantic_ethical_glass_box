from datetime import datetime, timezone
import unittest
from unittest.mock import Mock, patch

import requests

from semantic_log_generator.shared_context import HTTPSharedContextResolver, build_http_shared_context_resolver_from_env
from semantic_log_generator.types import SharedEventRequest


class TestHTTPSharedContextResolver(unittest.TestCase):
    def test_returns_shared_context_uri_on_success(self) -> None:
        session = Mock(spec=requests.Session)
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"shared_context_uri": "https://example.org/shared-events/ctx_1"}
        session.post.return_value = response

        resolver = HTTPSharedContextResolver(
            base_url="https://segb.example.org",
            token="abc123",
            session=session,
            raise_on_error=True,
        )
        resolved = resolver(
            SharedEventRequest(
                event_kind="human_utterance",
                observed_at=datetime(2026, 2, 10, 12, 0, 0, tzinfo=timezone.utc),
                subject="https://example.org/human/maria",
                text="hello",
                modality="speech",
            )
        )

        self.assertEqual(resolved, "https://example.org/shared-events/ctx_1")
        session.post.assert_called_once()

    def test_returns_none_on_failure_when_not_raising(self) -> None:
        session = Mock(spec=requests.Session)
        session.post.side_effect = requests.RequestException("boom")

        resolver = HTTPSharedContextResolver(
            base_url="https://segb.example.org",
            session=session,
            raise_on_error=False,
        )
        with patch("semantic_log_generator.shared_context.logger.warning") as warning_mock:
            resolved = resolver(
                SharedEventRequest(
                    event_kind="human_utterance",
                    observed_at=datetime(2026, 2, 10, 12, 0, 0, tzinfo=timezone.utc),
                    subject="https://example.org/human/maria",
                    text="hello",
                    modality="speech",
                )
            )

        self.assertIsNone(resolved)
        warning_mock.assert_called_once()

    def test_env_helper_returns_none_without_base_url(self) -> None:
        resolver = build_http_shared_context_resolver_from_env(env={})
        self.assertIsNone(resolver)

    def test_env_helper_builds_resolver(self) -> None:
        resolver = build_http_shared_context_resolver_from_env(
            env={
                "SEGB_API_URL": "https://segb.example.org",
                "SEGB_API_TOKEN": "token-123",
                "SEGB_SHARED_CONTEXT_TIMEOUT_SECONDS": "7.5",
                "SEGB_SHARED_CONTEXT_VERIFY_TLS": "false",
                "SEGB_SHARED_CONTEXT_RAISE_ON_ERROR": "true",
            }
        )
        self.assertIsNotNone(resolver)
        assert resolver is not None
        self.assertEqual(resolver.base_url, "https://segb.example.org")
        self.assertEqual(resolver.token, "token-123")
        self.assertEqual(resolver.timeout_seconds, 7.5)
        self.assertFalse(resolver.verify_tls)
        self.assertTrue(resolver.raise_on_error)

    def test_env_helper_uses_default_timeout_when_timeout_env_is_invalid(self) -> None:
        resolver = build_http_shared_context_resolver_from_env(
            env={
                "SEGB_API_URL": "https://segb.example.org",
                "SEGB_SHARED_CONTEXT_TIMEOUT_SECONDS": "abc",
            }
        )
        self.assertIsNotNone(resolver)
        assert resolver is not None
        self.assertEqual(resolver.timeout_seconds, 5.0)

    def test_env_helper_uses_default_timeout_when_timeout_env_is_not_positive(self) -> None:
        resolver = build_http_shared_context_resolver_from_env(
            env={
                "SEGB_API_URL": "https://segb.example.org",
                "SEGB_SHARED_CONTEXT_TIMEOUT_SECONDS": "0",
            }
        )
        self.assertIsNotNone(resolver)
        assert resolver is not None
        self.assertEqual(resolver.timeout_seconds, 5.0)


if __name__ == "__main__":
    unittest.main()
