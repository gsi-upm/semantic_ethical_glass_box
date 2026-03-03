"""Small HTTP helpers for simulation scripts that talk to the SEGB backend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import requests


@dataclass(slots=True)
class ApiConfig:
    """Runtime settings to call SEGB HTTP endpoints."""

    base_url: str
    token: str | None = None
    timeout_seconds: float = 20.0
    verify_tls: bool = True


class SimulationApiClient(Protocol):
    """Minimal HTTP contract used by simulation use cases."""

    def post_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def get_json(self, endpoint: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        ...

    def get_text(self, endpoint: str, *, params: dict[str, Any] | None = None) -> str:
        ...


@dataclass(slots=True)
class RequestsSimulationApiClient:
    """Requests-based implementation of `SimulationApiClient`."""

    config: ApiConfig

    def post_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        return post_json(self.config, endpoint, payload)

    def get_json(self, endpoint: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return get_json(self.config, endpoint, params=params)

    def get_text(self, endpoint: str, *, params: dict[str, Any] | None = None) -> str:
        return get_text(self.config, endpoint, params=params)


def _headers(token: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _raise_for_status(response: requests.Response, *, endpoint: str) -> None:
    if response.status_code >= 400:
        raise RuntimeError(
            f"SEGB API call failed at {endpoint} with HTTP {response.status_code}: {response.text}"
        )


def post_json(config: ApiConfig, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POSTs JSON and returns parsed JSON body."""
    url = f"{config.base_url.rstrip('/')}{endpoint}"
    response = requests.post(
        url,
        json=payload,
        headers=_headers(config.token),
        timeout=config.timeout_seconds,
        verify=config.verify_tls,
    )
    _raise_for_status(response, endpoint=endpoint)
    if not response.content:
        return {"status_code": response.status_code}
    try:
        body = response.json()
    except ValueError as error:
        raise RuntimeError(f"Endpoint {endpoint} returned non-JSON payload: {response.text}") from error
    if not isinstance(body, dict):
        raise RuntimeError(f"Endpoint {endpoint} returned JSON that is not an object.")
    return body


def get_json(config: ApiConfig, endpoint: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """GETs JSON and returns parsed object body."""
    url = f"{config.base_url.rstrip('/')}{endpoint}"
    response = requests.get(
        url,
        params=params,
        headers=_headers(config.token),
        timeout=config.timeout_seconds,
        verify=config.verify_tls,
    )
    _raise_for_status(response, endpoint=endpoint)
    if not response.content:
        return {"status_code": response.status_code}
    try:
        body = response.json()
    except ValueError as error:
        raise RuntimeError(f"Endpoint {endpoint} returned non-JSON payload: {response.text}") from error
    if not isinstance(body, dict):
        raise RuntimeError(f"Endpoint {endpoint} returned JSON that is not an object.")
    return body


def get_text(config: ApiConfig, endpoint: str, *, params: dict[str, Any] | None = None) -> str:
    """GETs plain text content."""
    url = f"{config.base_url.rstrip('/')}{endpoint}"
    response = requests.get(
        url,
        params=params,
        headers=_headers(config.token),
        timeout=config.timeout_seconds,
        verify=config.verify_tls,
    )
    _raise_for_status(response, endpoint=endpoint)
    return response.text
