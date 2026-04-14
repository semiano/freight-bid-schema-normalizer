from __future__ import annotations

import json
import re
from typing import Any

from ..models.contracts import AgentResponse, CanonicalSchema, WorkbookProfile
from .foundry_agent_client import FoundryAgentClient
from .prompt_renderer import PromptRenderer


class TransformationPlanningService:
    def __init__(
        self,
        client: FoundryAgentClient | None = None,
        prompt_renderer: PromptRenderer | None = None,
    ) -> None:
        self.client = client or FoundryAgentClient(mode="mock")
        self.prompt_renderer = prompt_renderer or PromptRenderer()

    def build_plan(
        self,
        canonical_schema: CanonicalSchema,
        workbook_profile: WorkbookProfile,
        run_mode: str = "draft",
        reference_data: dict[str, Any] | None = None,
        constraints: dict[str, Any] | None = None,
    ) -> AgentResponse:
        system_prompt = self.prompt_renderer.load_prompt("transform_planner_system.txt")

        user_prompt = self.prompt_renderer.render(
            "transform_planner_user.txt.j2",
            {
                "run_mode": run_mode,
                "canonical_schema_json": canonical_schema.model_dump_json(indent=2),
                "workbook_profile_json": workbook_profile.model_dump_json(indent=2),
                "reference_data_json": json.dumps(reference_data or {}, indent=2),
                "constraints_json": json.dumps(constraints or {}, indent=2),
            },
        )

        raw_response = self.client.plan(system_prompt=system_prompt, user_prompt=user_prompt)
        raw_response = self._normalize_plan_payload(raw_response)
        return AgentResponse(**raw_response)

    def _normalize_plan_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        script = normalized.get("python_script")
        if isinstance(script, str):
            normalized["python_script"] = self._normalize_python_script(script)
        return normalized

    def _normalize_python_script(self, script: str) -> str:
        normalized = script.strip()

        fenced = re.match(r"^```(?:python)?\s*(.*?)\s*```$", normalized, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            normalized = fenced.group(1)

        if "\\n" in normalized and "\n" not in normalized:
            normalized = normalized.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")

        return normalized
