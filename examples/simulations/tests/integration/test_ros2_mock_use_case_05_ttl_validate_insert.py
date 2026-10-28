import unittest

from examples.simulations.run_use_case_05_ttl_validate_insert import run_ttl_validate_insert_use_case


class FakeApiClient:
    def __init__(self) -> None:
        self.post_calls: list[tuple[str, dict[str, object]]] = []
        self.get_text_calls: list[str] = []

    def post_json(self, endpoint: str, payload: dict[str, object]) -> dict[str, object]:
        self.post_calls.append((endpoint, payload))
        if endpoint == "/ttl/validate":
            ttl_content = str(payload.get("ttl_content", ""))
            if "@prefx" in ttl_content:
                return {
                    "valid": False,
                    "syntax_ok": False,
                    "semantic_ok": False,
                    "triple_count": 0,
                    "issues": [{"severity": "error", "code": "TTL_SYNTAX_ERROR", "message": "Invalid Turtle"}],
                }
            return {
                "valid": True,
                "syntax_ok": True,
                "semantic_ok": True,
                "triple_count": 200,
                "issues": [],
            }

        if endpoint == "/ttl/delete_all":
            return {"message": "Graph cleared."}
        if endpoint == "/ttl":
            return {"message": "TTL inserted into Virtuoso", "log_id": "abc-123"}

        raise AssertionError(f"Unexpected POST endpoint: {endpoint}")

    def get_json(self, endpoint: str, *, params: dict[str, object] | None = None) -> dict[str, object]:
        raise AssertionError(f"Unexpected GET JSON endpoint: {endpoint}")

    def get_text(self, endpoint: str, *, params: dict[str, object] | None = None) -> str:
        self.get_text_calls.append(endpoint)
        if endpoint == "/events":
            return "@prefix ex: <https://example.org/> ."
        raise AssertionError(f"Unexpected GET text endpoint: {endpoint}")


class TestUseCase05TtlValidateInsert(unittest.TestCase):
    def test_validate_insert_and_export_flow(self) -> None:
        api_client = FakeApiClient()
        result = run_ttl_validate_insert_use_case(
            api_client=api_client,
            user="admin_user",
            validate_only=False,
            delete_before_insert=True,
        )

        self.assertFalse(result.invalid_validation.valid)
        self.assertTrue(result.valid_validation.valid)
        self.assertIsNotNone(result.delete_response)
        self.assertIsNotNone(result.insert_response)
        assert result.insert_response is not None
        self.assertEqual(result.insert_response["log_id"], "abc-123")
        self.assertIsNotNone(result.exported_ttl)
        self.assertGreater(len(result.ttl_text), 0)
        self.assertGreater(len(api_client.post_calls), 2)
        self.assertEqual(api_client.get_text_calls, ["/events"])

    def test_validate_only_skips_insert_and_export(self) -> None:
        api_client = FakeApiClient()
        result = run_ttl_validate_insert_use_case(
            api_client=api_client,
            user=None,
            validate_only=True,
            delete_before_insert=True,
        )

        self.assertIsNone(result.delete_response)
        self.assertIsNone(result.insert_response)
        self.assertIsNone(result.exported_ttl)
        endpoints = [endpoint for endpoint, _ in api_client.post_calls]
        self.assertEqual(endpoints, ["/ttl/validate", "/ttl/validate"])
        self.assertEqual(api_client.get_text_calls, [])


if __name__ == "__main__":
    unittest.main()
