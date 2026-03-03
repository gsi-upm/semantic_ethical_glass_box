from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from fastapi import HTTPException

from api.deps import get_log_service, get_services, get_shared_context_service, require_virtuoso_ready
from services.log_service import LogService
from services.shared_context_service import SharedContextService


def _build_request_with_services(services: object) -> SimpleNamespace:
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(services=services)))


class TestApiDeps(unittest.TestCase):
    def test_get_services_returns_runtime_services_from_request_state(self) -> None:
        services = SimpleNamespace()
        request = _build_request_with_services(services)

        resolved = get_services(request)  # type: ignore[arg-type]
        self.assertIs(resolved, services)

    def test_get_log_service_wraps_virtuoso_port(self) -> None:
        virtuoso = Mock()
        services = SimpleNamespace(virtuoso=virtuoso)
        request = _build_request_with_services(services)

        service = get_log_service(request)  # type: ignore[arg-type]

        self.assertIsInstance(service, LogService)
        self.assertIs(service.virtuoso, virtuoso)

    def test_get_shared_context_service_wraps_resolver_port(self) -> None:
        shared_context = Mock()
        services = SimpleNamespace(shared_context=shared_context)
        request = _build_request_with_services(services)

        service = get_shared_context_service(request)  # type: ignore[arg-type]

        self.assertIsInstance(service, SharedContextService)
        self.assertIs(service.resolver, shared_context)

    def test_require_virtuoso_ready_allows_request_when_ready(self) -> None:
        services = SimpleNamespace(virtuoso_ok=True)
        request = _build_request_with_services(services)
        require_virtuoso_ready(request)  # type: ignore[arg-type]

    def test_require_virtuoso_ready_rejects_when_not_ready(self) -> None:
        services = SimpleNamespace(virtuoso_ok=False)
        request = _build_request_with_services(services)

        with self.assertRaises(HTTPException) as context:
            require_virtuoso_ready(request)  # type: ignore[arg-type]

        self.assertEqual(context.exception.status_code, 503)
        self.assertEqual(context.exception.detail, "Virtuoso is unavailable")


if __name__ == "__main__":
    unittest.main()
