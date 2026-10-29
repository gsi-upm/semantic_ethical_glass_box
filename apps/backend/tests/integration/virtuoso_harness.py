"""Isolated Virtuoso instance for opt-in integration tests.

Every instance gets its own container, its own throwaway volume, its own DBA
password and a host port chosen by the Docker daemon (loopback only). Nothing
shared is touched: no fixed names, no fixed ports, no ``prune``.

Tests that need a real triple store are opt-in: set ``SEGB_INTEGRATION=1``.
"""

from __future__ import annotations

import os
import secrets
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable

VIRTUOSO_IMAGE = "openlink/virtuoso-opensource-7:7.2.16"
CONTAINER_PORT = 8890
NAME_PREFIX = "segb-it-"
LABEL_KEY = "segb.integration-test"

DockerRunner = Callable[[list[str]], subprocess.CompletedProcess]


def integration_enabled() -> bool:
    """True only when the user explicitly opted in with ``SEGB_INTEGRATION=1``."""
    return os.environ.get("SEGB_INTEGRATION") == "1"


def _docker(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], check=True, capture_output=True, text=True)


def _wait_until_ready(endpoint: str, timeout_s: float = 180.0) -> None:
    """Poll the public SPARQL endpoint until Virtuoso answers a trivial query."""
    url = endpoint.replace("/sparql-auth", "/sparql") + "?query=ASK%20%7B%7D"
    deadline = time.monotonic() + timeout_s
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, OSError) as exc:
            last_error = exc
        time.sleep(2)
    raise TimeoutError(f"Virtuoso did not become ready at {url}: {last_error}")


class VirtuosoTestInstance:
    """A disposable Virtuoso, usable as a context manager."""

    def __init__(
        self,
        *,
        docker: DockerRunner = _docker,
        wait_ready: Callable[[str], None] = _wait_until_ready,
        image: str = VIRTUOSO_IMAGE,
    ) -> None:
        self.run_id = uuid.uuid4().hex[:12]
        self.container_name = f"{NAME_PREFIX}{self.run_id}"
        self.volume_name = f"{NAME_PREFIX}{self.run_id}"
        self.password = secrets.token_hex(8)
        self.image = image
        self._docker = docker
        self._wait_ready = wait_ready
        self._volume_created = False
        self._container_attempted = False
        self._host_port: str | None = None

    @property
    def _label(self) -> str:
        return f"{LABEL_KEY}={self.run_id}"

    @property
    def endpoint(self) -> str:
        if self._host_port is None:
            raise RuntimeError("Virtuoso test instance is not started.")
        return f"http://127.0.0.1:{self._host_port}/sparql-auth"

    def environ(self) -> dict[str, str]:
        """Environment variables that point the backend at this instance."""
        return {
            "VIRTUOSO_ENDPOINT": self.endpoint,
            "VIRTUOSO_USER": "dba",
            "VIRTUOSO_PASSWORD": self.password,
        }

    def start(self) -> "VirtuosoTestInstance":
        try:
            self._docker(["volume", "create", "--label", self._label, self.volume_name])
            self._volume_created = True
            self._container_attempted = True
            self._docker(
                [
                    "run",
                    "-d",
                    "--name",
                    self.container_name,
                    "--label",
                    self._label,
                    "-e",
                    f"DBA_PASSWORD={self.password}",
                    "-v",
                    f"{self.volume_name}:/database",
                    "-p",
                    f"127.0.0.1::{CONTAINER_PORT}",
                    self.image,
                ]
            )
            mapping = self._docker(["port", self.container_name, f"{CONTAINER_PORT}/tcp"]).stdout
            self._host_port = mapping.splitlines()[0].rsplit(":", 1)[1].strip()
            self._wait_ready(self.endpoint)
        except BaseException:
            self.stop()
            raise
        return self

    def stop(self) -> None:
        """Remove this instance's container and volume, and nothing else."""
        if self._container_attempted:
            self._best_effort(["rm", "-f", "-v", self.container_name])
            self._container_attempted = False
        if self._volume_created:
            self._best_effort(["volume", "rm", self.volume_name])
            self._volume_created = False
        self._host_port = None

    def _best_effort(self, args: list[str]) -> None:
        try:
            self._docker(args)
        except subprocess.CalledProcessError:
            pass

    def __enter__(self) -> "VirtuosoTestInstance":
        return self.start()

    def __exit__(self, *exc_info: object) -> None:
        self.stop()
