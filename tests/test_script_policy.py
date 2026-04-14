import unittest

from src.function_app.services.script_policy import evaluate_script_policy


class TestScriptPolicy(unittest.TestCase):
    def test_valid_script_passes_policy(self) -> None:
        script = """
def helper(x):
    return x

def transform(context):
    return {\"dataframe\": None}
"""
        result = evaluate_script_policy(script)
        self.assertTrue(result["passed"])
        self.assertEqual(result["error_count"], 0)

    def test_banned_import_fails_policy(self) -> None:
        script = """
import os

def transform(context):
    return {}
"""
        result = evaluate_script_policy(script)
        self.assertFalse(result["passed"])
        self.assertTrue(any(item["code"] == "banned_import" for item in result["findings"]))

    def test_banned_call_fails_policy(self) -> None:
        script = """
def transform(context):
    eval(\"1+1\")
    return {}
"""
        result = evaluate_script_policy(script)
        self.assertFalse(result["passed"])
        self.assertTrue(any(item["code"] == "banned_call" for item in result["findings"]))

    def test_missing_transform_fails_policy(self) -> None:
        script = """
def not_transform(context):
    return {}
"""
        result = evaluate_script_policy(script)
        self.assertFalse(result["passed"])
        self.assertTrue(any(item["code"] == "missing_transform_entrypoint" for item in result["findings"]))


if __name__ == "__main__":
    unittest.main()
