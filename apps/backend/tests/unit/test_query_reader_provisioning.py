"""Exercise the provisioning shell's fail-closed handling of isql's unusual exit status."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "apps/backend/virtuoso/provision-query-reader.sh"


class TestProvisioningIsqlFailures(unittest.TestCase):
    def _run(
        self,
        output: str,
        policy: str = "PUBLIC|32|DB.DBA.X|_all|-",
        *,
        manifest_name: str = "manifest",
        failing_step: str = "",
        record_store: bool = False,
    ) -> subprocess.CompletedProcess:
        # Keep subprocess fixtures within the worktree; the real database tests use the actual isql instead.
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            isql = Path(directory) / "isql"
            isql.write_text(
                '#!/bin/sh\n'
                'case "${4-}" in\n'
                '  "exec=select 1") exit 0 ;;\n'
                '  exec=DB.DBA.SEGB_QUERY_READER_SQL_POLICY_ROWS*)\n'
                '    [ "$ISQL_TEST_FAIL_STEP" = POLICY_ROWS ] && { echo "SQL> *** Error 42000: rows failed"; exit 0; }\n'
                '    printf "%s\\nDIGEST|0123456789abcdef0123456789abcdef\\n" "$ISQL_TEST_POLICY"; exit 0 ;;\n'
                '  exec=DB.DBA.SEGB_QUERY_READER_SQL_POLICY_STORE*)\n'
                '    printf "%s\\n" "$4" > "$ISQL_TEST_STORE_LOG"\n'
                '    [ "$ISQL_TEST_FAIL_STEP" = POLICY_STORE ] && echo "SQL> *** Error 42000: store failed"\n'
                '    exit 0 ;;\n'
                'esac\n'
                'cat >/dev/null\n'
                'printf "%s\\n" "$ISQL_TEST_OUTPUT"\n',
                encoding="utf-8",
            )
            isql.chmod(0o700)
            manifest = Path(directory) / "manifest"
            manifest.write_text("# comment\nPUBLIC|32|DB.DBA.X|_all|-\n", encoding="utf-8")
            store_log = Path(directory) / "store.log"
            env = {
                **os.environ,
                "PATH": f"{directory}:{os.environ.get('PATH', '')}",
                "VIRTUOSO_ADMIN_USER": "dba",
                "VIRTUOSO_ADMIN_PASSWORD": "admin-pw",
                "VIRTUOSO_READER_USER": "segb_reader",
                "VIRTUOSO_READER_PASSWORD": "secret-reader-pw",
                "VIRTUOSO_GRAPH_URI": "http://segb/events",
                "VIRTUOSO_AUDIT_GRAPH_URI": "http://segb/audit",
                "ISQL_TEST_OUTPUT": output,
                "ISQL_TEST_POLICY": policy,
                "ISQL_TEST_FAIL_STEP": failing_step,
                "ISQL_TEST_STORE_LOG": str(store_log),
                "VIRTUOSO_READER_POLICY_FILE": str(Path(directory) / manifest_name),
            }
            result = subprocess.run(["sh", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=10)
            self.store_call = store_log.read_text(encoding="utf-8") if store_log.exists() else ""
            return result

    def test_isql_error_with_exit_zero_still_refuses_provisioning_without_echoing_password(self) -> None:
        result = self._run(
            "SQL> provisioning call with 'secret-reader-pw'\n"
            "*** Error SEGB5: the query reader has direct SQL grants\n"
            "SEGB_QUERY_READER_PROVISIONED\n"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("direct SQL grants", result.stderr)
        self.assertNotIn("secret-reader-pw", result.stdout + result.stderr)

    def test_no_confirmation_is_a_failure_even_when_isql_exits_zero(self) -> None:
        result = self._run("")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("did not confirm provisioning", result.stderr)

    def test_a_confirmation_without_errors_succeeds(self) -> None:
        result = self._run("SQL> select confirmation\nSEGB_QUERY_READER_PROVISIONED\n1 Rows.\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("read-only", result.stdout)

    def test_an_effective_privilege_outside_the_manifest_refuses_provisioning(self) -> None:
        result = self._run(
            "SEGB_QUERY_READER_PROVISIONED\n",
            policy="PUBLIC|32|DB.DBA.X|_all|-\nPUBLIC|32|DB.DBA.WRITE_IT|_all|abc",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("differ from the reviewed manifest", result.stderr)
        self.assertIn("DB.DBA.WRITE_IT", result.stderr)

    def test_a_missing_manifest_refuses_provisioning(self) -> None:
        result = self._run("SEGB_QUERY_READER_PROVISIONED\n", manifest_name="missing")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cannot read the reviewed SQL privilege manifest", result.stderr)

    def test_prompt_prefixed_isql_errors_are_failures_in_every_step(self) -> None:
        result = self._run("SQL> *** Error SEGB5: refused\nSEGB_QUERY_READER_PROVISIONED\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SEGB5", result.stderr)
        for step in ("POLICY_ROWS", "POLICY_STORE"):
            with self.subTest(step=step):
                result = self._run("SEGB_QUERY_READER_PROVISIONED\n", failing_step=step)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("*** Error", result.stderr)
                self.assertNotIn("segb_reader is read-only", result.stdout)

    def test_the_digest_stored_is_the_one_reported_with_the_compared_listing(self) -> None:
        result = self._run("SEGB_QUERY_READER_PROVISIONED\n", record_store=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("0123456789abcdef0123456789abcdef", self.store_call)

    def test_passwords_with_line_breaks_are_refused_not_altered(self) -> None:
        for password in ("secret\n", "se\ncret", "secret\r"):
            with self.subTest(password=repr(password)):
                with tempfile.TemporaryDirectory(dir=ROOT) as directory:
                    env = {
                        **os.environ, "VIRTUOSO_ADMIN_PASSWORD": "admin-pw", "VIRTUOSO_READER_PASSWORD": password,
                        "PATH": f"{directory}:{os.environ.get('PATH', '')}",
                    }
                    result = subprocess.run(["sh", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("line breaks", result.stderr)


if __name__ == "__main__":
    unittest.main()
