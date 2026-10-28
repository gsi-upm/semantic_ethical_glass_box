import unittest
from unittest.mock import patch

from starlette.requests import Request

from api.request_context import (
    RequestActor,
    build_request_actor,
    request_actor_context,
    resolve_actor,
    resolve_client_ip,
)


def _build_request(*, headers: dict[str, str] | None = None, client_host: str | None = "127.0.0.1") -> Request:
    raw_headers = [(key.lower().encode("latin-1"), value.encode("latin-1")) for key, value in (headers or {}).items()]
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": raw_headers,
        "client": (client_host, 4321) if client_host is not None else None,
        "server": ("testserver", 80),
        "state": {},
    }
    return Request(scope)


class TestRequestContext(unittest.TestCase):
    def test_resolve_client_ip_prefers_first_forwarded_hop(self) -> None:
        request = _build_request(headers={"x-forwarded-for": "10.0.0.2, 192.168.1.10"}, client_host="127.0.0.1")
        self.assertEqual(resolve_client_ip(request), "10.0.0.2")

    def test_resolve_client_ip_falls_back_to_client_host(self) -> None:
        request = _build_request(headers={}, client_host="192.168.1.5")
        self.assertEqual(resolve_client_ip(request), "192.168.1.5")

    def test_resolve_client_ip_returns_dash_when_no_source_is_available(self) -> None:
        request = _build_request(headers={}, client_host=None)
        self.assertEqual(resolve_client_ip(request), "-")

    def test_resolve_actor_uses_first_non_blank_candidate(self) -> None:
        self.assertEqual(resolve_actor(None, "   ", "  admin_user  ", "logger"), "admin_user")

    def test_build_request_actor_combines_actor_and_origin_ip(self) -> None:
        request = _build_request(headers={"x-forwarded-for": "10.10.10.1"}, client_host="127.0.0.1")
        actor = build_request_actor(request, None, "  robot_logger ")

        self.assertEqual(actor.actor, "robot_logger")
        self.assertEqual(actor.origin_ip, "10.10.10.1")

    def test_request_actor_context_sets_state_and_resets_log_context(self) -> None:
        request = _build_request()
        request_actor = RequestActor(actor="admin", origin_ip="10.0.0.3")
        tokens = {"actor": object()}

        with (
            patch("api.request_context.bind_log_context", return_value=tokens) as bind_mock,
            patch("api.request_context.reset_log_context") as reset_mock,
        ):
            with request_actor_context(request, request_actor) as yielded:
                self.assertEqual(yielded, request_actor)
                self.assertEqual(request.state.actor, "admin")

            bind_mock.assert_called_once_with(actor="admin", origin_ip="10.0.0.3")
            reset_mock.assert_called_once_with(tokens)

    def test_request_actor_context_resets_context_on_exceptions(self) -> None:
        request = _build_request()
        request_actor = RequestActor(actor="admin", origin_ip="10.0.0.3")
        tokens = {"actor": object()}

        with (
            patch("api.request_context.bind_log_context", return_value=tokens),
            patch("api.request_context.reset_log_context") as reset_mock,
        ):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                with request_actor_context(request, request_actor):
                    raise RuntimeError("boom")

            reset_mock.assert_called_once_with(tokens)


if __name__ == "__main__":
    unittest.main()
