import asyncio
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from api.request_context import RequestActor
from api.routers import graph_ops, health_auth, shared_context_ops, system_ops
from api.schemas import TTLContent
from core.security import User
from services.system_log_service import InvalidLogLevelError
from utils.shared_context import SharedContextResolveRequest


class TestApiRouters(unittest.TestCase):
    def setUp(self) -> None:
        self.request = SimpleNamespace(state=SimpleNamespace())
        self.request_actor = RequestActor(actor="admin", origin_ip="127.0.0.1")
        self.admin_user = User(username="admin", roles=["admin"])
        self.logger_user = User(username="logger", roles=["logger"])

    def test_execute_query_returns_http_422_when_service_rejects_query(self) -> None:
        service = Mock()
        service.execute_query.side_effect = PermissionError("Update queries are not allowed.")

        with (
            patch("api.routers.graph_ops.require_roles"),
            patch("api.routers.graph_ops.get_log_service", return_value=service),
            patch("api.routers.graph_ops.build_request_actor", return_value=self.request_actor),
            patch(
                "api.routers.graph_ops.request_actor_context",
                side_effect=lambda request, request_actor: nullcontext(request_actor),
            ),
        ):
            with self.assertRaises(HTTPException) as context:
                asyncio.run(
                    graph_ops.execute_query(
                        request=self.request,  # type: ignore[arg-type]
                        query="INSERT DATA { <a> <b> <c> . }",
                        _=None,
                        user=self.admin_user,
                    )
                )

        self.assertEqual(context.exception.status_code, 422)
        self.assertIn("Update queries are not allowed", context.exception.detail)
        service.execute_query.assert_called_once_with(
            query="INSERT DATA { <a> <b> <c> . }",
            actor="admin",
            origin_ip="127.0.0.1",
        )

    def test_insert_ttl_rejects_when_transaction_lock_is_already_taken(self) -> None:
        busy_lock = Mock()
        busy_lock.locked.return_value = True
        payload = TTLContent(ttl_content="@prefix ex: <https://example.org/> .")

        with (
            patch.object(graph_ops, "transaction_lock", busy_lock),
            patch("api.routers.graph_ops.require_roles"),
        ):
            with self.assertRaises(HTTPException) as context:
                asyncio.run(
                    graph_ops.insert_ttl(
                        request=self.request,  # type: ignore[arg-type]
                        data=payload,
                        _=None,
                        user=self.logger_user,
                    )
                )

        self.assertEqual(context.exception.status_code, 429)
        self.assertIn("Another transaction is in progress", context.exception.detail)

    def test_shared_context_resolve_maps_value_error_to_http_422(self) -> None:
        service = Mock()
        service.resolve.side_effect = ValueError("event_kind must be provided")
        data = SharedContextResolveRequest(
            event_kind="",
            observed_at=datetime(2026, 2, 10, 12, 0, 0, tzinfo=timezone.utc),
        )

        with (
            patch("api.routers.shared_context_ops.require_roles"),
            patch("api.routers.shared_context_ops.get_shared_context_service", return_value=service),
            patch("api.routers.shared_context_ops.build_request_actor", return_value=self.request_actor),
            patch(
                "api.routers.shared_context_ops.request_actor_context",
                side_effect=lambda request, request_actor: nullcontext(request_actor),
            ),
        ):
            with self.assertRaises(HTTPException) as context:
                asyncio.run(
                    shared_context_ops.resolve_shared_context(
                        request=self.request,  # type: ignore[arg-type]
                        data=data,
                        user=self.admin_user,
                    )
                )

        self.assertEqual(context.exception.status_code, 422)
        self.assertIn("event_kind must be provided", context.exception.detail)
        service.resolve.assert_called_once_with(data)

    def test_system_logs_maps_invalid_level_to_http_422(self) -> None:
        system_service = Mock()
        system_service.read_server_logs.side_effect = InvalidLogLevelError("Invalid level 'TRACE'.")

        with (
            patch("api.routers.system_ops.require_roles"),
            patch("api.routers.system_ops.resolve_log_file_path", return_value=Path("/tmp/segb.log")),
            patch("api.routers.system_ops.SystemLogService", return_value=system_service),
            patch("api.routers.system_ops.build_request_actor", return_value=self.request_actor),
            patch(
                "api.routers.system_ops.request_actor_context",
                side_effect=lambda request, request_actor: nullcontext(request_actor),
            ),
        ):
            with self.assertRaises(HTTPException) as context:
                asyncio.run(
                    system_ops.get_server_logs(
                        request=self.request,  # type: ignore[arg-type]
                        user=self.admin_user,
                        limit=100,
                        level="TRACE",
                        contains=None,
                    )
                )

        self.assertEqual(context.exception.status_code, 422)
        self.assertIn("Invalid level", context.exception.detail)
        system_service.read_server_logs.assert_called_once_with(limit=100, level="TRACE", contains=None)

    def test_health_ready_reflects_runtime_virtuoso_flag(self) -> None:
        with patch("api.routers.health_auth.get_services", return_value=SimpleNamespace(virtuoso_ok=False)):
            result = health_auth.ready(self.request)  # type: ignore[arg-type]

        self.assertEqual(result, {"ready": False, "virtuoso": False})

    def test_auth_mode_reports_if_secret_key_is_configured(self) -> None:
        with patch("api.routers.health_auth.SECRET_KEY", "x" * 32):
            enabled = health_auth.auth_mode()
        with patch("api.routers.health_auth.SECRET_KEY", None):
            disabled = health_auth.auth_mode()

        self.assertEqual(enabled, {"auth_enabled": True})
        self.assertEqual(disabled, {"auth_enabled": False})


if __name__ == "__main__":
    unittest.main()
