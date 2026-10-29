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
from pathlib import Path

VIRTUOSO_IMAGE = "openlink/virtuoso-opensource-7:7.2.16"
CONTAINER_PORT = 8890
NAME_PREFIX = "segb-it-"
LABEL_KEY = "segb.integration-test"
# The same script the compose files run before the backend starts.
PROVISION_SCRIPT = Path(__file__).resolve().parents[2] / "virtuoso" / "provision-query-reader.sh"
PROVISION_TARGET = "/tmp/provision-query-reader.sh"
POLICY_MANIFEST = PROVISION_SCRIPT.parent / "reader-sql-policy.manifest"
POLICY_TARGET = "/tmp/reader-sql-policy.manifest"

DockerRunner = Callable[[list[str]], subprocess.CompletedProcess]


def _isql_errors(result: subprocess.CompletedProcess) -> list[str]:
    """isql can report SQL errors on either stream while still exiting successfully."""
    return [
        line for stream in (result.stdout or "", result.stderr or "")
        for line in stream.splitlines() if "*** Error" in line
    ]


class ProvisioningError(subprocess.CalledProcessError):
    """The provisioning script refused or failed; the message carries what it printed on stderr."""

    def __str__(self) -> str:
        return f"Provisioning exited with {self.returncode}: {(self.stderr or '').strip()}"


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

    def provision_query_reader(
        self,
        *,
        user: str = "segb_reader",
        password: str | None = None,
        events_graph: str = "http://segb/events",
        audit_graph: str = "http://segb/audit",
    ) -> dict[str, str]:
        """Runs the repository's provisioning script inside this instance; returns the backend's reader settings.

        Raises ``subprocess.CalledProcessError`` when the script refuses or fails.
        """
        if self._host_port is None:
            raise RuntimeError("Virtuoso test instance is not started.")
        password = secrets.token_hex(8) if password is None else password
        self._docker(["cp", str(PROVISION_SCRIPT), f"{self.container_name}:{PROVISION_TARGET}"])
        self._docker(["cp", str(POLICY_MANIFEST), f"{self.container_name}:{POLICY_TARGET}"])
        env = {
            "VIRTUOSO_ISQL_ADDRESS": "localhost:1111",
            "VIRTUOSO_ADMIN_USER": "dba",
            "VIRTUOSO_ADMIN_PASSWORD": self.password,
            "VIRTUOSO_READER_USER": user,
            "VIRTUOSO_READER_PASSWORD": password,
            "VIRTUOSO_GRAPH_URI": events_graph,
            "VIRTUOSO_AUDIT_GRAPH_URI": audit_graph,
            "VIRTUOSO_READER_POLICY_FILE": POLICY_TARGET,
        }
        flags = [arg for key, value in env.items() for arg in ("-e", f"{key}={value}")]
        try:
            self._docker(["exec", *flags, self.container_name, "sh", PROVISION_TARGET])
        except subprocess.CalledProcessError as error:
            raise ProvisioningError(error.returncode, error.cmd, error.output, error.stderr) from None
        return {"VIRTUOSO_READER_USER": user, "VIRTUOSO_READER_PASSWORD": password}

    def sql(self, statement: str) -> str:
        """Runs one SQL statement as DBA through isql; raises when Virtuoso reports an error (isql exits 0 anyway)."""
        if self._host_port is None:
            raise RuntimeError("Virtuoso test instance is not started.")
        result = self._docker(
            ["exec", self.container_name, "isql", "1111", "dba", self.password, f"exec={statement}"]
        )
        errors = _isql_errors(result)
        if errors:
            raise RuntimeError("; ".join(errors))
        return result.stdout

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
