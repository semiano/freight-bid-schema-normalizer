from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..models.contracts import ExecutionResult
from .artifact_store import (
    LocalArtifactStore,
    create_blob_artifact_store_from_env,
    mirror_local_artifacts_to_blob,
)
from .foundry_agent_client import FoundryAgentClient
from .output_writer import normalize_records_to_canonical, write_canonical_csv, write_canonical_xlsx
from .planning_service import TransformationPlanningService
from .sandbox_executor import execute_script_in_sandbox
from .script_policy import evaluate_script_policy
from .template_loader import load_canonical_schema
from .validation_service import validate_canonical_records
from .workbook_profiler import profile_workbook


def _extract_records_from_sandbox_result(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]

    if isinstance(result, dict):
        for key in ("records", "rows", "data"):
            payload = result.get(key)
            if isinstance(payload, list):
                return [item for item in payload if isinstance(item, dict)]

        dataframe_payload = result.get("dataframe")
        if isinstance(dataframe_payload, list):
            return [item for item in dataframe_payload if isinstance(item, dict)]

    return []


def run_pipeline(
    input_workbook: str,
    output_root: str,
    run_mode: str = "execute_with_validation",
    planner_mode: str | None = None,
) -> dict[str, Any]:
    input_workbook_path = str(Path(input_workbook).resolve())
    schema = load_canonical_schema("src/function_app/templates/canonical_schema.freight_bid_v1.json")
    profile = profile_workbook(input_workbook_path)
    selected_planner_mode = (planner_mode or os.getenv("PLANNER_MODE", "mock")).strip().lower()
    if selected_planner_mode not in {"mock", "live"}:
        selected_planner_mode = "mock"

    planning_service = TransformationPlanningService(
        client=FoundryAgentClient(mode=selected_planner_mode)
    )

    run_id = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    run_dir = Path(output_root) / f"pipeline_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    artifact_store = LocalArtifactStore(str(run_dir))
    blob_artifact_store = create_blob_artifact_store_from_env(run_id)

    csv_path = str(run_dir / "canonical_output.csv")
    xlsx_path = str(run_dir / "canonical_output.xlsx")

    system_prompt = planning_service.prompt_renderer.load_prompt("transform_planner_system.txt")
    user_prompt = planning_service.prompt_renderer.render(
        "transform_planner_user.txt.j2",
        {
            "run_mode": run_mode,
            "canonical_schema_json": schema.model_dump_json(indent=2),
            "workbook_profile_json": profile.model_dump_json(indent=2),
            "reference_data_json": json.dumps({}, indent=2),
            "constraints_json": json.dumps({}, indent=2),
        },
    )

    plan = planning_service.build_plan(schema, profile, run_mode=run_mode)

    system_prompt_path = artifact_store.write_text("planner_system_prompt.txt", system_prompt)
    user_prompt_path = artifact_store.write_text("planner_user_prompt.txt", user_prompt)
    planner_response_path = artifact_store.write_text("planner_response.json", plan.model_dump_json(indent=2))
    profile_path = artifact_store.write_text("workbook_profile.json", profile.model_dump_json(indent=2))
    foundry_invocation_payload: dict[str, Any] = {"mode": selected_planner_mode, "path": "unknown"}
    if hasattr(planning_service.client, "get_last_invocation_report"):
        try:
            foundry_invocation_payload = planning_service.client.get_last_invocation_report()
        except Exception:
            foundry_invocation_payload = {"mode": selected_planner_mode, "path": "report_unavailable"}
    foundry_invocation_report_path = artifact_store.write_json(
        "foundry_invocation_report.json",
        foundry_invocation_payload,
    )

    policy_result = evaluate_script_policy(plan.python_script)
    policy_report_path = artifact_store.write_json("script_policy_report.json", policy_result)

    if not policy_result["passed"]:
        write_canonical_csv([], schema, csv_path)
        policy_failed_validation = {
            "status": "PolicyFailed",
            "passed": False,
            "issues": policy_result["findings"],
            "issue_counts": {
                "error": policy_result["error_count"],
                "warning": policy_result["warning_count"],
            },
            "metrics": {"row_count": 0, "column_count": len(schema.columns), "null_rates": {}},
        }
        validation_path = artifact_store.write_json("validation_report.json", policy_failed_validation)
        execution_result = ExecutionResult(
            status="Failed",
            run_id=run_id,
            output_path=csv_path,
            artifacts=artifact_store.list_artifacts(),
            validation_summary=policy_failed_validation,
            error="Script policy failed",
        )
        execution_result_path = artifact_store.write_text(
            "execution_result.json",
            execution_result.model_dump_json(indent=2),
        )
        blob_manifest = []
        if blob_artifact_store is not None:
            blob_manifest = mirror_local_artifacts_to_blob(artifact_store, blob_artifact_store)
            artifact_store.write_json("blob_artifact_manifest.json", {"artifacts": blob_manifest})

        return {
            "run_mode": run_mode,
            "planner_mode": selected_planner_mode,
            "run_dir": str(run_dir),
            "row_count": 0,
            "validation_status": policy_failed_validation["status"],
            "validation_errors": policy_result["error_count"],
            "validation_warnings": policy_result["warning_count"],
            "csv": str(csv_path),
            "xlsx": "",
            "profile": str(profile_path),
            "validation_report": str(validation_path),
            "planner_system_prompt": str(system_prompt_path),
            "planner_user_prompt": str(user_prompt_path),
            "planner_response": str(planner_response_path),
            "foundry_invocation_report": str(foundry_invocation_report_path),
            "script_policy_report": str(policy_report_path),
            "sandbox_execution_report": "",
            "execution_result": str(execution_result_path),
            "blob_artifact_manifest": blob_manifest,
        }

    if run_mode == "draft":
        canonical_records: list[dict[str, Any]] = []
        write_canonical_csv(canonical_records, schema, csv_path)
        sandbox_report_path = artifact_store.write_json(
            "sandbox_execution_report.json",
            {
                "status": "Skipped",
                "passed": True,
                "timed_out": False,
                "duration_ms": 0,
                "return_code": None,
                "stdout": "",
                "stderr": "",
                "result": None,
                "error": None,
            },
        )
        validation_result = {
            "status": "Draft",
            "passed": True,
            "issues": [],
            "issue_counts": {"error": 0, "warning": 0},
            "metrics": {"row_count": 0, "column_count": len(schema.columns), "null_rates": {}},
        }
        validation_path = artifact_store.write_json("validation_report.json", validation_result)
        execution_result = ExecutionResult(
            status="Succeeded",
            run_id=run_id,
            output_path=csv_path,
            artifacts=artifact_store.list_artifacts(),
            validation_summary=validation_result,
            error=None,
        )
        execution_result_path = artifact_store.write_text(
            "execution_result.json",
            execution_result.model_dump_json(indent=2),
        )
        blob_manifest = []
        if blob_artifact_store is not None:
            blob_manifest = mirror_local_artifacts_to_blob(artifact_store, blob_artifact_store)
            artifact_store.write_json("blob_artifact_manifest.json", {"artifacts": blob_manifest})

        return {
            "run_mode": run_mode,
            "planner_mode": selected_planner_mode,
            "run_dir": str(run_dir),
            "row_count": 0,
            "validation_status": validation_result["status"],
            "validation_errors": 0,
            "validation_warnings": 0,
            "csv": str(csv_path),
            "xlsx": "",
            "profile": str(profile_path),
            "validation_report": str(validation_path),
            "planner_system_prompt": str(system_prompt_path),
            "planner_user_prompt": str(user_prompt_path),
            "planner_response": str(planner_response_path),
            "foundry_invocation_report": str(foundry_invocation_report_path),
            "script_policy_report": str(policy_report_path),
            "sandbox_execution_report": str(sandbox_report_path),
            "execution_result": str(execution_result_path),
            "blob_artifact_manifest": blob_manifest,
        }

    sandbox_result = execute_script_in_sandbox(
        plan.python_script,
        {
            "input_workbook_path": input_workbook_path,
            "output_dir": str(run_dir),
            "run_mode": run_mode,
            "canonical_schema": schema.model_dump(),
        },
        timeout_seconds=30,
    )
    sandbox_report_path = artifact_store.write_json("sandbox_execution_report.json", sandbox_result)

    if not sandbox_result["passed"]:
        write_canonical_csv([], schema, csv_path)
        sandbox_failed_validation = {
            "status": "SandboxFailed",
            "passed": False,
            "issues": [
                {
                    "code": "sandbox_execution_failed",
                    "severity": "error",
                    "message": sandbox_result.get("error") or "Sandbox execution failed.",
                }
            ],
            "issue_counts": {"error": 1, "warning": 0},
            "metrics": {"row_count": 0, "column_count": len(schema.columns), "null_rates": {}},
        }
        validation_path = artifact_store.write_json("validation_report.json", sandbox_failed_validation)
        execution_result = ExecutionResult(
            status="Failed",
            run_id=run_id,
            output_path=csv_path,
            artifacts=artifact_store.list_artifacts(),
            validation_summary=sandbox_failed_validation,
            error=sandbox_result.get("error") or "Sandbox execution failed",
        )
        execution_result_path = artifact_store.write_text(
            "execution_result.json",
            execution_result.model_dump_json(indent=2),
        )
        blob_manifest = []
        if blob_artifact_store is not None:
            blob_manifest = mirror_local_artifacts_to_blob(artifact_store, blob_artifact_store)
            artifact_store.write_json("blob_artifact_manifest.json", {"artifacts": blob_manifest})

        return {
            "run_mode": run_mode,
            "planner_mode": selected_planner_mode,
            "run_dir": str(run_dir),
            "row_count": 0,
            "validation_status": sandbox_failed_validation["status"],
            "validation_errors": 1,
            "validation_warnings": 0,
            "csv": str(csv_path),
            "xlsx": "",
            "profile": str(profile_path),
            "validation_report": str(validation_path),
            "planner_system_prompt": str(system_prompt_path),
            "planner_user_prompt": str(user_prompt_path),
            "planner_response": str(planner_response_path),
            "foundry_invocation_report": str(foundry_invocation_report_path),
            "script_policy_report": str(policy_report_path),
            "sandbox_execution_report": str(sandbox_report_path),
            "execution_result": str(execution_result_path),
            "blob_artifact_manifest": blob_manifest,
        }

    raw_records = _extract_records_from_sandbox_result(sandbox_result.get("result"))
    canonical_records = normalize_records_to_canonical(raw_records, schema)

    write_canonical_csv(canonical_records, schema, csv_path)
    write_canonical_xlsx(canonical_records, schema, xlsx_path)

    validation_result = validate_canonical_records(canonical_records, schema, include_lineage=True)
    validation_path = artifact_store.write_json("validation_report.json", validation_result)
    execution_result = ExecutionResult(
        status="Succeeded",
        run_id=run_id,
        output_path=xlsx_path,
        artifacts=artifact_store.list_artifacts(),
        validation_summary=validation_result,
        error=None,
    )
    execution_result_path = artifact_store.write_text(
        "execution_result.json",
        execution_result.model_dump_json(indent=2),
    )
    blob_manifest = []
    if blob_artifact_store is not None:
        blob_manifest = mirror_local_artifacts_to_blob(artifact_store, blob_artifact_store)
        artifact_store.write_json("blob_artifact_manifest.json", {"artifacts": blob_manifest})

    return {
        "run_mode": run_mode,
        "planner_mode": selected_planner_mode,
        "run_dir": str(run_dir),
        "row_count": len(canonical_records),
        "validation_status": validation_result["status"],
        "validation_errors": validation_result["issue_counts"]["error"],
        "validation_warnings": validation_result["issue_counts"]["warning"],
        "csv": str(csv_path),
        "xlsx": str(xlsx_path),
        "profile": str(profile_path),
        "validation_report": str(validation_path),
        "planner_system_prompt": str(system_prompt_path),
        "planner_user_prompt": str(user_prompt_path),
        "planner_response": str(planner_response_path),
        "foundry_invocation_report": str(foundry_invocation_report_path),
        "script_policy_report": str(policy_report_path),
        "sandbox_execution_report": str(sandbox_report_path),
        "execution_result": str(execution_result_path),
        "blob_artifact_manifest": blob_manifest,
    }
