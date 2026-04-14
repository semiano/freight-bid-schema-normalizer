import unittest

from pydantic import ValidationError

from src.function_app.models.contracts import WorkbookProfile
from src.function_app.services.foundry_agent_client import FoundryAgentClient
from src.function_app.services.planning_service import TransformationPlanningService
from src.function_app.services.template_loader import load_canonical_schema
from src.function_app.services.workbook_profiler import profile_workbook


class BadMockFoundryClient(FoundryAgentClient):
    def __init__(self) -> None:
        super().__init__(mode="mock")

    def plan(self, system_prompt: str, user_prompt: str) -> dict:
        return {
            "relevant_sheets": ["SINGLE FTL LIVE LOAD TRAILERS"],
            "ignored_sheets": ["REQUIREMENTS"],
            "mapping_plan": {},
            "constants": {},
            "enrichments": {},
            "assumptions": [],
            "confidence_scores": {},
            "tests": [],
        }


class EscapedScriptMockFoundryClient(FoundryAgentClient):
    def __init__(self) -> None:
        super().__init__(mode="mock")

    def plan(self, system_prompt: str, user_prompt: str) -> dict:
        return {
            "relevant_sheets": ["Sheet1"],
            "ignored_sheets": [],
            "mapping_plan": {},
            "constants": {},
            "enrichments": {},
            "assumptions": [],
            "confidence_scores": {"overall": 0.5},
            "python_script": "def transform(context):\\n    return {'records': []}",
            "tests": [],
        }


class TestPlanningService(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = load_canonical_schema(
            "src/function_app/templates/canonical_schema.freight_bid_v1.json"
        )
        cls.profile: WorkbookProfile = profile_workbook("examples/inputs/Input 8.xlsx", sample_size=2)

    def test_build_plan_returns_valid_agent_response_with_default_mock(self) -> None:
        service = TransformationPlanningService()

        plan = service.build_plan(self.schema, self.profile, run_mode="draft")

        self.assertGreaterEqual(len(plan.relevant_sheets), 1)
        self.assertIsInstance(plan.mapping_plan, dict)
        self.assertIsInstance(plan.python_script, str)

    def test_build_plan_raises_on_invalid_agent_payload(self) -> None:
        service = TransformationPlanningService(client=BadMockFoundryClient())

        with self.assertRaises(ValidationError):
            service.build_plan(self.schema, self.profile, run_mode="draft")

    def test_build_plan_normalizes_escaped_python_script(self) -> None:
        service = TransformationPlanningService(client=EscapedScriptMockFoundryClient())

        plan = service.build_plan(self.schema, self.profile, run_mode="draft")

        self.assertIn("\n", plan.python_script)
        self.assertNotIn("\\n", plan.python_script)


if __name__ == "__main__":
    unittest.main()
