"""Offline tests for the isolated Virtuoso harness (no Docker needed)."""

from __future__ import annotations

import os
import subprocess
import unittest
from unittest import mock

import virtuoso_harness as harness


class FakeDocker:
    """Records docker invocations and answers like a minimal daemon."""

    def __init__(self, host_port: str = "49321") -> None:
        self.calls: list[list[str]] = []
        self.host_port = host_port

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess:
        self.calls.append(list(args))
        stdout = ""
        if args[:1] == ["port"]:
            stdout = f"127.0.0.1:{self.host_port}\n"
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

    def commands(self, verb: str) -> list[list[str]]:
        return [c for c in self.calls if c[: len(verb.split())] == verb.split()]


def _instance(docker: FakeDocker, **kwargs) -> harness.VirtuosoTestInstance:
    return harness.VirtuosoTestInstance(docker=docker, wait_ready=lambda endpoint: None, **kwargs)


class HarnessNamingTests(unittest.TestCase):
    def test_two_instances_never_share_names(self) -> None:
        a = _instance(FakeDocker())
        b = _instance(FakeDocker())
        self.assertNotEqual(a.container_name, b.container_name)
        self.assertNotEqual(a.volume_name, b.volume_name)
        self.assertNotEqual(a.password, b.password)

    def test_names_are_prefixed_so_they_cannot_collide_with_deployments(self) -> None:
        inst = _instance(FakeDocker())
        for name in (inst.container_name, inst.volume_name):
            self.assertTrue(name.startswith("segb-it-"), name)
        self.assertNotIn(inst.container_name, {"segb-virtuoso", "segb-db-test"})
        self.assertNotIn(inst.volume_name, {"segb-db-test", "virtuoso_data"})


class HarnessStartTests(unittest.TestCase):
    def test_start_creates_own_volume_and_binds_a_random_loopback_port(self) -> None:
        docker = FakeDocker()
        inst = _instance(docker)
        inst.start()

        (volume_create,) = docker.commands("volume create")
        self.assertIn(inst.volume_name, volume_create)

        (run,) = docker.commands("run")
        self.assertIn(inst.container_name, run)
        self.assertIn(f"{inst.volume_name}:/database", run)
        # Port 0 on loopback: the daemon picks a free host port, nothing fixed like 5000/8890.
        self.assertIn("127.0.0.1::8890", run)
        self.assertFalse(any(arg.startswith(("8890:", "1111:", "5000:")) for arg in run))
        self.assertIn(f"DBA_PASSWORD={inst.password}", run)

    def test_endpoint_uses_the_port_the_daemon_assigned(self) -> None:
        inst = _instance(FakeDocker(host_port="50123"))
        inst.start()
        self.assertEqual(inst.endpoint, "http://127.0.0.1:50123/sparql-auth")

    def test_start_applies_a_label_to_container_and_volume(self) -> None:
        docker = FakeDocker()
        inst = _instance(docker)
        inst.start()
        label = f"segb.integration-test={inst.run_id}"
        self.assertIn(label, docker.commands("run")[0])
        self.assertIn(label, docker.commands("volume create")[0])

    def test_start_failure_still_cleans_up_what_it_created(self) -> None:
        docker = FakeDocker()

        def failing(args: list[str]) -> subprocess.CompletedProcess:
            if args[:1] == ["run"]:
                raise subprocess.CalledProcessError(125, args, stderr="boom")
            return docker(args)

        inst = harness.VirtuosoTestInstance(docker=failing, wait_ready=lambda e: None)
        with self.assertRaises(subprocess.CalledProcessError):
            inst.start()
        self.assertTrue(docker.commands("volume rm"))


class HarnessStopTests(unittest.TestCase):
    def test_stop_removes_only_its_own_container_and_volume(self) -> None:
        docker = FakeDocker()
        inst = _instance(docker)
        inst.start()
        docker.calls.clear()
        inst.stop()

        removed = {arg for call in docker.calls for arg in call}
        self.assertIn(inst.container_name, removed)
        self.assertIn(inst.volume_name, removed)
        # Never anything global.
        for call in docker.calls:
            self.assertNotIn("prune", call)
            self.assertNotIn("-a", call)
        # The container is removed with its anonymous volumes, then the named one.
        self.assertEqual(docker.commands("rm")[0][:3], ["rm", "-f", "-v"])

    def test_stop_is_idempotent_and_safe_before_start(self) -> None:
        docker = FakeDocker()
        inst = _instance(docker)
        inst.stop()
        inst.stop()
        self.assertEqual(docker.calls, [])

    def test_context_manager_stops_on_error(self) -> None:
        docker = FakeDocker()
        with self.assertRaises(RuntimeError):
            with _instance(docker):
                raise RuntimeError("test failed")
        self.assertTrue(docker.commands("rm"))
        self.assertTrue(docker.commands("volume rm"))


class HarnessEnvironmentTests(unittest.TestCase):
    def test_environ_points_the_backend_at_the_instance(self) -> None:
        inst = _instance(FakeDocker(host_port="50999"))
        inst.start()
        env = inst.environ()
        self.assertEqual(env["VIRTUOSO_ENDPOINT"], "http://127.0.0.1:50999/sparql-auth")
        self.assertEqual(env["VIRTUOSO_PASSWORD"], inst.password)
        self.assertEqual(env["VIRTUOSO_USER"], "dba")

    def test_environ_before_start_fails_loudly(self) -> None:
        with self.assertRaises(RuntimeError):
            _instance(FakeDocker()).environ()


class OptInTests(unittest.TestCase):
    def test_disabled_by_default(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(harness.integration_enabled())

    def test_enabled_by_env_var(self) -> None:
        with mock.patch.dict(os.environ, {"SEGB_INTEGRATION": "1"}, clear=True):
            self.assertTrue(harness.integration_enabled())

    def test_other_values_do_not_enable_it(self) -> None:
        for value in ("", "0", "false", "no"):
            with mock.patch.dict(os.environ, {"SEGB_INTEGRATION": value}, clear=True):
                self.assertFalse(harness.integration_enabled(), value)


if __name__ == "__main__":
    unittest.main()
