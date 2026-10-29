"""Opt-in tests against a real Virtuoso. Run with SEGB_INTEGRATION=1."""

from __future__ import annotations

import subprocess
import unittest
from concurrent.futures import ThreadPoolExecutor

import requests
from requests.auth import HTTPDigestAuth

import virtuoso_harness as harness

GRAPH = "http://amor-segb/it-isolation"


def _sparql(instance: harness.VirtuosoTestInstance, query: str) -> requests.Response:
    response = requests.post(
        instance.endpoint,
        data={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        auth=HTTPDigestAuth("dba", instance.password),
        timeout=30,
    )
    response.raise_for_status()
    return response


def _docker_names(*args: str) -> set[str]:
    out = subprocess.run(["docker", *args], check=True, capture_output=True, text=True).stdout
    return {line for line in out.splitlines() if line}


@unittest.skipUnless(harness.integration_enabled(), "set SEGB_INTEGRATION=1 to run against a real Virtuoso")
class VirtuosoIsolationTests(unittest.TestCase):
    def test_parallel_instances_are_isolated_and_leave_no_trace(self) -> None:
        containers_before = _docker_names("ps", "-a", "--format", "{{.Names}}")
        volumes_before = _docker_names("volume", "ls", "-q")

        a, b = harness.VirtuosoTestInstance(), harness.VirtuosoTestInstance()
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(lambda inst: inst.start(), (a, b)))

            self.assertNotEqual(a.endpoint, b.endpoint)

            _sparql(a, f"INSERT DATA {{ GRAPH <{GRAPH}> {{ <urn:it:a> <urn:it:p> 'only-in-a' }} }}")
            in_a = _sparql(a, f"SELECT ?o FROM <{GRAPH}> WHERE {{ ?s ?p ?o }}").json()
            in_b = _sparql(b, f"SELECT ?o FROM <{GRAPH}> WHERE {{ ?s ?p ?o }}").json()
            self.assertEqual([r["o"]["value"] for r in in_a["results"]["bindings"]], ["only-in-a"])
            self.assertEqual(in_b["results"]["bindings"], [])
        finally:
            a.stop()
            b.stop()

        self.assertEqual(_docker_names("ps", "-a", "--format", "{{.Names}}"), containers_before)
        self.assertEqual(_docker_names("volume", "ls", "-q"), volumes_before)


if __name__ == "__main__":
    unittest.main()
