import json
import tempfile
import unittest
from pathlib import Path

from src.function_app.services.pipeline_runner import run_pipeline


class TestPipelineRunner(unittest.TestCase):
    def test_run_pipeline_draft_writes_planner_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_pipeline(
                input_workbook="examples/inputs/Input 8.xlsx",
                output_root=temp_dir,
                run_mode="draft",
            )

            self.assertEqual(result["run_mode"], "draft")
            self.assertEqual(result["validation_status"], "Draft")
            self.assertTrue(Path(result["csv"]).exists())
            self.assertTrue(Path(result["planner_system_prompt"]).exists())
            self.assertTrue(Path(result["planner_user_prompt"]).exists())
            self.assertTrue(Path(result["planner_response"]).exists())
            self.assertTrue(Path(result["script_policy_report"]).exists())
            self.assertTrue(Path(result["sandbox_execution_report"]).exists())
            self.assertTrue(Path(result["execution_result"]).exists())

            sandbox_payload = json.loads(
                Path(result["sandbox_execution_report"]).read_text(encoding="utf-8")
            )
            self.assertEqual(sandbox_payload["status"], "Skipped")

            execution_payload = json.loads(
                Path(result["execution_result"]).read_text(encoding="utf-8")
            )
            self.assertEqual(execution_payload["status"], "Succeeded")
            self.assertTrue(execution_payload["run_id"])

    def test_run_pipeline_execute_with_validation_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_pipeline(
                input_workbook="examples/inputs/Input 8.xlsx",
                output_root=temp_dir,
                run_mode="execute_with_validation",
            )

            self.assertEqual(result["run_mode"], "execute_with_validation")
            self.assertTrue(Path(result["csv"]).exists())
            self.assertTrue(Path(result["xlsx"]).exists())
            self.assertTrue(Path(result["validation_report"]).exists())
            self.assertTrue(Path(result["planner_response"]).exists())
            self.assertTrue(Path(result["script_policy_report"]).exists())
            self.assertTrue(Path(result["sandbox_execution_report"]).exists())
            self.assertTrue(Path(result["execution_result"]).exists())

            sandbox_payload = json.loads(
                Path(result["sandbox_execution_report"]).read_text(encoding="utf-8")
            )
            self.assertEqual(sandbox_payload["status"], "Succeeded")
            self.assertGreater(result["row_count"], 0)

            validation_payload = json.loads(Path(result["validation_report"]).read_text(encoding="utf-8"))
            self.assertIn("status", validation_payload)
            self.assertIn("issue_counts", validation_payload)

            execution_payload = json.loads(
                Path(result["execution_result"]).read_text(encoding="utf-8")
            )
            self.assertEqual(execution_payload["status"], "Succeeded")
            self.assertTrue(execution_payload["artifacts"])


if __name__ == "__main__":
    unittest.main()
