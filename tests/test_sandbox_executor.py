import unittest

from src.function_app.services.sandbox_executor import execute_script_in_sandbox


class TestSandboxExecutor(unittest.TestCase):
    def test_execute_script_succeeds(self) -> None:
        script = """
def transform(context):
    return {"echo": context.get("value", "")}
"""
        result = execute_script_in_sandbox(script, {"value": "ok"}, timeout_seconds=10)

        self.assertTrue(result["passed"])
        self.assertEqual(result["status"], "Succeeded")
        self.assertEqual(result["result"]["echo"], "ok")

    def test_execute_script_returns_failure_on_exception(self) -> None:
        script = """
def transform(context):
    raise RuntimeError("boom")
"""
        result = execute_script_in_sandbox(script, {}, timeout_seconds=10)

        self.assertFalse(result["passed"])
        self.assertEqual(result["status"], "Failed")
        self.assertIn("RuntimeError", result["error"])

    def test_execute_script_times_out(self) -> None:
        script = """
import time

def transform(context):
    time.sleep(2)
    return {}
"""
        result = execute_script_in_sandbox(script, {}, timeout_seconds=1)

        self.assertFalse(result["passed"])
        self.assertEqual(result["status"], "TimedOut")
        self.assertTrue(result["timed_out"])


if __name__ == "__main__":
    unittest.main()
