from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

import azure.functions as func

from src.function_app.services.pipeline_runner import run_pipeline

app = func.FunctionApp()
logger = logging.getLogger(__name__)


@app.function_name(name="ProcessWorkbookBlob")
@app.blob_trigger(
    arg_name="input_blob",
    path="%INPUT_CONTAINER%/{name}",
    connection="AzureWebJobsStorage",
)
@app.blob_output(
    arg_name="output_csv",
    path="%OUTPUT_CONTAINER%/{name}.canonical.csv",
    connection="AzureWebJobsStorage",
)
@app.blob_output(
    arg_name="output_validation",
    path="%OUTPUT_CONTAINER%/{name}.validation.json",
    connection="AzureWebJobsStorage",
)
@app.blob_output(
    arg_name="output_planner",
    path="%OUTPUT_CONTAINER%/{name}.planner.json",
    connection="AzureWebJobsStorage",
)
def process_workbook_blob(
    input_blob: func.InputStream,
    output_csv: func.Out[bytes],
    output_validation: func.Out[str],
    output_planner: func.Out[str],
) -> None:
    blob_name = Path(input_blob.name or "input.xlsx").name
    blob_stem = Path(blob_name).stem
    run_mode = os.getenv("RUN_MODE", "execute_with_validation").strip().lower()
    if run_mode not in {"draft", "execute_with_validation"}:
        run_mode = "execute_with_validation"
    planner_mode = os.getenv("PLANNER_MODE", "mock").strip().lower()
    if planner_mode not in {"mock", "live"}:
        planner_mode = "mock"
    persist_artifacts = os.getenv("FUNCTION_PERSIST_ARTIFACTS", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    local_artifact_root = os.getenv("FUNCTION_LOCAL_ARTIFACT_ROOT", "").strip()

    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = Path(temp_dir) / blob_name
        output_root = Path(temp_dir) / "run_artifacts"
        if persist_artifacts and local_artifact_root:
            output_root = Path(local_artifact_root) / blob_stem

        input_path.write_bytes(input_blob.read())
        pipeline_result = run_pipeline(
            str(input_path),
            str(output_root),
            run_mode=run_mode,
            planner_mode=planner_mode,
        )

        csv_bytes = Path(pipeline_result["csv"]).read_bytes()
        validation_text = Path(pipeline_result["validation_report"]).read_text(encoding="utf-8")
        planner_text = Path(pipeline_result["planner_response"]).read_text(encoding="utf-8")

        output_csv.set(csv_bytes)
        output_validation.set(validation_text)
        output_planner.set(planner_text)

        logger.info(
            "Blob trigger run complete: %s",
            json.dumps(
                {
                    "name": blob_name,
                    "run_mode": run_mode,
                    "planner_mode": planner_mode,
                    "validation_status": pipeline_result["validation_status"],
                    "validation_errors": pipeline_result["validation_errors"],
                    "validation_warnings": pipeline_result["validation_warnings"],
                    "row_count": pipeline_result["row_count"],
                    "artifact_run_dir": pipeline_result["run_dir"],
                }
            ),
        )
