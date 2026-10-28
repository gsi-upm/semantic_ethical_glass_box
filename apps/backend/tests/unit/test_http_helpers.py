import unittest
from unittest.mock import Mock, patch

from examples.simulations.http_helpers import ApiConfig, _headers, get_json, get_text, post_json


class TestHttpHelpers(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ApiConfig(
            base_url="https://segb.example.org/",
            token="token-123",
            timeout_seconds=7.5,
            verify_tls=False,
        )

    def test_headers_include_authorization_when_token_is_present(self) -> None:
        headers = _headers("token-123")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["Authorization"], "Bearer token-123")

    @patch("examples.simulations.http_helpers.requests.post")
    def test_post_json_returns_dict_body(self, post_mock: Mock) -> None:
        response = Mock()
        response.status_code = 200
        response.text = '{"ok": true}'
        response.content = b'{"ok": true}'
        response.json.return_value = {"ok": True}
        post_mock.return_value = response

        result = post_json(self.config, "/ttl/validate", {"ttl_content": "@prefix ex: <https://example.org/> ."})

        self.assertEqual(result, {"ok": True})
        post_mock.assert_called_once_with(
            "https://segb.example.org/ttl/validate",
            json={"ttl_content": "@prefix ex: <https://example.org/> ."},
            headers={"Content-Type": "application/json", "Authorization": "Bearer token-123"},
            timeout=7.5,
            verify=False,
        )

    @patch("examples.simulations.http_helpers.requests.post")
    def test_post_json_raises_runtime_error_for_http_failure(self, post_mock: Mock) -> None:
        response = Mock()
        response.status_code = 500
        response.text = "internal error"
        response.content = b"internal error"
        post_mock.return_value = response

        with self.assertRaisesRegex(RuntimeError, "HTTP 500"):
            post_json(self.config, "/ttl/validate", {"ttl_content": "x"})

    @patch("examples.simulations.http_helpers.requests.post")
    def test_post_json_raises_when_json_body_is_not_an_object(self, post_mock: Mock) -> None:
        response = Mock()
        response.status_code = 200
        response.text = '["invalid"]'
        response.content = b'["invalid"]'
        response.json.return_value = ["invalid"]
        post_mock.return_value = response

        with self.assertRaisesRegex(RuntimeError, "not an object"):
            post_json(self.config, "/ttl/validate", {"ttl_content": "x"})

    @patch("examples.simulations.http_helpers.requests.get")
    def test_get_json_returns_status_code_when_body_is_empty(self, get_mock: Mock) -> None:
        response = Mock()
        response.status_code = 204
        response.text = ""
        response.content = b""
        get_mock.return_value = response

        result = get_json(self.config, "/shared-context/stats")

        self.assertEqual(result, {"status_code": 204})
        get_mock.assert_called_once_with(
            "https://segb.example.org/shared-context/stats",
            params=None,
            headers={"Content-Type": "application/json", "Authorization": "Bearer token-123"},
            timeout=7.5,
            verify=False,
        )

    @patch("examples.simulations.http_helpers.requests.get")
    def test_get_text_returns_response_text(self, get_mock: Mock) -> None:
        response = Mock()
        response.status_code = 200
        response.text = "@prefix ex: <https://example.org/> ."
        response.content = b"ttl"
        get_mock.return_value = response

        result = get_text(self.config, "/events")

        self.assertEqual(result, "@prefix ex: <https://example.org/> .")
        get_mock.assert_called_once_with(
            "https://segb.example.org/events",
            params=None,
            headers={"Content-Type": "application/json", "Authorization": "Bearer token-123"},
            timeout=7.5,
            verify=False,
        )


if __name__ == "__main__":
    unittest.main()
